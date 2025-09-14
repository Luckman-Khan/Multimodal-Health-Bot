import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json
import firebase_admin
from firebase_admin import credentials, firestore
from langdetect import detect, LangDetectException

# --- Firebase Initialization ---
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("[DEBUG] Firebase connected successfully.")
except Exception as e:
    print(f"[ERROR] Firebase connection failed: {e}")
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

# --- Supported Languages ---
SUPPORTED_LANGS = ['en', 'hi', 'bn', 'or']
lang_map = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'or': 'Odia'}

# --- Multilingual Static Responses ---
RESPONSES = {
    'en': {
        'set_district_success': "Thank you! Your district has been set to: {district_name}",
        'no_district_for_alert': "Please set your district first to receive local alerts. Send: `set district [Your District Name]`",
        'no_alert_found': "There are no new health alerts for your registered district: {district_name}",
        'update_district_prompt': "To set or update your location, please send a message in this format:\n\n`set district [Your District Name]`\n\nFor example: `set district Murshidabad`",
        'provide_district_name': "Please provide a district name. Example: `set district Murshidabad`",
        'db_connection_error': "Database connection is not available.",
        'feedback_success': "Thank you for your feedback! It helps us improve.",
        'feedback_prompt': "Please provide your feedback after the word 'feedback'.",
        'error_message': "Sorry, I encountered an error. Please try again later.",
        'image_error': "Sorry, I could not process the image file."
    },
    # hi, bn, or same as before...
}

# --- Prompts ---
PROMPT_TEXT = """
Your task is to be a helpful AI health assistant.
YOU MUST respond in the following language: {language_name}.
Base your answer ONLY on the following information from the knowledge base:
---
{knowledge_base}
---
User's question: "{incoming_msg}"
If the question is not in the knowledge base, respond in {language_name} with a message like: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant. Your task is to analyze the user-provided image of a medicine package.
YOU MUST respond in the following language: {language_name}.

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
- If you do not have reliable information on any point, you MUST state "Information not available in my knowledge base" in {language_name}.
"""

# --- WhatsApp Handler ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    media_url = request.values.get('MediaUrl0')
    user_phone_number = request.values.get('From')

    resp = MessagingResponse()
    msg = resp.message()
    clean_msg = incoming_msg.lower()

    print(f"\n[DEBUG] Incoming: {incoming_msg} from {user_phone_number}")

    # Default language
    stored_lang = 'en'

    try:
        user_doc_ref, user_doc = None, None
        if db:
            user_doc_ref = db.collection('users').document(user_phone_number)
            user_doc = user_doc_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                stored_lang = user_data.get('language', 'en')

        # Detect language if not a command
        is_command = clean_msg.startswith('alert') or clean_msg.startswith('set district') \
                     or clean_msg.startswith('feedback') or 'update district' in clean_msg \
                     or 'change district' in clean_msg

        if not is_command and incoming_msg:
            try:
                current_lang = detect(incoming_msg)
                if current_lang in SUPPORTED_LANGS and current_lang != stored_lang and db:
                    user_doc_ref.set({'language': current_lang}, merge=True)
                    stored_lang = current_lang
                    print(f"[DEBUG] Language updated to {current_lang}")
            except LangDetectException:
                print("[WARN] Could not detect language.")

        language_name = lang_map.get(stored_lang, 'English')
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])

        # --- Commands ---
        if clean_msg.startswith('alert'):
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            user_district = ""
            if user_doc and user_doc.exists:
                user_district = user_doc.to_dict().get('district', '').lower()

            if not user_district:
                msg.body(responses['no_district_for_alert'])
                return str(resp)

            alert_found = next((a for a in outbreak_data.get("outbreaks", []) 
                                if a['district'].lower() == user_district), None)

            if alert_found:
                alert_prompt = f"""
                You are a health alert system.
                Generate a concise and clear health alert message in {language_name}.
                The alert should be based on this data:
                - Disease: {alert_found['disease']}
                - Severity: {alert_found['severity']}
                - Recommendation: {alert_found['recommendation']}
                Start the message with ⚠️.
                """
                response = model.generate_content(alert_prompt)
                response.resolve()
                msg.body(response.text or responses['error_message'])
            else:
                msg.body(responses['no_alert_found'].format(
                    district_name=user_district.capitalize()))
            return str(resp)

        elif 'update district' in clean_msg or 'change district' in clean_msg:
            msg.body(responses['update_district_prompt'])
            return str(resp)

        elif clean_msg.startswith('set district'):
            parts = incoming_msg.split()
            if len(parts) > 2:
                district_name = " ".join(parts[2:])
                if db:
                    user_doc_ref.set({'district': district_name}, merge=True)
                    msg.body(responses['set_district_success'].format(district_name=district_name))
                else:
                    msg.body(responses['db_connection_error'])
            else:
                msg.body(responses['provide_district_name'])
            return str(resp)

        elif clean_msg.startswith('feedback'):
            feedback_text = incoming_msg[len('feedback '):].strip()
            if db and feedback_text:
                db.collection('feedback').add({
                    'user': user_phone_number,
                    'message': feedback_text,
                    'timestamp': firestore.SERVER_TIMESTAMP
                })
                msg.body(responses['feedback_success'])
            else:
                msg.body(responses['feedback_prompt'])
            return str(resp)

        # --- AI Processing ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        if media_url:
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')

            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
                prompt = PROMPT_IMAGE.format(language_name=language_name)
                full_prompt = [prompt, f"User caption: {incoming_msg}", image_parts[0]]
                response = model.generate_content(full_prompt)
                response.resolve()
                msg.body(response.text or responses['image_error'])
            else:
                msg.body(responses['image_error'])
        else:
            prompt = PROMPT_TEXT.format(
                language_name=language_name,
                knowledge_base=knowledge_base,
                incoming_msg=incoming_msg
            )
            response = model.generate_content(prompt)
            response.resolve()
            msg.body(response.text or responses['error_message'])

    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    return str(resp)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
