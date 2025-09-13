import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Initialization ---
# IMPORTANT: You need to download your Firebase service account key and save it as 'serviceAccountKey.json'
# This file MUST be added to your .gitignore file to keep it secure.
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
    outbreak_data = {"alerts": []}

# --- Universal Prompts ---
PROMPT_TEXT = f"""
Your task is to be a helpful AI health assistant.
First, identify the language of the user's question below (it could be English, Hinglish, Hindi, Bengali, Odia, etc.).
Then, answer the user's question in that same language.
Base your answer ONLY on the following information from the knowledge base:
---
{knowledge_base}
---
User's question: "{{incoming_msg}}"
If the question is not in the knowledge base, respond in the user's language with a message like: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant. Your task is to analyze the user-provided image of a medicine package and provide a structured summary based on your internal knowledge.

**Language Control Rules (Follow these strictly):**
1.  Analyze the user's text caption provided separately. If a caption exists and has a detectable language, YOU MUST respond in that same language.
2.  If there is NO text caption, you must INFER the most likely language for the user. Consider the text visible on the package (e.g., if it's in Hindi, reply in Hindi). If no clues are available, default to English.

**Response Format:**
- Always start with a disclaimer in the identified or inferred language: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
- Provide the information in this structured format:
    1.  **Medicine Name:** (Brand and Generic)
    2.  **Form:** (Tablet, Syrup, etc.)
    3.  **Primary Use:**
    4.  **Recommended Age Group:**
    5.  **General Dosage Guidance:**
    6.  **Storage Instructions:**
    7.  **Common Warnings:**
- If you do not have reliable information on any point, you MUST state "Information not available in my knowledge base" in the response language. Do not invent details.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    # Get the user's phone number, which will be our unique ID
    user_phone_number = request.values.get('From') 

    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    try:
        # --- Keyword Logic ---
        if clean_msg == 'alert':
            user_ref = db.collection('users').document(user_phone_number).get()
            if user_ref.exists:
                user_district = user_ref.to_dict().get('district', '').lower()
                alert_found = False
                for alert in outbreak_data["alerts"]:
                    if alert['district'].lower() == user_district:
                        alert_message = f"{alert['message_en']}\n\n{alert['message_hi']}\n\n{alert['message_bn']}\n\n{alert['message_or']}"
                        msg.body(alert_message)
                        alert_found = True
                        break
                if not alert_found:
                    msg.body("There are no new health alerts for your registered district.")
            else:
                msg.body("Please set your district first to receive local alerts. Send: `set district [Your District Name]`")
            return str(resp)
        
        elif 'update district' in clean_msg or 'change district' in clean_msg:
            msg.body("To set or update your location, please send a message in this format:\n\n`set district [Your District Name]`\n\nFor example: `set district Murshidabad`")
            return str(resp)

        elif clean_msg.startswith('set district'):
            parts = incoming_msg.strip().split()
            if len(parts) > 2:
                district_name = " ".join(parts[2:])
                # Save the user's district to Firestore
                if db:
                    user_ref = db.collection('users').document(user_phone_number)
                    user_ref.set({'district': district_name})
                    msg.body(f"Thank you! Your district has been set to: {district_name}")
                else:
                    msg.body("Database connection is not available. Could not save your district.")
            else:
                msg.body("Please provide a district name after 'set district'. For example: `set district Murshidabad`")
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
                full_prompt = [PROMPT_IMAGE, f"User's text caption: {incoming_msg}", image_parts[0]]
                response = model.generate_content(full_prompt)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body("Sorry, I could not process the image file.")
        else:
            # Text Logic
            prompt = PROMPT_TEXT.format(incoming_msg=incoming_msg)
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)


if __name__ == "__main__":
    app.run(port=5000, debug=True)

