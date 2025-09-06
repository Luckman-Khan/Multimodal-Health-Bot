import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Load environment variables from .env file for local testing
load_dotenv()

app = Flask(__name__)

# --- Configuration ---
# This is the correct way to get the API key from the environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Load your custom knowledge base from a file
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        knowledge_base = f.read()
except FileNotFoundError:
    knowledge_base = "No knowledge base file found."


@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower()
    media_url = request.values.get('MediaUrl0')

    resp = MessagingResponse()
    msg = resp.message()

    try:
        # --- Image (Multimodal) Logic ---
        if media_url:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            image_response = requests.get(media_url)
            image_data = image_response.content
            image_parts = [{"mime_type": "image/jpeg", "data": image_data}]

            prompt = """
            You are a helpful AI health assistant.
            IMPORTANT: Start your response with this exact disclaimer in bold: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
            Describe what you see in simple terms. DO NOT give a diagnosis.
            If it looks like medicine, describe it generally.
            If it looks like a skin condition, describe it (e.g., redness, swelling).
            """
            
            response = model.generate_content([prompt, image_parts[0]], stream=False)
            response.resolve()
            msg.body(response.text)

        # --- Text Logic ---
        else:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"""
            Answer the user's question based ONLY on the following information:
            ---
            {knowledge_base}
            ---
            User's question: "{incoming_msg}"
            If the question is not in the information, say 'I can only answer questions about topics in my knowledge base.'
            """
            
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        error_message = "Sorry, I encountered an error. Please try again later."
        print(f"An error occurred: {e}")
        msg.body(error_message)

    return str(resp)


if __name__ == "__main__":

    app.run(port=5000, debug=True)

