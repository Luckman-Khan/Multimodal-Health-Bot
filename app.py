import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import logging
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. Configuration & Setup ---
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# --- Firebase Initialization ---
# Initialize Firebase Admin SDK
# Ensure 'serviceAccountKey.json' is in your project root or use environment variables
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    logging.info("Firebase Firestore connected successfully.")
except Exception as e:
    logging.error(f"Firebase connection failed: {e}")
    db = None

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logging.error("GEMINI_API_KEY is missing!")

# --- 2. Database Functions (Firestore) ---

def get_user_profile(phone_number):
    """Fetches user profile from Firestore."""
    if not db:
        return "Database unavailable. Treating as new user."
    
    doc_ref = db.collection('users').document(phone_number)
    doc = doc_ref.get()
    
    if doc.exists:
        return doc.to_dict().get('medical_profile', "No specific medical history provided.")
    else:
        # Create new user document if it doesn't exist
        doc_ref.set({
            'phone': phone_number,
            'medical_profile': "No specific medical history provided."
        })
        return "No specific medical history provided."

def update_user_profile(phone_number, new_info):
    """Updates user medical profile in Firestore."""
    if not db:
        return

    doc_ref = db.collection('users').document(phone_number)
    doc = doc_ref.get()
    
    if doc.exists:
        current_profile = doc.to_dict().get('medical_profile', "")
        # Append new info
        if "No specific" in current_profile:
             updated_profile = new_info
        else:
             updated_profile = f"{current_profile}, {new_info}"
        
        doc_ref.update({'medical_profile': updated_profile})
        logging.info(f"Updated profile for {phone_number}: {updated_profile}")

# --- 3. The Brain (System Instructions) ---
def get_system_prompt(user_profile):
    return f"""
    You are an advanced AI Medical Assistant.
    
    CONTEXT ABOUT USER:
    The user's medical profile is: "{user_profile}".
    Use this profile to personalize your advice (e.g., if diabetic, warn about sugar).

    YOUR TASKS:
    1. **Language Detection**: Automatically detect the language of the user's message/image caption.
    2. **Respond in the SAME Language**: If they ask in Hindi, answer in Hindi.
    3. **Profile Extraction**: If the user provides new medical info (e.g., "I have high BP", "I am 25"), 
       add a specific tag at the end of your response like this: [[UPDATE_PROFILE: <summary of new info>]].
    4. **Structure**: format your medical advice strictly as follows:
       - 🩺 **Analysis**: What do you think is happening?
       - 💊 **Remedy/Advice**: Immediate steps or home remedies.
       - ⚠️ **Precaution**: Specific warnings (check for interactions if they mentioned medicines).
       - 🏥 **When to see a Doctor**: Red flag symptoms.
    
    SAFETY PROTOCOL:
    - If the user implies suicide, chest pain, or unconsciousness, start with "🚨 EMERGENCY" and tell them to call a hospital.
    - Always end with: "Disclaimer: I am an AI. Consult a doctor for medical decisions."
    """

def get_gemini_response(text_input, image_data, mime_type, current_profile):
    try:
        
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash-lite',
            system_instruction=get_system_prompt(current_profile)
        )
        
        content = []
        if text_input:
            content.append(text_input)
        if image_data:
            content.append({"mime_type": mime_type, "data": image_data})

        # Generate response
        response = model.generate_content(content)
        return response.text
    except Exception as e:
        logging.error(f"Gemini API Error: {e}")
        return "⚠️ Service unavailable temporarily. Please try again."

# --- 4. The Route ---
@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').strip()
    media_url = request.values.get('MediaUrl0')
    sender_phone = request.values.get('From')

    resp = MessagingResponse()
    msg = resp.message()

    try:
        # A. Fetch User Profile from Firebase
        current_profile = get_user_profile(sender_phone)
        logging.info(f"User Profile for {sender_phone}: {current_profile}")

        # B. Handle Image Download
        image_data = None
        mime_type = None
        
        if media_url:
            # Twilio requires auth to download media
            try:
                media_req = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
                if media_req.status_code == 200:
                    mime_type = media_req.headers.get('Content-Type')
                    image_data = media_req.content
                    if not incoming_msg:
                        incoming_msg = "Please analyze this medical image."
                else:
                    logging.error(f"Failed to download image: {media_req.status_code}")
                    msg.body("❌ Failed to download image. Please try again.")
                    return str(resp)
            except Exception as e:
                 logging.error(f"Error downloading image: {e}")
                 msg.body("❌ Error processing image.")
                 return str(resp)

        # C. Get AI Response
        ai_reply = get_gemini_response(incoming_msg, image_data, mime_type, current_profile)

        # D. Check for Profile Updates (Smart Memory)
        # We look for the tag [[UPDATE_PROFILE: ...]] generated by the AI
        if "[[UPDATE_PROFILE:" in ai_reply:
            try:
                # Extract the new info
                start = ai_reply.find("[[UPDATE_PROFILE:") + 17
                end = ai_reply.find("]]", start)
                if end != -1:
                    new_info = ai_reply[start:end].strip()
                    
                    # Update Firebase
                    update_user_profile(sender_phone, new_info)
                    
                    # Clean the tag from the user's message
                    ai_reply = ai_reply.replace(f"[[UPDATE_PROFILE: {new_info}]]", "")
                    ai_reply = ai_reply.replace("[[UPDATE_PROFILE:", "") # Cleanup remnants
            except Exception as e:
                logging.error(f"Profile update extraction failed: {e}")

        msg.body(ai_reply)

    except Exception as e:
        logging.error(f"Critical Application Error: {e}")
        msg.body("Sorry, I'm having trouble connecting right now.")

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)