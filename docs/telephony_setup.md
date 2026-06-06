# Production Telephony Setup Guide

This guide provides instructions to connect the Siddhant AI Persona Platform to a live public phone line using Twilio, Vapi, and FastAPI.

---

## Architecture Flow

```
   [Recruiter Inbound Call]
             ↓
        [Twilio Number]
             ↓ (Webhook Forward)
        [Vapi Assistant]
             ↓ (Custom LLM Endpoint)
     [FastAPI backend/ngrok]
             ↓
     [VoiceQueryRouter]
             ↓
[QA Engine / Booking Agent]
```

---

## Part 1: Twilio Setup

1. **Create a Twilio Account**:
   - Go to [Twilio Console](https://www.twilio.com/console) and sign up for a trial or paid account.
2. **Purchase a Twilio Phone Number**:
   - Navigate to **Develop** $\rightarrow$ **Phone Numbers** $\rightarrow$ **Manage** $\rightarrow$ **Buy a number**.
   - Search for a number with voice capabilities and purchase it.
3. **Configure Incoming Voice Webhook**:
   - After setting up the Vapi assistant (see Part 2), configure the Twilio phone number's **Incoming Voice Webhook** to forward calls to Vapi's webhook URL:
     ```text
     https://api.vapi.ai/webhook/twilio
     ```
   - Set the HTTP method to `POST`.

---

## Part 2: Vapi Assistant Setup

1. **Create a Vapi Account**:
   - Sign up at the [Vapi Dashboard](https://dashboard.vapi.ai/).
2. **Create a New Assistant**:
   - Click **Create Assistant** $\rightarrow$ select **Blank Assistant**.
   - Name it `"Siddhant AI Representative"`.
3. **Configure Settings**:
   - **Greeting**: 
     ```text
     Hello, this is Siddhant's AI representative. I can answer questions about Siddhant's projects, technical experience, and interview availability. How can I help you today?
     ```
   - **Model**:
     - Provider: **Custom LLM**
     - URL: `https://<your-subdomain>.ngrok-free.app/api/v1/voice/query` (the public URL to your FastAPI `/query` endpoint).
     - Model: `google/gemma-4-31b-it:free` (or any configured model in your `.env`).
   - **Voice**:
     - Select a provider (e.g., Vapi, ElevenLabs, PlayHT) and choose a voice (e.g., Jennifer, Azure Guy).
   - **Server URL**:
     - Enter your public webhook URL: `https://<your-subdomain>.ngrok-free.app/api/v1/voice/webhook`
4. **Connect Twilio to Vapi**:
   - Go to **Phone Numbers** in Vapi.
   - Click **Import** $\rightarrow$ enter your Twilio SID and Auth Token to bind your Twilio number directly to Vapi.

---

## Part 3: FastAPI Webhook & Port Tunneling

1. **Start ngrok Tunnel**:
   - Vapi needs a public HTTPS URL to reach your local FastAPI server:
     ```bash
     ngrok http 8000
     ```
   - Copy the generated HTTPS URL (e.g., `https://abcdef.ngrok-free.app`).
2. **Set Webhook URLs in Vapi**:
   - Update Vapi's assistant Custom LLM URL to: `https://abcdef.ngrok-free.app/api/v1/voice/query`
   - Update Vapi's Server Webhook URL to: `https://abcdef.ngrok-free.app/api/v1/voice/webhook`
3. **Run your local server**:
   - Make sure your FastAPI backend is running:
     ```bash
     $env:PYTHONPATH="."
     .venv\Scripts\python.exe app/main.py
     ```

---

## Part 4: Environment Variables

Configure the following variables in the `.env` file for live production integration:

```env
# Backend Vapi Webhook Server Settings
HOST=127.0.0.1
PORT=8000
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemma-4-31b-it:free

# Frontend Public Keys (For Web Client Integration)
NEXT_PUBLIC_API_URL=https://abcdef.ngrok-free.app
NEXT_PUBLIC_VAPI_PUBLIC_KEY=your_vapi_public_key_from_dashboard
NEXT_PUBLIC_VAPI_ASSISTANT_ID=your_vapi_assistant_id_from_dashboard
NEXT_PUBLIC_REPRESENTATIVE_PHONE=+16098582026
```
