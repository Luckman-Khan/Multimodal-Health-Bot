# Multimodal-Health-Bot

A multilingual, multimodal AI health assistant on WhatsApp, designed to provide accessible preventive healthcare information to rural and semi-urban populations in India.

## 🚀 The Problem

Access to clear, simple, and timely healthcare information is a significant challenge in rural India. Barriers include literacy levels, language diversity, and a lack of immediate access to medical professionals for simple queries.

## ✨ Our Solution

**Multimodal-Health-Bot** is a WhatsApp chatbot powered by Google's Gemini Pro model. It bridges the information gap by allowing users to:
- Ask health questions in their native language.
- Get information on disease symptoms and preventive care.
- Send pictures (e.g., of a skin rash, medicine strip) for preliminary, non-diagnostic information.

## 🛠️ Tech Stack

- **AI Model:** Google Gemini Pro & Gemini Pro Vision
- **Backend:** Python (Flask)
- **Messaging Platform:** Twilio WhatsApp API
- **Deployment:** Render

## 📋 Features

- **Multilingual Support:** Understands and responds in multiple Indian languages.
- **Text-Based Queries:** Ask questions about symptoms, vaccines, and first aid.
- **Image Analysis (Multimodal):** Send a photo to get information about medicines or physical symptoms (with clear disclaimers).
- **Real-time & Accessible:** Available 24/7 on WhatsApp, a platform with deep penetration in India.

## ⚙️ How to Set Up Locally

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
    cd your-repo-name
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
4.  **Set up environment variables:**
    -   Create a `.env` file by copying the `env.example`.
    -   Add your `GEMINI_API_KEY` to the `.env` file.
    -   Add your `TWILIO_ACCOUNT_SID` to the `.env` file.
    -   Add your `TWILIO_AUTH_TOKEN` to the `.env` file.

5.  **Run the application:**
    ```bash
    flask run
    ```
