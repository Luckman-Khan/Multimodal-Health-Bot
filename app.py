import os
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Load your knowledge base
with open('knowledge.txt', 'r') as f:
    knowledge_base = f.read()

# Configure Gemini API
# It's better to set this as an environment variable in Render
GEMINI_API_KEY = "YOUR_API_KEY_HERE"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    msg = resp.message()

    # Create the prompt for Gemini
    prompt = f"""
    You are a simple, friendly AI health assistant for people in rural India.
    Answer the user's question based ONLY on the following information:
    ---
    {knowledge_base}
    ---
    User's question: "{incoming_msg}"
    Keep your answer short, in simple language, and use bullet points or lists if possible.
    If the question is not in the information, say 'I can only answer questions about topics in my knowledge base.'
    """

    # Get the response from Gemini
    response = model.generate_content(prompt)
    msg.body(response.text)

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000)