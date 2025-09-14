import os
import google.generativeai as genai
from dotenv import load_dotenv
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# --- Configuration ---
# Load environment variables from a .env file
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check if the API key is available
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found. Please create a .env file and add your API key.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)

# Initialize Flask app
app = Flask(__name__)


def get_health_info(user_question):
    """
    Answers a user's health question based on the knowledge.txt file.
    """
    # Load the knowledge base from the file
    try:
        with open('knowledge.txt', 'r', encoding='utf-8') as f:
            knowledge_base = f.read()
    except FileNotFoundError:
        return "Error: knowledge.txt file not found in the same directory."

    # Initialize the Gemini model
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    # Create a precise prompt for the AI
    prompt = f"""
    You are a health information assistant.
    Your task is to answer the user's question based ONLY on the information provided in the knowledge base below.
    Do not use any external knowledge.
    If the answer cannot be found in the text, simply respond with: "I do not have information on that topic."

    --- KNOWLEDGE BASE ---
    {knowledge_base}
    --------------------

    User's Question: "{user_question}"
    """

    try:
        # Generate the response from the AI
        response = model.generate_content(prompt)
        response.resolve()
        
        # Return the AI's text, with a fallback for empty responses
        return response.text.strip() if response.text and response.text.strip() else "Sorry, I could not generate a response."

    except Exception as e:
        return f"An error occurred while contacting the AI service: {e}"


@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    """Handle incoming WhatsApp messages."""
    incoming_msg = request.values.get('Body', '').lower()
    resp = MessagingResponse()
    
    # Get the answer from our function
    answer = get_health_info(incoming_msg)
    
    # Send the answer back to the user
    resp.message(answer)
    
    return str(resp)


# --- Main execution block ---
if __name__ == "__main__":
    # This will run a simple development server. 
    # For a live bot, you would deploy this using a production server like Gunicorn.
    app.run(port=5000, debug=True)

