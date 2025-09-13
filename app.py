import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import json

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

    resp = MessagingResponse()
    msg = resp.message()
    
    # Clean the incoming message for keyword checks
    clean_msg = incoming_msg.strip().lower()

    try:
        # --- Keyword Logic ---
        if clean_msg == 'alert':
            if outbreak_data["alerts"]:
                alert = outbreak_data["alerts"][0]
                alert_message = f"{alert['message_en']}\n\n{alert['message_hi']}\n\n{alert['message_bn']}\n\n{alert['message_or']}"
                msg.body(alert_message)
            else:
                msg.body("There are no new health alerts in your area.")
            return str(resp)
        
        # NEW: Handle district update requests
        elif 'update district' in clean_msg or 'change district' in clean_msg:
            msg.body("To update your location for health alerts, please reply with the name of your new district.")
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

