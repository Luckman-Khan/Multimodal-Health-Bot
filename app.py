import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json
import firebase_admin
from firebase_admin import credentials, firestore
# langdetect imports removed

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

# Load custom knowledge base
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        knowledge_base = f.read()
except FileNotFoundError:
    knowledge_base = "No knowledge base file found."

# Load mock outbreak data
try:
    with open('outbreaks.json', 'r', encoding='utf-8') as f:
        outbreak_data = json.load(f)
except FileNotFoundError:
    outbreak_data = {"outbreaks": []}

# --- Multilingual Static Responses ---
# RESPONSES dictionary removed

# --- Universal Prompts ---
PROMPT_TEXT = """
Your task is to be a helpful AI health assistant.
First, identify the language of the user's question below (it could be English, Hinglish, Hindi, Bengali, Odia, etc.).
Then, answer the user's question in that same language.
Base your answer ONLY on the following information from the knowledge base:
---
{knowledge_base}
---
User's question: "{incoming_msg}"
If the question is not in the knowledge base, respond in the user's language with a message like: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant. Your task is to analyze the user-provided image of a medicine package.
First, identify the language from the user's text caption. If there is no caption, infer the language from text on the package, or default to English.
YOU MUST respond in the identified language.

**Response Format:**
- Always start with a disclaimer in {language_name}: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
- Provide the information in this structured format:
    1.  **Medicine Name:** (Brand and Generic)
    2.  **Form:** (Tablet, Syrup, etc.)
    3.  **Primary Use:**
    4.  **Recommended Age Group:**
    5.  **General Dosage Guidance:**
    6.  **Storage Instructions:**
    7.  **Common Warnings:**
- If you do not have reliable information on any point, you MUST state "Information not available in my knowledge base" in {language_name}. Do not invent details.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    user_phone_number = request.values.get('From') 

    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    try:
        # --- Language Handling with Memory --- block has been removed ---

        # Get the response dictionary for the user's language, defaulting to English
        # This logic has been removed as we will generate all responses with the AI

        # --- Keyword Logic ---
        if clean_msg == 'alert':
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            user_district = ""
            user_doc = None
            if db:
                user_doc_ref = db.collection('users').document(user_phone_number)
                user_doc = user_doc_ref.get()

            if user_doc and user_doc.exists:
                user_district = user_doc.to_dict().get('district', '').lower()
            
            if not user_district:
                 # AI generates the response in the user's language
                 alert_prompt = f"The user asked for an alert but has not set their district. Respond in the same language as '{incoming_msg}' with a message like: 'Please set your district first. Send: `set district [Your District Name]`'"
                 response = model.generate_content(alert_prompt)
                 msg.body(response.text)
                 return str(resp)

            alert_found = None
            for alert in outbreak_data.get("outbreaks", []):
                if alert['district'].lower() == user_district:
                    alert_found = alert
                    break
            
            if alert_found:
                # AI generates the alert in the user's language
                alert_prompt = f"""
                You are a health alert system.
                Generate a concise and clear health alert message in the same language as the user's message ('{incoming_msg}').
                The alert should be based on this data:
                - Disease: {alert_found['disease']}
                - Severity: {alert_found['severity']}
                - Recommendation: {alert_found['recommendation']}
                Start the message with a warning emoji (⚠️).
                """
                response = model.generate_content(alert_prompt)
                msg.body(response.text)
            else:
                # AI generates the response in the user's language
                alert_prompt = f"The user asked for an alert for their district '{user_district.capitalize()}' but no alert was found. Respond in the same language as '{incoming_msg}' with a message like: 'There are no new health alerts for your registered district: {user_district.capitalize()}'"
                response = model.generate_content(alert_prompt)
                msg.body(response.text)
            return str(resp)
        
        elif 'update district' in clean_msg or 'change district' in clean_msg:
            # AI generates the response in the user's language
            alert_prompt = f"The user wants to update their district. Respond in the same language as '{incoming_msg}' with a message like: 'To set or update your location, please send a message in this format: `set district [Your District Name]`'"
            response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(alert_prompt)
            msg.body(response.text)
            return str(resp)

        elif clean_msg.startswith('set district'):
            parts = incoming_msg.strip().split()
            if len(parts) > 2:
                district_name = " ".join(parts[2:])
                if db:
                    user_doc_ref = db.collection('users').document(user_phone_number)
                    user_doc_ref.set({'district': district_name}, merge=True)
                    # AI generates the response in the user's language
                    alert_prompt = f"The user has successfully set their district to '{district_name}'. Confirm this action in the same language as '{incoming_msg}' with a message like: 'Thank you! Your district has been set to: {district_name}'"
                    response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(alert_prompt)
                    msg.body(response.text)
                else:
                    # Fallback to English if DB fails
                    msg.body("Database connection is not available.")
            else:
                # AI generates the response in the user's language
                alert_prompt = f"The user tried to set a district but provided no name. Respond in the same language as '{incoming_msg}' with a message like: 'Please provide a district name. Example: `set district Murshidabad`'"
                response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(alert_prompt)
                msg.body(response.text)
            return str(resp)

        elif clean_msg.startswith('feedback'):
            feedback_text = incoming_msg.strip()[len('feedback '):]
            if db and feedback_text:
                db.collection('feedback').add({
                    'user': user_phone_number,
                    'message': feedback_text,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                # AI generates the response in the user's language
                alert_prompt = f"The user has provided feedback. Thank them in the same language as '{incoming_msg}' with a message like: 'Thank you for your feedback! It helps us improve.'"
                response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(alert_prompt)
                msg.body(response.text)
            else:
                # AI generates the response in the user's language
                alert_prompt = f"The user tried to give feedback but provided no text. Respond in the same language as '{incoming_msg}' with a message like: 'Please provide your feedback after the word 'feedback'.'"
                response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(alert_prompt)
                msg.body(response.text)
            return str(resp)

        # --- AI Processing Logic ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        if media_url:
            # Image Logic
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')
            
            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
                # The universal prompt already handles language
                full_prompt = [PROMPT_IMAGE, f"User's text caption: {incoming_msg}", image_parts[0]]
                response = model.generate_content(full_prompt)
                response.resolve()
                msg.body(response.text)
            else:
                # AI generates the response in the user's language
                alert_prompt = f"The user sent an invalid image file. Respond in the same language as '{incoming_msg}' with a message like: 'Sorry, I could not process the image file.'"
                response = model.generate_content(alert_prompt)
                msg.body(response.text)
        else:
            # Text Logic
            prompt = PROMPT_TEXT.format(knowledge_base=knowledge_base, incoming_msg=incoming_msg)
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        # Universal error message in English
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)


if __name__ == "__main__":
    app.run(port=5000, debug=True)


