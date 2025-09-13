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
    media_url = request.values.get('MediaUrl0')

    resp = MessagingResponse()
    msg = resp.message()

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        if media_url:
            # --- Image Logic ---
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')

            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]

                # Step 1: Extract medicine name & form
                extract_prompt = """
                You are a helpful assistant. Look at this medicine package image.
                Extract ONLY:
                - Medicine name (brand and generic if visible)
                - Form (tablet, capsule, syrup, etc.)
                Respond in plain text only.
                """
                extract_response = model.generate_content([extract_prompt, image_parts[0]])
                extract_response.resolve()
                medicine_name = extract_response.text.strip()

                # Step 2: Search reliable sources
                from openai import web  # assumes you have web search enabled
                search_query = f"{medicine_name} drug use dosage age group storage site:fda.gov OR site:drugs.com OR site:nhs.uk"
                search_results = web.search(search_query)

                # Step 3: Summarize in structured format
                structured_prompt = f"""
                You are a medical information assistant.
                Medicine identified: {medicine_name}

                Use the following reliable source results:
                {search_results}

                Respond following these rules:
                - If caption exists, reply in that language; otherwise, use English.
                - Always start with: "*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*"
                - Provide structured info:
                  1. Medicine Name (brand + generic)
                  2. Form (tablet, syrup, etc.)
                  3. Primary Use / Indication
                  4. Recommended Age Group
                  5. Typical Dosage Guidance (general, not personalized)
                  6. Special Instructions (e.g., storage, use after opening if syrup)
                  7. Common Warnings / Side Effects
                - Do NOT invent details. If not available, write "Not specified in reliable sources."
                """
                final_response = model.generate_content(structured_prompt)
                final_response.resolve()

                msg.body(final_response.text)

            else:
                msg.body("Sorry, I could not process the image file.")

        else:
            # --- Text Logic ---
            prompt = PROMPT_TEXT.format(incoming_msg=incoming_msg)
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)



if __name__ == "__main__":
    app.run(port=5000, debug=True)
