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
from datetime import datetime, timedelta
from dateutil.parser import parse

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

# Load data files
try:
    with open('knowledge.txt', 'r', encoding='utf-8') as f:
        knowledge_base = f.read()
    with open('outbreaks.json', 'r', encoding='utf-8') as f:
        outbreak_data = json.load(f)
    with open('vaccine_schedule.json', 'r', encoding='utf-8') as f:
        vaccine_data = json.load(f)
except FileNotFoundError as e:
    print(f"Error loading data file: {e}")
    knowledge_base = "No knowledge base file found."
    outbreak_data = {"outbreaks": []}
    vaccine_data = {"schedule": []}


# --- Multilingual Static Responses ---
RESPONSES = {
    'en': {
        'set_district_success': "Thank you! Your district has been set to: {district_name}",
        'no_district_for_alert': "Please set your district first. Send: `set district [Your District Name]`",
        'no_alert_found': "There are no new health alerts for your registered district: {district_name}",
        'update_district_prompt': "To set or update your location, send a message in this format:\n`set district [Your District Name]`",
        'provide_district_name': "Please provide a district name. Example: `set district Murshidabad`",
        'db_connection_error': "Database connection is not available.",
        'feedback_success': "Thank you for your feedback!",
        'feedback_prompt': "Please provide your feedback after the word 'feedback'.",
        'error_message': "Sorry, I encountered an error. Please try again later.",
        'image_error': "Sorry, I could not process the image file.",
        'vaccine_prompt': "To get a personalized child vaccination schedule, please provide the date of birth in this format:\n`schedule dob DD-MM-YYYY`",
        'dob_error': "Could not understand the date. Please use DD-MM-YYYY format, for example: `schedule dob 25-12-2024`",
        'schedule_saved': "Here is the upcoming vaccination schedule for your child. I will also send you a reminder before each due date."
    },
    'hi': {
        'set_district_success': "धन्यवाद! आपका जिला {district_name} पर सेट कर दिया गया है।",
        'no_district_for_alert': "कृपया पहले अपना जिला सेट करें। भेजें: `set district [आपके जिले का नाम]`",
        'no_alert_found': "आपके पंजीकृत जिले {district_name} के लिए कोई नया स्वास्थ्य अलर्ट नहीं है।",
        'update_district_prompt': "अपना स्थान सेट या अपडेट करने के लिए, इस प्रारूप में एक संदेश भेजें:\n`set district [आपके जिले का नाम]`",
        'provide_district_name': "कृपया एक जिले का नाम प्रदान करें। उदाहरण: `set district Murshidabad`",
        'db_connection_error': "डेटाबेस कनेक्शन उपलब्ध नहीं है।",
        'feedback_success': "आपकी प्रतिक्रिया के लिए धन्यवाद!",
        'feedback_prompt': "'फीडबैक' शब्द के बाद कृपया अपनी प्रतिक्रिया प्रदान करें।",
        'error_message': "क्षमा करें, मुझे एक त्रुटि का सामना करना पड़ा।",
        'image_error': "क्षमा करें, मैं छवि फ़ाइल को संसाधित नहीं कर सका।",
        'vaccine_prompt': "बच्चे का व्यक्तिगत टीकाकरण कार्यक्रम प्राप्त करने के लिए, कृपया इस प्रारूप में जन्म तिथि प्रदान करें:\n`schedule dob DD-MM-YYYY`",
        'dob_error': "तारीख समझ में नहीं आई। कृपया DD-MM-YYYY प्रारूप का उपयोग करें, उदाहरण के लिए: `schedule dob 25-12-2024`",
        'schedule_saved': "यहाँ आपके बच्चे का आगामी टीकाकरण कार्यक्रम है। मैं आपको प्रत्येक नियत तारीख से पहले एक अनुस्मारक भी भेजूंगा।"
    },
    'bn': {
        'set_district_success': "ধন্যবাদ! আপনার জেলা {district_name} হিসাবে সেট করা হয়েছে।",
        'no_district_for_alert': "অনুগ্রহ করে প্রথমে আপনার জেলা সেট করুন। পাঠান: `set district [আপনার জেলার নাম]`",
        'no_alert_found': "আপনার নিবন্ধিত জেলা {district_name} এর জন্য কোন নতুন স্বাস্থ্য সতর্কতা নেই।",
        'update_district_prompt': "আপনার অবস্থান সেট বা আপডেট করতে, এই ফর্ম্যাটে একটি বার্তা পাঠান:\n`set district [আপনার জেলার নাম]`",
        'provide_district_name': "অনুগ্রহ করে একটি জেলার নাম দিন। উদাহরণ: `set district Murshidabad`",
        'db_connection_error': "ডাটাবেস সংযোগ উপলব্ধ নেই।",
        'feedback_success': "আপনার মতামতের জন্য ধন্যবাদ!",
        'feedback_prompt': "অনুগ্রহ করে 'ফিডব্যাক' শব্দের পরে আপনার মতামত দিন।",
        'error_message': "দুঃখিত, একটি ত্রুটি ঘটেছে।",
        'image_error': "দুঃখিত, আমি ছবির ফাইলটি প্রক্রিয়া করতে পারিনি।",
        'vaccine_prompt': "শিশুর ব্যক্তিগত টিকাদানের সময়সূচী পেতে, অনুগ্রহ করে এই ফর্ম্যাটে জন্ম তারিখ দিন:\n`schedule dob DD-MM-YYYY`",
        'dob_error': "তারিখটি বোঝা যায়নি। অনুগ্রহ করে DD-MM-YYYY ফর্ম্যাট ব্যবহার করুন, উদাহরণস্বরূপ: `schedule dob 25-12-2024`",
        'schedule_saved': "এখানে আপনার সন্তানের আসন্ন টিকাদানের সময়সূচী দেওয়া হল। আমি প্রতিটি নির্ধারিত তারিখের আগে আপনাকে একটি অনুস্মারকও পাঠাব।"
    }
}

# --- Universal Prompts ---
PROMPT_TEXT = """
Your task is to be a helpful AI health assistant.
YOU MUST respond in the following language: {language_name}.
Base your answer ONLY on the knowledge base:
---
{knowledge_base}
---
User's question: "{incoming_msg}"
If the question is not in the knowledge base, respond in {language_name} with: 'I can only answer questions about topics in my knowledge base.'
"""

PROMPT_IMAGE = """
You are a medical information assistant.
YOU MUST respond in the following language: {language_name}.
**Response Format:**
- Start with a disclaimer in {language_name}: '*I am an AI assistant, not a doctor...*'
- Provide structured information: Medicine Name, Form, Use, etc.
- If information is not available, state that in {language_name}.
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
        stored_lang = 'en'
        user_doc_ref = None
        if db:
            user_doc_ref = db.collection('users').document(user_phone_number)
            user_doc = user_doc_ref.get()
            if user_doc.exists:
                stored_lang = user_doc.to_dict().get('language', 'en')

        is_command = any(keyword in clean_msg for keyword in ['alert', 'district', 'feedback', 'schedule', 'dob'])

        if not is_command and incoming_msg:
            try:
                current_lang = detect(incoming_msg)
                if db and current_lang != stored_lang:
                    user_doc_ref.set({'language': current_lang}, merge=True)
                    stored_lang = current_lang
            except LangDetectException:
                pass
        
        lang_map = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'or': 'Odia'}
        language_name = lang_map.get(stored_lang, 'English')
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])

        # --- Keyword Logic ---
        if 'schedule' in clean_msg or 'vaccine' in clean_msg:
            if 'dob' in clean_msg:
                # User provided DOB, calculate schedule
                try:
                    dob_str = clean_msg.split('dob')[1].strip()
                    dob = parse(dob_str, dayfirst=True).date()
                    
                    schedule_list = []
                    for item in vaccine_data['schedule']:
                        due_date = dob
                        if 'due_weeks' in item:
                            due_date += timedelta(weeks=item['due_weeks'])
                        elif 'due_months' in item:
                            due_date += timedelta(days=item['due_months'] * 30)
                        
                        schedule_list.append({
                            'name': item['name'],
                            'due_date': due_date.strftime('%d-%m-%Y'),
                            'due_text': item['due_text']
                        })

                    if db:
                        user_doc_ref.set({'vaccine_schedule': schedule_list, 'dob': str(dob)}, merge=True)

                    response_text = f"{responses['schedule_saved']}\n\n"
                    for item in schedule_list:
                        response_text += f"*{item['due_text']}* ({item['due_date']}):\n- {item['name']}\n\n"
                    msg.body(response_text)

                except Exception as e:
                    print(f"DOB parsing error: {e}")
                    msg.body(responses['dob_error'])
            else:
                msg.body(responses['vaccine_prompt'])
            return str(resp)

        elif clean_msg == 'alert':
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
                Generate a concise health alert in {language_name} based on this data:
                - Disease: {alert_found['disease']}
                - Recommendation: {alert_found['recommendation']}
                Start with a warning emoji (⚠️).
                """
                response = model.generate_content(alert_prompt)
                msg.body(response.text)
            else:
                msg.body(responses['no_alert_found'].format(district_name=user_district.capitalize()))
            return str(resp)

        # ... (rest of keyword logic: set district, feedback, etc.) ...
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
        
        # --- AI Processing Logic ---
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        if media_url:
            # Image Logic ...
        else:
            # Text Logic
            prompt = PROMPT_TEXT.format(language_name=language_name, knowledge_base=knowledge_base, incoming_msg=incoming_msg)
            response = model.generate_content(prompt)
            
            # NEW: Check for empty response from AI
            if response.text and response.text.strip():
                msg.body(response.text)
            else:
                print(f"DEBUG: Gemini returned an empty response for prompt: {prompt}")
                msg.body(responses['error_message'])

    except Exception as e:
        print(f"An error occurred: {e}")
        responses = RESPONSES.get(stored_lang, RESPONSES.get('en'))
        msg.body(responses['error_message'])

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)

