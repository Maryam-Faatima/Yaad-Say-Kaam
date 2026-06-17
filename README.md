# 🐞 Yaad Say Kaam (formerly Privacy Memory Guardian)

A privacy-first, agent-driven task reminder system that automatically ingests unread emails (or manual inputs), extracts actionable tasks without leaking personal data to the cloud, and triggers recurring alarms before deadlines.

## Features
- **Local Privacy Priority**: Sensitive task details are stored purely locally in `data/tasks.json`.
- **4-Agent Pipeline**: Extracts (Data Sentinel), Neutralizes (Memory Agent), Audits (Privacy Auditor), and Reminds (Reminder Agent).
- **Auto-Sync**: Checks Gmail every 15 seconds for new emails.
- **LadyBugs Dashboard**: Red and black stylized UI with animated alarm notifications.
- **Recurring Alarms**: Built-in 24h, 12h, 30m, 5m, 0m cascading alarms with Snooze and Dismiss capabilities.

## 🚀 Deployment Guide

Before deploying this to a cloud environment (like Streamlit Cloud, Heroku, or Render), please review these architectural constraints:

### 1. Environment Variables
You MUST set the following environment variables in your deployment platform's Secrets or Config Vars:
- `OPENAI_API_KEY`: Required for the primary OpenAI GPT-4o-mini processing.
- `GROQ_API_KEY`: Required as a fallback if OpenAI quotas are exceeded.

### 2. Gmail OAuth (credentials.json)
This project uses a desktop OAuth flow via `google-auth-oauthlib`. It looks for a `credentials.json` file in the root directory.
- **Security Warning**: `credentials.json` and `token.pickle` contain sensitive OAuth keys and tokens. **Do not commit them to GitHub**. A `.gitignore` is included to prevent this.
- **Cloud Deployment**: Serverless platforms like Streamlit Community Cloud do not support uploading standalone files securely outside of version control. If you deploy to Streamlit Cloud, you will either need to:
  1. Base64 encode the `credentials.json` into an environment variable and decode it at runtime.
  2. Use a Virtual Private Server (VPS) (e.g., DigitalOcean, AWS EC2) or a Dockerized environment (e.g., Render, Railway) where you can securely mount or inject the file.

### 3. Local JSON Storage
The app uses a local file `data/tasks.json` as a database.
- Serverless platforms often have ephemeral (temporary) file systems. This means your tasks will be wiped out whenever the container restarts.
- **Solution**: To deploy properly, you will need a platform with a persistent disk volume (like Render, Railway, or Fly.io) or swap out `task_store.py` to use a cloud database like Firebase, Supabase, or PostgreSQL.

## Local Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Setup Environment:**
   Create a `.env` file and add your API keys:
   ```env
   OPENAI_API_KEY=your_key
   GROQ_API_KEY=your_key
   ```
3. **Gmail Credentials:**
   Place your Google Workspace `credentials.json` in the root folder.
4. **Run the App:**
   ```bash
   streamlit run src/app.py
   ```
