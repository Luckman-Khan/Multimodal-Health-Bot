import os
import requests
import google.generativeai as genai
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from langdetect import detect

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


@app.route("/whatsapp", methods=['POST'])
# Make sure you have this import at the top of your file
<<<<<<< HEAD

=======
>>>>>>> 8be0a16e205b80f15c26d04750a31b122acf58b4

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '') # Get the message text/caption
    media_url = request.values.get('MediaUrl0')

    resp = MessagingResponse()
    msg = resp.message()

    # --- NEW: Detect language at the beginning ---
    # We detect the language from the text, whether it's a caption or a standalone message.
    try:
        # We use the original incoming_msg before converting to lower() for better detection
        lang = detect(incoming_msg) if incoming_msg else 'en'
    except:
        lang = 'en' # Default to English if detection fails or message is empty

    try:
        # --- Image (Multimodal) Logic ---
        if media_url:
            # Prompts for image analysis in different languages
            prompts_image = {
                'en': """
                You are a helpful AI health assistant. Analyze this image.
                IMPORTANT: Start your response in English with this exact disclaimer in bold: '*I am an AI assistant, not a doctor. Please consult a healthcare professional for medical advice.*'
                Describe what you see in simple terms. DO NOT give a diagnosis.
                """,
                'hi': """
                आप एक सहायक एआई स्वास्थ्य सहायक हैं। इस छवि का विश्लेषण करें।
                महत्वपूर्ण: अपनी प्रतिक्रिया हिंदी में इस सटीक अस्वीकरण के साथ बोल्ड में शुरू करें: '*मैं एक एआई सहायक हूं, डॉक्टर नहीं। कृपया चिकित्सीय सलाह के लिए एक स्वास्थ्य देखभाल पेशेवर से परामर्श लें।*'
                सरल शब्दों में बताएं कि आप क्या देखते हैं। निदान न करें।
                """,
                'bn': """
                আপনি একজন সহায়ক এআই স্বাস্থ্য সহকারী। এই ছবিটি বিশ্লেষণ করুন।
                গুরুত্বপূর্ণ: আপনার প্রতিক্রিয়াটি বাংলাতে এই সুনির্দিষ্ট দাবিত্যাগের সাথে বোল্ডে শুরু করুন: '*আমি একজন এআই সহকারী, ডাক্তার নই। অনুগ্রহ করে চিকিৎসার জন্য একজন স্বাস্থ্য специалиста সাথে পরামর্শ করুন।*'
                আপনি যা দেখছেন তা সহজ ভাষায় বর্ণনা করুন। রোগ নির্ণয় করবেন না।
                """,
                'or': """
                ଆପଣ ଜଣେ ସହାୟକ ଏଆଇ ସ୍ୱାସ୍ଥ୍ୟ ସହାୟକ ଅଟନ୍ତି। ଏହି ଛବିକୁ ବିଶ୍ଳେଷଣ କରନ୍ତୁ।
                ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ: ଆପଣଙ୍କର ପ୍ରତିକ୍ରିୟାକୁ ଓଡ଼ିଆରେ ଏହି ସଠିକ୍ ଡିସକ୍ଲେମର୍ ସହିତ ବୋଲ୍ଡରେ ଆରମ୍ଭ କରନ୍ତୁ: '*ମୁଁ ଜଣେ ଏଆଇ ସହାୟକ, ଡାକ୍ତର ନୁହେଁ। ଦୟାକରି ଡାକ୍ତରୀ ପରାମର୍ଶ ପାଇଁ ଜଣେ ସ୍ୱାସ୍ଥ୍ୟ ବିଶେଷଜ୍ଞଙ୍କ ସହିତ ପରାମର୍ଶ କରନ୍ତୁ।*'
                ଆପଣ ଯାହା ଦେଖୁଛନ୍ତି ତାହାକୁ ସରଳ ଭାଷାରେ ବର୍ଣ୍ଣନା କରନ୍ତୁ। ରୋଗ ନିର୍ଣ୍ଣୟ କରନ୍ତୁ ନାହିଁ।
                """
            }
            # Select the correct prompt, defaulting to English
            prompt = prompts_image.get(lang, prompts_image['en'])
            
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            image_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            mime_type = image_response.headers.get('Content-Type')
            
            if mime_type and mime_type.startswith('image/'):
                image_data = image_response.content
                image_parts = [{"mime_type": mime_type, "data": image_data}]
                response = model.generate_content([prompt, image_parts[0]], stream=False)
                response.resolve()
                msg.body(response.text)
            else:
                msg.body("Sorry, I could not process the image file.")

        # --- Text Logic ---
        else:
            # Prompts for text analysis (as defined before)
            # Prompts for text analysis
            prompts_text = {
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
                কেবল নিম্নলিখিত जानकारी के आधार पर उपयोगकर्ता के प्रश्न का उत्तर हिंदी में दें:
                ---
                {knowledge_base}
                ---
                उपयोगकर्ता का प्रश्न: "{incoming_msg}"
                यदि प्रश्न जानकारी में नहीं है, तो हिंदी में कहें: 'मैं केवल अपने ज्ञानकोष में मौजूद विषयों के बारे में ही प्रश्नों का उत्तर दे सकता हूं।'
                """,
                'bn': f"""
                কেবলমাত্র নিম্নলিখিত তথ্যের উপর ভিত্তি করে ব্যবহারকারীর প্রশ্নের উত্তর বাংলাতে দিন:
                ---
                {knowledge_base}
                ---
                ব্যবহারকারীর প্রশ্ন: "{incoming_msg}"
                যদি প্রশ্নটি তথ্যের মধ্যে না থাকে, তাহলে বাংলাতে বলুন: 'আমি শুধুমাত্র আমার জ্ঞানভান্ডারে থাকা বিষয়গুলি সম্পর্কে প্রশ্নের উত্তর দিতে পারি।'
                """,
                'or': f"""
                କେବଳ ନିମ୍ନଲିଖିତ ସୂଚନା ଉପରେ ଆଧାର କରି ବ୍ୟବହାରକାରୀଙ୍କ ପ୍ରଶ୍ନର ଉତ୍ତର ଓଡ଼ିଆରେ ଦିଅନ୍ତୁ:
                ---
                {knowledge_base}
                ---
                ବ୍ୟବହାରକାରୀଙ୍କ ପ୍ରଶ୍ନ: "{incoming_msg}"
                ଯଦି ପ୍ରଶ୍ନଟି ସୂଚନାରେ ନାହିଁ, ତେବେ ଓଡ଼ିଆରେ କୁହନ୍ତୁ: 'ମୁଁ କେବଳ ମୋର ଜ୍ଞାନକୋଷରେ ଥିବା ବିଷୟଗୁଡ଼ିକ ଉପରେ ହିଁ ପ୍ରଶ୍ନର ଉତ୍ତର ଦେଇପାରିବି।'
                """
            }
            
            # Select the correct prompt, defaulting to English
            prompt = prompts_text.get(lang, prompts_text['en'])
            
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            response = model.generate_content(prompt)
            msg.body(response.text)

    except Exception as e:
        print(f"An error occurred: {e}")
        msg.body("Sorry, I encountered an error. Please try again later.")

    return str(resp)

if __name__ == "__main__":

    app.run(port=5000, debug=True)

