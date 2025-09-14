import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from dateutil.parser import parse

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
# Simplified for a stateless bot
RESPONSES = {
    'en': {
        'set_district_success': "Thank you! Your district has been set.",
        'error_message': "Sorry, I encountered an error. Please try again later.",
        'vaccine_prompt': "To get a personalized child vaccination schedule, please send your message in this format:\n`schedule dob DD-MM-YYYY`",
        'dob_error': "Could not understand the date. Please use the format: `schedule dob DD-MM-YYYY`",
        'schedule_saved': "Here is the upcoming vaccination schedule for your child:"
    },
    # Add other language translations if needed for static messages
}

# --- Universal Prompts ---
PROMPT_TEXT = """
Your task is to be a helpful AI health assistant.
First, identify the language of the user's question (e.g., English, Hinglish, Hindi, Bengali, Odia).
Then, answer the user's question in that same language.
Base your answer ONLY on the knowledge base provided below.
---
{knowledge_base}
---
User's question: "{incoming_msg}"
If the question is not in the knowledge base, respond in the user's language with a message like: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant.
First, identify the language from the user's text caption. If there is no caption, default to English.
Then, analyze the image and respond in the identified language.
IMPORTANT: Start your response with a disclaimer in the identified language: '*I am an AI assistant, not a doctor...*'
Focus only on medically relevant items.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    
    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # --- Keyword Logic ---
        if 'schedule' in clean_msg or 'vaccine' in clean_msg:
            if 'dob' in clean_msg:
                try:
                    dob_str = clean_msg.split('dob')[1].strip()
                    dob = parse(dob_str, dayfirst=True).date()
                    
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

                    response_text = f"{RESPONSES['en']['schedule_saved']}\n\n"
                    for item in schedule_list:
                        response_text += f"*{item['due_text']}* ({item['due_date']}):\n- {item['name']}\n\n"
                    msg.body(response_text)

                except Exception as e:
                    print(f"DOB parsing error: {e}")
                    msg.body(RESPONSES['en']['dob_error'])
            else:
                msg.body(RESPONSES['en']['vaccine_prompt'])

        elif clean_msg == 'alert':
            alert_found = None
            for alert in outbreak_data.get("outbreaks", []):
                if alert['district'].lower() == 'howrah': # Hardcoded for demo
                    alert_found = alert
                    break
            
            if alert_found:
                alert_prompt = f"Generate a concise health alert in English based on this data: Disease: {alert_found['disease']}, Recommendation: {alert_found['recommendation']}. Start with a warning emoji (⚠️)."
                response = model.generate_content(alert_prompt)
                response.resolve()
                if response.text and response.text.strip():
                    msg.body(response.text)
                else:
                    msg.body(RESPONSES['en']['error_message'])
            else:
                msg.body("No alerts found for Howrah district.")

        elif clean_msg.startswith('set district'):
            msg.body(RESPONSES['en']['set_district_success'].format(district_name="your district"))

        # --- AI Processing Logic (if no keyword was matched) ---
        elif not msg.body:
            if media_url:
                image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
                mime_type = image_response.headers.get('Content-Type')
                
                if mime_type and mime_type.startswith('image/'):
                    image_data = image_response.content
                    image_parts = [{"mime_type": mime_type, "data": image_data}]
                    full_prompt = [PROMPT_IMAGE + "\nUser's text caption: " + incoming_msg, image_parts[0]]
                    response = model.generate_content(full_prompt)
                    response.resolve()
                    if response.text and response.text.strip():
                        msg.body(response.text)
                else:
                    msg.body("Sorry, I could not process the image file.")
            else:
                prompt = PROMPT_TEXT.format(knowledge_base=knowledge_base, incoming_msg=incoming_msg)
                response = model.generate_content(prompt)
                response.resolve()
                if response.text and response.text.strip():
                    msg.body(response.text)

    except Exception as e:
        print(f"CRITICAL ERROR in main try block: {e}")
        msg.body(RESPONSES['en']['error_message'])

    if not msg.body:
        msg.body(RESPONSES['en']['error_message'])

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)

