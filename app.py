import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

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

# --- Universal Prompts ---
# This single prompt will handle all languages for text
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

<<<<<<< HEAD
# This single prompt will handle all languages for images
PROMPT_IMAGE = """
You are a helpful AI health assistant. Your task is to analyze an image and respond.

**Language Control Rules:**
1. Check for a text caption from the user. If a caption exists, YOU MUST respond in the same language as the caption.
2. If there is NO text caption, YOU MUST respond in English. Do not use any other language.

**Response Instructions:**
- Start your response with a disclaimer like this in the chosen language: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
- Describe what you see in simple terms. DO NOT give a diagnosis.
- Focus only on medically relevant items in the image.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
=======
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower()
>>>>>>> parent of fe4939f (English and Hinglish language support)
    media_url = request.values.get('MediaUrl0')

    resp = MessagingResponse()
    msg = resp.message()

    try:
<<<<<<< HEAD
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        if media_url:
            # Image Logic
=======
        # --- Image (Multimodal) Logic ---
        if media_url:
            # UPDATED: Use Twilio credentials to securely download the image
>>>>>>> parent of fe4939f (English and Hinglish language support)
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            
            mime_type = image_response.headers.get('Content-Type')
            print(f"DEBUG: Detected MIME Type is: {mime_type}") # We can leave this for now
            
            if mime_type and mime_type.startswith('image/'):
                model = genai.GenerativeModel('gemini-1.5-flash-latest')
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
<<<<<<< HEAD
                full_prompt = [PROMPT_IMAGE + "\nUser's text caption: " + incoming_msg, image_parts[0]]
                response = model.generate_content(full_prompt, stream=False)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body("Sorry, I could not process the image file.")
        else:
            # Text Logic
            prompt = PROMPT_TEXT.format(incoming_msg=incoming_msg)
=======

        
                prompt = """
            You are a helpful AI health information assistant. Analyze this image.
            IMPORTANT: Start your response with this exact disclaimer in bold: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for specific medical advice.*'
            If the image is of a medicine or prescription:
            1. Identify the name of the medicine if it is clearly visible.
            2. State its general purpose (e.g., "Paracetamol is a common medicine used to treat pain and fever").
            3. DO NOT suggest a dosage, frequency, or how to take it.
            4. End your response by strongly advising the user to follow their doctor's exact prescription or consult a pharmacist for instructions.
            """
            

                response = model.generate_content([prompt, image_parts[0]], stream=False)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body("Sorry, I could not process the image file. Twilio returned a non-image file type.")

        # --- Text Logic ---
        else:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
           

            prompts = {
                'en': f"""
                You are a friendly health assistant. The user might be writing in English or Hinglish (Hindi written in the Roman alphabet).
                Answer the user's question in the same language and script they used (English or Hinglish).
                Base your answer ONLY on the following information from the knowledge base:
                ---
                {knowledge_base}
                ---
                User's question: "{incoming_msg}"
                If the question is not in the knowledge base, respond in the user's language: 'I can only answer questions about topics in my knowledge base.'
                """,
                'hi': f"""
                केवल निम्नलिखित जानकारी के आधार पर उपयोगकर्ता के प्रश्न का उत्तर हिंदी में दें:
                ---
                {knowledge_base}
                ---
                उपयोगकर्ता का प्रश्न: "{incoming_msg}"
                यदि प्रश्न जानकारी में नहीं है, तो हिंदी में कहें: 'मैं केवल अपने ज्ञानकोष में मौजूद विषयों के बारे में ही प्रश्नों का उत्तर दे सकता हूं।'
                """
            }

>>>>>>> parent of fe4939f (English and Hinglish language support)
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)

<<<<<<< HEAD
=======

if __name__ == "__main__":
>>>>>>> parent of fe4939f (English and Hinglish language support)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
