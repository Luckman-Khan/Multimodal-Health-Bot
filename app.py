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
        'provide_district_name': "Incorrect format. Please provide a district name.\nExample: `set district Murshidabad`",
        'db_connection_error': "Database connection is not available.",
        'feedback_success': "Thank you for your feedback!",
        'feedback_prompt': "Incorrect format. Please provide your feedback after the word 'feedback'.\nExample: `feedback This bot is helpful.`",
        'error_message': "Sorry, I encountered an error. Please try again later.",
        'image_error': "Sorry, I could not process the image file.",
        'vaccine_prompt': "To get a personalized child vaccination schedule, please provide the date of birth in this format: DD-MM-YYYY",
        'dob_error': "Incorrect format. Please start again by sending 'schedule' or 'vaccine'.",
        'schedule_saved': "Here is the upcoming vaccination schedule for your child. I will also send you a reminder before each due date."
    },
    'hi': {
        'set_district_success': "धन्यवाद! आपका जिला {district_name} पर सेट कर दिया गया है।",
        'no_district_for_alert': "कृपया पहले अपना जिला सेट करें। भेजें: `set district [आपके जिले का नाम]`",
        'no_alert_found': "आपके पंजीकृत जिले {district_name} के लिए कोई नया स्वास्थ्य अलर्ट नहीं है।",
        'update_district_prompt': "अपना स्थान सेट या अपडेट करने के लिए, इस प्रारूप में एक संदेश भेजें:\n`set district [आपके जिले का नाम]`",
        'provide_district_name': "गलत प्रारूप। कृपया एक जिले का नाम प्रदान करें।\nउदाहरण: `set district Murshidabad`",
        'db_connection_error': "डेटाबेस कनेक्शन उपलब्ध नहीं है।",
        'feedback_success': "आपकी प्रतिक्रिया के लिए धन्यवाद!",
        'feedback_prompt': "गलत प्रारूप। 'फीडबैक' शब्द के बाद कृपया अपनी प्रतिक्रिया प्रदान करें।\nउदाहरण: `feedback यह बॉट बहुत मददगार है।`",
        'error_message': "क्षमा करें, मुझे एक त्रुटि का सामना करना पड़ा।",
        'image_error': "क्षमा करें, मैं छवि फ़ाइल को संसाधित नहीं कर सका।",
        'vaccine_prompt': "बच्चे का व्यक्तिगत टीकाकरण कार्यक्रम प्राप्त करने के लिए, कृपया इस प्रारूप में जन्म तिथि प्रदान करें: DD-MM-YYYY",
        'dob_error': "गलत प्रारूप। कृपया 'schedule' या 'vaccine' भेजकर फिर से शुरू करें।",
        'schedule_saved': "यहाँ आपके बच्चे का आगामी टीकाकरण कार्यक्रम है। मैं आपको प्रत्येक नियत तारीख से पहले एक अनुस्मारक भी भेजूंगा।"
    },
    'bn': {
        'set_district_success': "ধন্যবাদ! আপনার জেলা {district_name} হিসাবে সেট করা হয়েছে।",
        'no_district_for_alert': "অনুগ্রহ করে প্রথমে আপনার জেলা সেট করুন। পাঠান: `set district [আপনার জেলার নাম]`",
        'no_alert_found': "আপনার নিবন্ধিত জেলা {district_name} এর জন্য কোন নতুন স্বাস্থ্য সতর্কতা নেই।",
        'update_district_prompt': "আপনার অবস্থান সেট বা আপডেট করতে, এই ফর্ম্যাটে একটি বার্তা পাঠান:\n`set district [আপনার জেলার নাম]`",
        'provide_district_name': "ভুল ফর্ম্যাট। অনুগ্রহ করে একটি জেলার নাম দিন।\nউদাহরণ: `set district Murshidabad`",
        'db_connection_error': "ডাটাবেস সংযোগ উপলব্ধ নেই।",
        'feedback_success': "আপনার মতামতের জন্য ধন্যবাদ!",
        'feedback_prompt': "ভুল ফর্ম্যাট। অনুগ্রহ করে 'ফিডব্যাক' শব্দের পরে আপনার মতামত দিন।\nউদাহরণ: `feedback বটটি খুব সহায়ক।`",
        'error_message': "দুঃখিত, একটি ত্রুটি ঘটেছে।",
        'image_error': "দুঃখিত, আমি ছবির ফাইলটি প্রক্রিয়া করতে পারিনি।",
        'vaccine_prompt': "শিশুর ব্যক্তিগত টিকাদানের সময়সূচী পেতে, অনুগ্রহ করে এই ফর্ম্যাটে জন্ম তারিখ দিন: DD-MM-YYYY",
        'dob_error': "ভুল ফর্ম্যাট। অনুগ্রহ করে 'schedule' বা 'vaccine' পাঠিয়ে আবার শুরু করুন।",
        'schedule_saved': "এখানে আপনার সন্তানের আসন্ন টিকাদানের সময়সূচী দেওয়া হল। আমি প্রতিটি নির্ধারিত তারিখের আগে আপনাকে একটি অনুস্মারকও পাঠাব।"
    },
    'or': {
        'set_district_success': "ଧନ୍ୟବାଦ! ଆପଣଙ୍କ ଜିଲ୍ଲା {district_name} କୁ ସେଟ୍ କରାଯାଇଛି।",
        'no_district_for_alert': "ସ୍ଥାନୀୟ ସ୍ୱାସ୍ଥ୍ୟ ସତର୍କତା ପାଇବାକୁ ଦୟାକରି ପ୍ରଥମେ ଆପଣଙ୍କର ଜିଲ୍ଲା ସେଟ୍ କରନ୍ତୁ। ପଠାନ୍ତୁ: `set district [ଆପଣଙ୍କ ଜିଲ୍ଲା ନାମ]`",
        'no_alert_found': "ଆପଣଙ୍କର ପଞ୍ଜୀକୃତ ଜିଲ୍ଲା {district_name} ପାଇଁ କୌଣସି ନୂତନ ସ୍ୱାସ୍ଥ୍ୟ ସତର୍କତା ନାହିଁ।",
        'update_district_prompt': "ଆପଣଙ୍କ ସ୍ଥାନ ସେଟ୍ କିମ୍ବା ଅପଡେଟ୍ କରିବାକୁ, ଦୟାକରି ଏହି ଫର୍ମାଟରେ ଏକ ବାର୍ତ୍ତା ପଠାନ୍ତୁ:\n`set district [ଆପଣଙ୍କ ଜିଲ୍ଲା ନାମ]`",
        'provide_district_name': "ଭୁଲ ଫର୍ମାଟ୍। ଦୟାକରି ଏକ ଜିଲ୍ଲା ନାମ ପ୍ରଦାନ କରନ୍ତୁ।\nଉଦାହରଣ: `set district Murshidabad`",
        'db_connection_error': "ଡାଟାବେସ୍ ସଂଯୋଗ ଉପଲବ୍ଧ ନାହିଁ।",
        'feedback_success': "ଆପଣଙ୍କ ମତାମତ ପାଇଁ ଧନ୍ୟବାଦ!",
        'feedback_prompt': "ଭୁଲ ଫର୍ମାଟ୍। ଦୟାକରି 'ଫିଡବ୍ୟାକ୍' ଶବ୍ଦ ପରେ ଆପଣଙ୍କର ମତାମତ ଦିଅନ୍ତୁ।\nଉଦାହରଣ: `feedback ଏହି ବଟ୍ ବହୁତ ସାହାଯ୍ୟକାରୀ ଅଟେ।`",
        'error_message': "କ୍ଷମା କରନ୍ତୁ, ଏକ ତ୍ରୁଟି ଦେଖାଗଲା।",
        'image_error': "କ୍ଷମା କରନ୍ତୁ, ମୁଁ ଇମେଜ୍ ଫାଇଲ୍ ପ୍ରକ୍ରିୟାକରଣ କରିପାରିଲି ନାହିଁ।",
        'vaccine_prompt': "ଶିଶୁର ବ୍ୟକ୍ତିଗତ ଟୀକାକରଣ କାର୍ଯ୍ୟସୂଚୀ ପାଇବାକୁ, ଦୟାକରି ଏହି ଫର୍ମାଟରେ ଜନ୍ମ ତାରିଖ ଦିଅନ୍ତୁ: DD-MM-YYYY",
        'dob_error': "ଭୁଲ ଫର୍ମାଟ୍। ଦୟାକରି 'schedule' କିମ୍ବା 'vaccine' ପଠାଇ ପୁଣିଥରେ ଆରମ୍ଭ କରନ୍ତୁ।",
        'schedule_saved': "ଏଠାରେ ଆପଣଙ୍କ ଶିଶୁର ଆଗାମୀ ଟୀକାକରଣ କାର୍ଯ୍ୟସୂଚୀ ଅଛି। ମୁଁ ଆପଣଙ୍କୁ ପ୍ରତ୍ୟେକ ନିର୍ଦ୍ଧାରିତ ତାରିଖ ପୂର୍ବରୁ ଏକ ସ୍ମାରକ ମଧ୍ୟ ପଠାଇବି।"
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
    print("\n--- NEW REQUEST ---")
    print(f"[{datetime.now()}] HEARTBEAT: WhatsApp message received!")
    
    incoming_msg = request.values.get('Body', '')
    media_url = request.values.get('MediaUrl0')
    user_phone_number = request.values.get('From') 
    print(f"From: {user_phone_number}, Message: '{incoming_msg}'")

    resp = MessagingResponse()
    msg = resp.message()
    
    clean_msg = incoming_msg.strip().lower()

    # --- Default Language Setup ---
    stored_lang = 'en'
    
    try:
        # --- Language and State Handling with Memory ---
        print("Step 1: Checking database for user state and language...")
        user_state = None
        user_doc_ref = None
        if db:
            user_doc_ref = db.collection('users').document(user_phone_number)
            user_doc = user_doc_ref.get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                stored_lang = user_data.get('language', 'en')
                user_state = user_data.get('state')
                print(f"User found in DB. Stored Lang: {stored_lang}, State: {user_state}")
            else:
                print("New user. Using default language 'en'.")
        else:
            print("Database not connected. Using default language 'en'.")

        supported_langs = ['en', 'hi', 'bn', 'or']
        is_command = any(keyword in clean_msg for keyword in ['alert', 'district', 'feedback', 'schedule', 'vaccine'])
        print(f"Is command: {is_command}")

        if not is_command and incoming_msg and user_state is None:
            try:
                detected_lang = detect(incoming_msg)
                if detected_lang in supported_langs:
                    if db and detected_lang != stored_lang:
                        print(f"Language changed from {stored_lang} to {detected_lang}. Updating DB.")
                        user_doc_ref.set({'language': detected_lang}, merge=True)
                        stored_lang = detected_lang
                else:
                    print(f"Detected '{detected_lang}', but it's not in the whitelist. Using stored language: {stored_lang}")
            except LangDetectException:
                print("Language detection failed. Using stored language.")
                pass
        
        lang_map = {'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'or': 'Odia'}
        language_name = lang_map.get(stored_lang, 'English')
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        print(f"Final language for response: {language_name}")

        # --- State-Based Logic: Awaiting DOB ---
        if user_state == 'awaiting_dob':
            print("Step 2: Handling 'awaiting_dob' state...")
            try:
                dob = parse(incoming_msg.strip(), dayfirst=True).date()
                print(f"Successfully parsed DOB: {dob}")
                
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
                    print("Saving schedule to DB and clearing state.")
                    user_doc_ref.set({'vaccine_schedule': schedule_list, 'dob': str(dob), 'state': None}, merge=True)

                response_text = f"{responses['schedule_saved']}\n\n"
                for item in schedule_list:
                    response_text += f"*{item['due_text']}* ({item['due_date']}):\n- {item['name']}\n\n"
                msg.body(response_text)

            except Exception as e:
                print(f"DOB parsing error from state: {e}")
                if db:
                    print("Clearing 'awaiting_dob' state due to error.")
                    user_doc_ref.set({'state': None}, merge=True) 
                msg.body(responses['dob_error'])
            
            return str(resp)

        # --- Keyword Logic ---
        print("Step 2: Checking for keywords...")
        if 'schedule' in clean_msg or 'vaccine' in clean_msg:
            print("Keyword 'schedule' detected. Setting state to 'awaiting_dob'.")
            if db:
                user_doc_ref.set({'state': 'awaiting_dob'}, merge=True)
                msg.body(responses['vaccine_prompt'])
            else:
                msg.body(responses['db_connection_error'])
            return str(resp)

        elif clean_msg == 'alert':
            print("Keyword 'alert' detected.")
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            user_district = ""
            if db and user_doc and user_doc.exists:
                user_district = user_doc.to_dict().get('district', '').lower()
            
            if not user_district and db:
                 msg.body(responses['no_district_for_alert'])
            elif not db:
                 msg.body(responses['db_connection_error'])
            else:
                alert_found = None
                for alert in outbreak_data.get("outbreaks", []):
                    if alert['district'].lower() == user_district:
                        alert_found = alert
                        break
                
                if alert_found:
                    alert_prompt = f"Generate a concise health alert in {language_name} based on this data: Disease: {alert_found['disease']}, Recommendation: {alert_found['recommendation']}. Start with a warning emoji (⚠️)."
                    response = model.generate_content(alert_prompt)
                    response.resolve()
                    if response.text and response.text.strip():
                        msg.body(response.text)
                    else:
                        msg.body(responses['error_message'])
                else:
                    msg.body(responses['no_alert_found'].format(district_name=user_district.capitalize()))
            return str(resp)
        
        elif clean_msg.startswith('set district'):
            print("Keyword 'set district' detected.")
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
            print("Keyword 'feedback' detected.")
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

        # --- AI Processing Logic (if no keyword was matched) ---
        print("Step 3: No keyword matched. Proceeding to AI processing.")
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        if media_url:
            print("Image detected. Preparing for image analysis.")
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')
            
            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
                prompt = PROMPT_IMAGE.format(language_name=language_name)
                full_prompt = [prompt, f"User's text caption: {incoming_msg}", image_parts[0]]
                response = model.generate_content(full_prompt)
                response.resolve()
                if response.text and response.text.strip():
                    msg.body(response.text)
                else:
                    msg.body(responses['error_message'])
            else:
                msg.body(responses['image_error'])
        else:
            print("Text detected. Preparing for text analysis.")
            prompt = PROMPT_TEXT.format(language_name=language_name, knowledge_base=knowledge_base, incoming_msg=incoming_msg)
            print("Sending text prompt to Gemini...")
            response = model.generate_content(prompt)
            response.resolve()
            print(f"DEBUG: Raw AI Text Response: {response.text}")
            if response.text and response.text.strip():
                msg.body(response.text)
            else: 
                msg.body(responses['error_message'])

    except Exception as e:
        print(f"CRITICAL ERROR in main try block: {e}")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    # --- Final Fallback to prevent silent failures ---
    if not msg.body:
        print("FINAL FALLBACK: No response was set. Sending default error message.")
        responses = RESPONSES.get(stored_lang, RESPONSES['en'])
        msg.body(responses['error_message'])

    print("--- END REQUEST ---\n")
    return str(resp)    

if __name__ == "__main__":
    app.run(port=5000, debug=True)

