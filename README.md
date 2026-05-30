# AI Google Meet Assistant

AI Google Meet Assistant is a FastAPI web application that helps users manage Google Meet meetings from a clean browser portal. It connects to Google with OAuth 2.0, creates Google Calendar events with Meet links, and supports scheduling, listing, cancelling, and rescheduling meetings. The assistant also accepts natural-language prompts such as "Schedule a meeting with Ram on Monday at 3 PM" and turns them into real Calendar actions.

## Tech Stack

- **Backend:** FastAPI, Uvicorn, Pydantic
- **Frontend:** HTML, CSS, JavaScript
- **Google APIs:** Google OAuth 2.0, Google Calendar API, Google Meet conference data
- **AI/NLP:** Groq API with a local rule-based fallback parser
- **Environment:** Python, python-dotenv

## Features

- Google OAuth login and logout
- Persistent local token cache for development
- Schedule Google Calendar meetings with Google Meet links
- List upcoming meetings
- Cancel meetings by event ID or meeting search text
- Reschedule meetings by event ID or search text
- Natural-language assistant for schedule, list, cancel, and reschedule prompts
- Voice input with a microphone icon that automatically runs the assistant after speech recognition
- Professional dashboard UI with toast notifications and clean activity cards

## Setup

1. Clone the repository.

```bash
git clone https://github.com/rbbhadiyar/AI-Google-Meet-Assistant.git
cd AI-Google-Meet-Assistant
```

2. Create and activate a virtual environment.

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Create a Google Cloud project and enable **Google Calendar API**.

5. Create OAuth 2.0 credentials for a **Web application**.

6. Add this Authorized redirect URI in Google Cloud Console.

```text
http://localhost:8000/auth/callback
```

7. Copy `.env.example` to `.env` and fill in your credentials.

```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GROQ_API_KEY=your-groq-api-key
BASE_URL=http://localhost:8000
```

`GROQ_API_KEY` is optional. If it is missing or unavailable, the app uses the local fallback parser for common meeting commands.

8. Start the app.

```bash
python main.py
```

9. Open the portal.

```text
http://localhost:8000
```

## Usage

Click **Connect Google** and complete the OAuth flow. After authentication, use the assistant prompt, the microphone icon, or the manual tabs to manage meetings. When you use voice input, speak the meeting command and the assistant runs it automatically after the transcript is captured.

Example prompts:

- `Schedule a meeting with Ram on Monday at 3 PM`
- `What meetings do I have tomorrow?`
- `Cancel my meeting with John`
- `Move my meeting with Ram to Friday at 4 PM`

## Important Notes

- `.env` and `.tokens.json` are ignored by Git because they contain secrets.
- `guide.txt` is also ignored by Git and is meant for local learning/reference only.
- If Google Calendar API was enabled recently, wait a few minutes before retrying Calendar actions.
- If the OAuth app is in Testing mode, add your Gmail account as a test user in the Google Cloud OAuth consent screen.

## Screenshots

### Assistant Dashboard

The main portal provides Google connection status, natural-language and voice assistant controls, meeting management tools, and a clean activity area.

![AI Google Meet Assistant dashboard](Assets/Screenshot%202026-05-30%20161300.png)

### Meeting Activity

The activity area shows scheduling, rescheduling, cancellation, and error states as readable cards instead of raw API responses.

![AI Google Meet Assistant activity view](Assets/Screenshot%202026-05-30%20174511.png)

## Video

The video should show Google login, scheduling a Meet using natural language, listing meetings, rescheduling, cancelling, and logout.


https://github.com/user-attachments/assets/243ee094-59ec-417f-b98a-cb630c57d067




