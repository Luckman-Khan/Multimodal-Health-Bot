import os
import requests
import google.generativeai as genai
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json
import firebase_admin
from firebase_admin import credentials, firestore
from langdetect import detect, LangDetectException
from datetime import datetime, timedelta
from dateutil.parser import parse

# --- Firebase Initialization ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase connected successfully.")
except Exception as e:
    print(f"Firebase connection failed: {e}")
    db = None

# Load environment variables
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
genai.configure(api_key=GEMINI_API_KEY)

# Load data files
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        knowledge_base = f.read()
    with open('outbreaks.json', 'r', encoding='utf-8') as f:
        outbreak_data = json.load(f)
    with open('vaccine_schedule.json', 'r', encoding='utf-8') as f:
        vaccine_data = json.load(f)
except FileNotFoundError as e:
    print(f"Error loading data file: {e}")
    knowledge_base = "No knowledge base file found."
    outbreak_data = {"outbreaks": []}
    vaccine_data = {"schedule": []}


# --- Multilingual Static Responses ---
RESPONSES = {
    'en': {
        'set_district_success': "Thank you! Your district has been set to: {district_name}",
        'no_district_for_alert': "Please set your district first. Send: `set district [Your District Name]`",
        'no_alert_found': "There are no new health alerts for your registered district: {district_name}",
        'update_district_prompt': "To set or update your location, send a message in this format:\n`set district [Your District Name]`",
        'provide_district_name': "Incorrect format. Please provide a district name.\nExample: `set district Murshidabad`",
        'db_connection_error': "Database connection is not available.",
        'feedback_success': "Thank you for your feedback!",
        'feedback_prompt': "Incorrect format. Please provide your feedback after the word 'feedback'.\nExample: `feedback This bot is helpful.`",
        'error_message': "Sorry, I encountered an error. Please try again later.",
        'image_error': "Sorry, I could not process the image file.",
        'vaccine_prompt': "To get a personalized child vaccination schedule, please provide the date of birth in this format: DD-MM-YYYY",
        'dob_error': "Incorrect format. Please start again by sending 'schedule' or 'vaccine'.",
        'schedule_saved': "Here is the upcoming vaccination schedule for your child. I will also send you a reminder before each due date."
    },
    # Other languages omitted here for brevity...
}

# --- Universal Prompts ---
PROMPT_TEXT = """
Your task is to be a helpful AI health assistant.
YOU MUST respond in the following language: {language_name}.
Base your answer ONLY on the knowledge base:
---
{knowledge_base}
---
User's question: "{incoming_msg}"
If the question is not in the knowledge base, respond in {language_name} with: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant.
YOU MUST respond in the following language: {language_name}.
**Response Format:**
- Start with a disclaimer in {language_name}: '*I am an AI assistant, not a doctor...*'
- Provide structured information: Medicine Name, Form, Use, etc.
- If information is not available, state that in {language_name}.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    user_phone_number = request.values.get('From') 

    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    # --- Default Language Setup ---
    stored_lang = 'en'
    
    try:
        # --- Language and State Handling with Memory ---
        user_state = None
        user_doc_ref = None
        if db:
            user_doc_ref = db.collection('users').document(user_phone_number)
            user_doc = user_doc_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                stored_lang = user_data.get('language', 'en')
                user_state = user_data.get('state')

        is_command = any(keyword in clean_msg for keyword in ['alert', 'district', 'feedback', 'schedule', 'vaccine'])

        if not is_command and incoming_msg and user_state is None:
            try:
                current_lang = detect(incoming_msg)
                if db and current_lang != stored_lang:
                    user_doc_ref.set({'language': current_lang}, merge=True)
                    stored_lang = current_lang
            except LangDetectException:
                pass
        
        lang_map = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'or': 'Odia'}
        language_name = lang_map.get(stored_lang, 'English')
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])

        # --- State-Based Logic: Awaiting DOB ---
        if user_state == 'awaiting_dob':
            try:
                dob = parse(incoming_msg.strip(), dayfirst=True).date()
                
                schedule_list = []
                for item in vaccine_data['schedule']:
                    due_date = dob
                    if 'due_weeks' in item:
                        due_date += timedelta(weeks=item['due_weeks'])
                    elif 'due_months' in item:
                        due_date += timedelta(days=item['due_months'] * 30)
                    
                    schedule_list.append({
                        'name': item['name'],
                        'due_date': due_date.strftime('%d-%m-%Y'),
                        'due_text': item['due_text']
                    })

                if db:
                    user_doc_ref.set({'vaccine_schedule': schedule_list, 'dob': str(dob), 'state': None}, merge=True)

                response_text = f"{responses['schedule_saved']}\n\n"
                for item in schedule_list:
                    response_text += f"*{item['due_text']}* ({item['due_date']}):\n- {item['name']}\n\n"
                msg.body(response_text)

            except Exception as e:
                print(f"DOB parsing error from state: {e}")
                if db:
                    user_doc_ref.set({'state': None}, merge=True) # Clear the state after an error
                msg.body(responses['dob_error'])
            
            return Response(str(resp), mimetype="application/xml")

        # --- Keyword Logic ---
        if 'schedule' in clean_msg or 'vaccine' in clean_msg:
            if db:
                user_doc_ref.set({'state': 'awaiting_dob'}, merge=True)
                msg.body(responses['vaccine_prompt'])
            else:
                msg.body(responses['db_connection_error'])

        elif clean_msg == 'alert':
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            user_district = ""
            if db and user_doc and user_doc.exists:
                user_district = user_doc.to_dict().get('district', '').lower()
            
            if not user_district and db:
                 msg.body(responses['no_district_for_alert'])
            elif not db:
                 msg.body(responses['db_connection_error'])
            else:
                alert_found = None
                for alert in outbreak_data.get("outbreaks", []):
                    if alert['district'].lower() == user_district:
                        alert_found = alert
                        break
                
                if alert_found:
                    alert_prompt = f"Generate a concise health alert in {language_name} based on this data: Disease: {alert_found['disease']}, Recommendation: {alert_found['recommendation']}. Start with a warning emoji (⚠️)."
                    response = model.generate_content(alert_prompt)
                    response.resolve() 
                    if response.text and response.text.strip():
                        msg.body(response.text)
                    else: 
                        msg.body(responses['error_message'])
                else:
                    msg.body(responses['no_alert_found'].format(district_name=user_district.capitalize()))
        
        elif clean_msg.startswith('set district'):
            parts = incoming_msg.strip().split()
            if len(parts) > 2:
                district_name = " ".join(parts[2:])
                if db:
                    user_doc_ref.set({'district': district_name}, merge=True)
                    msg.body(responses['set_district_success'].format(district_name=district_name))
                else:
                    msg.body(responses['db_connection_error'])
            else:
                msg.body(responses['provide_district_name'])

        elif clean_msg.startswith('feedback'):
            feedback_text = incoming_msg.strip()[len('feedback '):]
            if db and feedback_text:
                db.collection('feedback').add({
                    'user': user_phone_number,
                    'message': feedback_text,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                msg.body(responses['feedback_success'])
            else:
                msg.body(responses['feedback_prompt'])

        # --- AI Processing Logic (if no keyword was matched) ---
        elif not msg.body():
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            if media_url:
                image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
                mime_type = image_response.headers.get('Content-Type')
                
                if mime_type and mime_type.startswith('image/'):
                    image_data = image_response.content
                    image_parts = [{"mime_type": mime_type, "data": image_data}]
                    prompt = PROMPT_IMAGE.format(language_name=language_name)
                    full_prompt = [prompt, f"User's text caption: {incoming_msg}", image_parts[0]]
                    response = model.generate_content(full_prompt)
                    response.resolve()
                    if response.text and response.text.strip():
                        msg.body(response.text)
                    else: 
                        msg.body(responses['error_message'])
                else:
                    msg.body(responses['image_error'])
            else:
                prompt = PROMPT_TEXT.format(language_name=language_name, knowledge_base=knowledge_base, incoming_msg=incoming_msg)
                response = model.generate_content(prompt)
                response.resolve() 
                if response.text and response.text.strip():
                    msg.body(response.text)
                else: 
                    msg.body(responses['error_message'])

    except Exception as e:
        print(f"An error occurred: {e}")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    # --- Final Fallback to prevent silent failures ---
    if not msg.body():
        print("DEBUG: No response was set. Sending default error message.")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    # Debug log for Twilio
    print("DEBUG Twilio Response:", str(resp))

    return Response(str(resp), mimetype="application/xml")    

if __name__ == "__main__":
    app.run(port=5000, debug=True)
