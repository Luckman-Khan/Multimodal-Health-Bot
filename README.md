# DocTalk: Your Multilingual AI Health Assistant

A multilingual, multimodal AI health assistant on WhatsApp, designed to provide accessible, personalized, and proactive preventive healthcare information to rural and semi-urban populations in India.

## 🚀 The Problem

Access to clear, simple, and timely healthcare information is a significant challenge in rural India. Barriers include literacy levels, language diversity, and a lack of immediate access to medical professionals for simple queries. This creates a gap where misinformation can thrive and preventive care is often overlooked.

## ✨ Our Solution

**Doc-Dost** is an intelligent WhatsApp chatbot powered by Google's Gemini Pro model and a persistent Firebase database. It bridges the information gap by acting as a personal, stateful health companion.

It allows users to:
-   Converse naturally in multiple languages (English, Hinglish, Hindi, Bengali, Odia).
-   Receive personalized, location-based health alerts.
-   Generate and save a personalized child vaccination schedule.
-   Send pictures of medicines or symptoms for analysis.
-   Provide feedback to continuously improve the service.

## 📋 Key Features

-   **Intelligent Multilingual Support**: Automatically detects and remembers a user's language for a seamless conversational experience.
-   **Multimodal Input**: Understands both text queries and images, allowing users to **show** what's wrong, not just describe it.
-   **Personalized Health Alerts**: Users can set their district to receive simulated real-time alerts about local disease outbreaks.
-   **Interactive Vaccination Scheduler**: A conversational, multi-step feature that:
    -   Asks for a child's date of birth.
    -   Generates a complete, personalized vaccination schedule with exact due dates.
    -   Saves the schedule to the user's profile for future reminders.
-   **Stateful Memory**: Utilizes a Firebase database to remember user preferences (language, district) and conversational context (like waiting for a date of birth), making interactions feel natural and intelligent.
-   **User Feedback Loop**: A `feedback` command allows users to submit their suggestions, which are saved directly to the database for future analysis and improvement.
-   **Robust Error Handling**: The bot is designed to be resilient, providing helpful guidance to the user even if an input is incorrect or an API fails.

## 🛠️ Tech Stack

-   **AI Model**: Google Gemini 1.5 Flash
-   **Backend**: Python (Flask)
-   **Database**: Google Firebase Firestore
-   **Messaging Platform**: Twilio WhatsApp API
-   **Deployment**: Render (for automated CI/CD)
-   **Version Control**: Git & GitHub

## ⚙️ How to Use the Bot

-   **Ask a health question**: `ডেঙ্গু জ্বরের লক্ষণ কি?`
-   **Set your location**: `set district Kolkata`
-   **Get a local alert**: `alert`
-   **Get a vaccine schedule**: Send `schedule`, then reply with the date of birth when prompted.
-   **Send an image**: Attach a photo of a medicine strip or symptom.
-   **Give feedback**: `feedback This bot is very helpful.`

## 🔮 Future Scope

-   **Real-Time Outbreak Integration**: Replace the demo `outbreaks.json` file with a live API feed from India's Integrated Disease Surveillance Programme (IDSP).
-   **Automated Vaccination Reminders**: Implement a daily scheduler (Cron Job) to scan the database and send proactive WhatsApp reminders one week before a vaccine is due.
-   **Voice Note Support**: Add a Speech-to-Text API to allow users to ask questions using voice notes, further breaking down literacy barriers.

## 🔧 How to Set Up Locally

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Luckman-Khan/Multimodal-Health-Bot.git](https://github.com/Luckman-Khan/Multimodal-Health-Bot.git)
    cd Multimodal-Health-Bot
    ```
2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up Firebase:**
    -   Create a Firebase project and a Firestore database.
    -   Download your private key file and save it as `serviceAccountKey.json` in the project root.
5.  **Set up environment variables:**
    -   Create a `.env` file by copying the `env.example`.
    -   Add your `GEMINI_API_KEY`, `TWILIO_ACCOUNT_SID`, and `TWILIO_AUTH_TOKEN`.
6.  **Run the application:**
    ```bash
    python app.py
    ```
