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
    outbreak_data = {"outbreaks": []}

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
    'hi': {
        'set_district_success': "धन्यवाद! आपका जिला {district_name} पर सेट कर दिया गया है।",
        'no_district_for_alert': "कृपया पहले अपना जिला सेट करें। भेजें: `set district [आपके जिले का नाम]`",
        'no_alert_found': "आपके पंजीकृत जिले {district_name} के लिए कोई नया स्वास्थ्य अलर्ट नहीं है।",
        'update_district_prompt': "अपना स्थान सेट या अपडेट करने के लिए, कृपया इस प्रारूप में एक संदेश भेजें:\n\n`set district [आपके जिले का नाम]`\n\nउदाहरण के लिए: `set district Murshidabad`",
        'provide_district_name': "कृपया एक जिले का नाम प्रदान करें। उदाहरण: `set district Murshidabad`",
        'db_connection_error': "डेटाबेस कनेक्शन उपलब्ध नहीं है।",
        'feedback_success': "आपकी प्रतिक्रिया के लिए धन्यवाद! यह हमें बेहतर बनाने में मदद करता है।",
        'feedback_prompt': "'फीडबैक' शब्द के बाद कृपया अपनी प्रतिक्रिया प्रदान करें।",
        'error_message': "क्षमा करें, मुझे एक त्रुटि का सामना करना पड़ा। कृपया बाद में पुन: प्रयास करें।",
        'image_error': "क्षमा करें, मैं छवि फ़ाइल को संसाधित नहीं कर सका।"
    },
    'bn': {
        'set_district_success': "ধন্যবাদ! আপনার জেলা {district_name} হিসাবে সেট করা হয়েছে।",
        'no_district_for_alert': "স্থানীয় স্বাস্থ্য সতর্কতা পেতে অনুগ্রহ করে প্রথমে আপনার জেলা সেট করুন। পাঠান: `set district [আপনার জেলার নাম]`",
        'no_alert_found': "আপনার নিবন্ধিত জেলা {district_name} এর জন্য কোন নতুন স্বাস্থ্য সতর্কতা নেই।",
        'update_district_prompt': "আপনার অবস্থান সেট বা আপডেট করতে, অনুগ্রহ করে এই বিন্যাসে একটি বার্তা পাঠান:\n\n`set district [আপনার জেলার নাম]`\n\nউদাহরণস্বরূপ: `set district Murshidabad`",
        'provide_district_name': "অনুগ্রহ করে একটি জেলার নাম দিন। উদাহরণ: `set district Murshidabad`",
        'db_connection_error': "ডাটাবেস সংযোগ উপলব্ধ নেই।",
        'feedback_success': "আপনার মতামতের জন্য ধন্যবাদ! এটি আমাদের উন্নতি করতে সাহায্য করে।",
        'feedback_prompt': "অনুগ্রহ করে 'ফিডব্যাক' শব্দের পরে আপনার মতামত দিন।",
        'error_message': "দুঃখিত, একটি ত্রুটি ঘটেছে। অনুগ্রহ করে পরে আবার চেষ্টা করুন।",
        'image_error': "দুঃখিত, আমি ছবির ফাইলটি প্রক্রিয়া করতে পারিনি।"
    },
    'or': {
        'set_district_success': "ଧନ୍ୟବାଦ! ଆପଣଙ୍କ ଜିଲ୍ଲା {district_name} କୁ ସେଟ୍ କରାଯାଇଛି।",
        'no_district_for_alert': "ସ୍ଥାନୀୟ ସ୍ୱାସ୍ଥ୍ୟ ସତର୍କତା ପାଇବାକୁ ଦୟାକରି ପ୍ରଥମେ ଆପଣଙ୍କର ଜିଲ୍ଲା ସେଟ୍ କରନ୍ତୁ। ପଠାନ୍ତୁ: `set district [ଆପଣଙ୍କ ଜିଲ୍ଲା ନାମ]`",
        'no_alert_found': "ଆପଣଙ୍କର ପଞ୍ଜୀକୃତ ଜିଲ୍ଲା {district_name} ପାଇଁ କୌଣସି ନୂତନ ସ୍ୱାସ୍ଥ୍ୟ ସତର୍କତା ନାହିଁ।",
        'update_district_prompt': "ଆପଣଙ୍କ ସ୍ଥାନ ସେଟ୍ କିମ୍ବା ଅପଡେଟ୍ କରିବାକୁ, ଦୟାକରି ଏହି ଫର୍ମାଟରେ ଏକ ବାର୍ତ୍ତା ପଠାନ୍ତୁ:\n\n`set district [ଆପଣଙ୍କ ଜିଲ୍ଲା ନାମ]`\n\nଉଦାହରଣ: `set district Murshidabad`",
        'provide_district_name': "ଦୟାକରି ଏକ ଜିଲ୍ଲା ନାମ ପ୍ରଦାନ କରନ୍ତୁ। ଉଦାହରଣ: `set district Murshidabad`",
        'db_connection_error': "ଡାଟାବେସ୍ ସଂଯୋଗ ଉପଲବ୍ଧ ନାହିଁ।",
        'feedback_success': "ଆପଣଙ୍କ ମତାମତ ପାଇଁ ଧନ୍ୟବାଦ! ଏହା ଆମକୁ ଉନ୍ନତ କରିବାରେ ସାହାଯ୍ୟ କରେ।",
        'feedback_prompt': "ଦୟାକରି 'ଫିଡବ୍ୟାକ୍' ଶବ୍ଦ ପରେ ଆପଣଙ୍କର ମତାମତ ଦିଅନ୍ତୁ।",
        'error_message': "କ୍ଷମା କରନ୍ତୁ, ଏକ ତ୍ରୁଟି ଦେଖାଗଲା। ଦୟାକରି ପରେ ପୁଣି ଚେଷ୍ଟା କରନ୍ତୁ।",
        'image_error': "କ୍ଷମା କରନ୍ତୁ, ମୁଁ ଇମେଜ୍ ଫାଇଲ୍ ପ୍ରକ୍ରିୟାକରଣ କରିପାରିଲି ନାହିଁ।"
    }
}

# --- Universal Prompts ---
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
- If you do not have reliable information on any point, you MUST state "Information not available in my knowledge base" in {language_name}. Do not invent details.
"""

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    user_phone_number = request.values.get('From') 

    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    try:
        # --- Language Handling with Memory ---
        stored_lang = 'en' # Default language
        user_doc_ref = None
        user_doc = None
        if db:
            user_doc_ref = db.collection('users').document(user_phone_number)
            user_doc = user_doc_ref.get()
            if user_doc.exists:
                stored_lang = user_doc.to_dict().get('language', 'en')

        # Identify if the message is a command
        is_command = any(keyword in clean_msg for keyword in ['alert', 'district', 'feedback'])

        # Detect and update language only if it's NOT a command and the message is not empty
        if not is_command and incoming_msg:
            try:
                current_lang = detect(incoming_msg)
                if db and current_lang != stored_lang:
                    user_doc_ref.set({'language': current_lang}, merge=True)
                    stored_lang = current_lang
            except LangDetectException:
                # If detection fails, we just use the stored language
                pass
        
        lang_map = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'or': 'Odia'}
        language_name = lang_map.get(stored_lang, 'English')
        
        # Get the response dictionary for the user's stored language
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])

        # --- Keyword Logic ---
        if clean_msg == 'alert':
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            user_district = ""
            if user_doc and user_doc.exists:
                user_district = user_doc.to_dict().get('district', '').lower()
            
            if not user_district:
                 msg.body(responses['no_district_for_alert'])
                 return str(resp)

            alert_found = None
            for alert in outbreak_data.get("outbreaks", []):
                if alert['district'].lower() == user_district:
                    alert_found = alert
                    break
            
            if alert_found:
                alert_prompt = f"""
                You are a health alert system.
                Generate a concise and clear health alert message in {language_name}.
                The alert should be based on this data:
                - Disease: {alert_found['disease']}
                - Severity: {alert_found['severity']}
                - Recommendation: {alert_found['recommendation']}
                Start the message with a warning emoji (⚠️).
                """
                response = model.generate_content(alert_prompt)
                msg.body(response.text)
            else:
                msg.body(responses['no_alert_found'].format(district_name=user_district.capitalize()))
            return str(resp)
        
        elif 'update district' in clean_msg or 'change district' in clean_msg:
            msg.body(responses['update_district_prompt'])
            return str(resp)

        elif clean_msg.startswith('set district'):
            parts = incoming_msg.strip().split()
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
            feedback_text = incoming_msg.strip()[len('feedback '):]
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

        # --- AI Processing Logic ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        if media_url:
            # Image Logic
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')
            
            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
                prompt = PROMPT_IMAGE.format(language_name=language_name)
                full_prompt = [prompt, f"User's text caption: {incoming_msg}", image_parts[0]]
                response = model.generate_content(full_prompt)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body(responses['image_error'])
        else:
            # Text Logic
            prompt = PROMPT_TEXT.format(language_name=language_name, knowledge_base=knowledge_base, incoming_msg=incoming_msg)
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    return str(resp)


if __name__ == "__main__":
    app.run(port=5000, debug=True)

