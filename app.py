import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Load custom knowledge base
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
            
            mime_type = image_response.headers.get('Content-Type')
            print(f"Debug: Detected MIME Type is:{mime_type}")
            
            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]

                prompt = """
                You are a helpful AI health assistant.
                IMPORTANT: Start your response with this exact disclaimer in bold: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
                Describe what you see in simple terms. DO NOT give a diagnosis.
                """

                response = model.generate_content([prompt, image_parts[0]], stream=False)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body("Sorry, I could not process the image file. Please send a standard image format like JPEG or PNG.")

        # --- Text Logic ---
        else:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            prompt = f"""
            Answer the user's question based ONLY on the following information:
            ---
            {knowledge_base}
            ---
            User's question: "{incoming_msg}"
            If the question is not in the information, say:
            'I can only answer questions about topics in my knowledge base.'
            """

            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)


if __name__ == "__main__":

    app.run(port=5000, debug=True)
