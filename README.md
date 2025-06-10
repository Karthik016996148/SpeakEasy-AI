# SpeakEasy AI 🗣️

Hey there! I built this conversational voice AI agent that lets people call a phone number and have natural conversations with an AI assistant. It's powered by OpenAI GPT-4o-mini, Twilio, and deployed on Google Cloud Platform. The coolest part? It remembers the entire conversation context and automatically saves complete transcripts!

## 🎯 What I Built

- **Natural Conversations**: Real-time back-and-forth voice conversations that feel human
- **Context Awareness**: The AI remembers everything said during the call
- **Smart Call Ending**: Automatically ends when users say "bye" or after 15 seconds of silence
- **Complete Transcripts**: Saves full conversation transcripts to Google Cloud Storage
- **Scalable**: Deployed on Google Cloud Run with auto-scaling (because I wanted it to handle traffic spikes)

## 📋 What You'll Need

I used these services and tools to build SpeakEasy AI:

- Google Cloud Platform account
- Twilio account with phone number
- OpenAI API key
- Python 3.11+
- gcloud CLI installed

## 🚀 How I Set It Up (And How You Can Too!)

### 1. Get the Code
```bash
git clone <your-repo> # or download my files
cd voice-agent
```

### 2. Grab Your API Keys

#### OpenAI API Key
I got mine from [OpenAI Platform](https://platform.openai.com) - just create an account, make an API key, and copy it (starts with `sk-proj-`)

#### Twilio Setup
Head to [Twilio Console](https://console.twilio.com) and grab:
- Account SID and Auth Token from the dashboard
- Buy a phone number (Phone Numbers → Manage → Buy a number)

#### Google Cloud Setup
I created a GCP project at [Cloud Console](https://console.cloud.google.com), enabled these APIs:
- Cloud Run
- Cloud Build 
- Cloud Storage

Then installed gcloud CLI and authenticated:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 3. Configure Your Setup

I made it super easy - just edit `quick_deploy.sh` with your details:
```bash
# Your project details
PROJECT_ID="your-project-id"
REGION="us-west2"
BUCKET_NAME="your-bucket-name"

# Your credentials
OPENAI_API_KEY="sk-proj-your-key..."
TWILIO_ACCOUNT_SID="ACxxxxx"
TWILIO_AUTH_TOKEN="your-token"
```

### 4. One-Click Deploy

I wrote a script that does everything for you:

```bash
chmod +x quick_deploy.sh
./quick_deploy.sh
```

This will:
- Create your GCS bucket
- Build and deploy to Cloud Run
- Set all environment variables
- Show you your service URL

### 5. Connect Twilio

Last step! Go to [Twilio Console](https://console.twilio.com) → Phone Numbers, click your number, and set:

**Voice Configuration:**
- **Webhook URL**: `https://your-service-url.run.app/twilio/webhook`
- **HTTP Method**: `POST`

**Call Status Changes:**
- **Status Callback URL**: `https://your-service-url.run.app/twilio/call_status`
- **HTTP Method**: `POST`

Save it and you're live!

## 🎮 How It Works

### The User Experience I Created
1. Someone calls your Twilio number
2. They hear: "Hi, How can I help you today?"
3. Natural conversation happens
4. They say "bye" or go silent for 15 seconds to end
5. Complete transcript gets saved automatically

### Example Conversation Flow
```
📞 User calls
🤖 "Hi, How can I help you today?"
👤 "Tell me about San Francisco"
🤖 "San Francisco is a beautiful city on the California coast..."
👤 "What's the weather like there?"
🤖 "San Francisco has a Mediterranean climate with cool summers..."
👤 "Thanks, that's helpful. Bye!"
🤖 "Thanks for calling! Have a great day!"
📁 Full conversation saved to cloud storage
```

### Where I Store Conversations

Everything gets saved to Google Cloud Storage in this format:
```
gs://your-bucket-name/conversations/
├── CA123456789.json
├── CA987654321.json
└── ...
```

Each file contains the complete conversation:
```json
{
  "call_sid": "CA123456789",
  "start_time": "2025-06-08T09:15:00Z",
  "end_time": "2025-06-08T09:20:00Z",
  "exchanges": [
    {"user": "Tell me about SF", "ai": "San Francisco is a beautiful city..."},
    {"user": "What about weather?", "ai": "San Francisco has a Mediterranean..."}
  ],
  "full_transcript": "User: Tell me about SF\nAI: San Francisco is a beautiful city...",
  "status": "completed"
}
```

## 📁 How I Organized The Code

```
voice-agent/
├── main.py              # FastAPI app (the heart of it all)
├── requirements.txt     # Python dependencies I used
├── Dockerfile          # Container setup
├── cloudbuild.yaml     # Google Cloud Build config
├── quick_deploy.sh     # My one-click deployment script
├── .dockerignore       # Docker optimization
└── README.md           # This file you're reading!
```

## 🔧 The Technical Stuff

### My Architecture Choice
I went with:
- **FastAPI**: For handling Twilio webhooks (fast and reliable)
- **Twilio**: For voice calls and speech recognition
- **OpenAI GPT-4o-mini**: The brain behind conversations
- **Google Cloud Run**: Serverless deployment (scales automatically)
- **Google Cloud Storage**: Transcript storage (cheap and reliable)

### The API Endpoints I Built
- `POST /twilio/webhook` - Handles incoming calls
- `POST /twilio/conversation` - Manages ongoing conversations
- `POST /twilio/call_status` - Processes call completion
- `GET /conversations` - Lists stored conversations
- `GET /active_calls` - Shows active calls

### Environment Variables I Use
```bash
OPENAI_API_KEY=sk-proj-...
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=xxxxx
GCS_BUCKET=your-bucket
GOOGLE_CLOUD_PROJECT=your-project
```

## 🛠️ Maintaining SpeakEasy AI

### Need to Redeploy?
```bash
./quick_deploy.sh
```

### Want to See Logs?
```bash
gcloud logs tail --follow --filter='resource.type=cloud_run_revision AND resource.labels.service_name=voice-agent'
```

### Check What's Happening
Visit: `https://your-service-url.run.app/active_calls`

## 🔍 If Something Goes Wrong

### Issues I've Encountered

**Calls not connecting:**
- Double-check your Twilio webhook URL
- Make sure the service is actually running

**No transcripts being saved:**
- Verify the call status webhook is set up
- Check Google Cloud Storage permissions

**AI not responding:**
- Confirm your OpenAI API key works
- Check if you've hit usage limits

### Debug Tools I Built
- Health check: `https://your-service-url.run.app/`
- Active calls: `https://your-service-url.run.app/active_calls`
- Conversations: `https://your-service-url.run.app/conversations`

## 💰 What It Costs Me

Here's what I spend running this (very reasonable!):
- **Google Cloud Run**: ~$0-10/month (free tier is generous)
- **Google Cloud Storage**: ~$0-5/month
- **Twilio**: ~$1/month + $0.0085/minute for calls
- **OpenAI**: ~$0.001-0.005 per conversation

## 🎉 Why I Built This

I wanted to create something that shows how powerful voice AI can be when done right. SpeakEasy AI demonstrates natural conversation flow, context awareness, and automatic transcription - perfect for customer service, personal assistants, or any voice-enabled application you can imagine.

The best part? Once it's set up, it just works. People can call and have meaningful conversations that get automatically saved for later review.

*Feel free to fork, modify, and make it your own! If you build something cool with it, I'd love to hear about it.* 

---
