"""
Voice AI Agent - Conversational Phone Assistant
Powered by GPT-4o-mini and Twilio Speech Recognition
Supports real-time back-and-forth conversation on phone calls
"""

import os
import logging
import json
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, HTTPException
from twilio.twiml.voice_response import VoiceResponse
from openai import OpenAI
from google.cloud import storage
import aiohttp

# Initialize FastAPI
app = FastAPI()

# Configure logging
tlogging = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
BASE_URL = os.environ.get(
    "BASE_URL", "https://voice-agent-719712007728.us-west2.run.app"
)
PROJECT_ID = os.environ.get(
    "GOOGLE_CLOUD_PROJECT", "voice-ai-project-461900"
)
BUCKET_NAME = os.environ.get("GCS_BUCKET", "voice-agent-ai")

# Initialize OpenAI
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    tlogging.error("OPENAI_API_KEY environment variable is not set")
    raise RuntimeError("OPENAI_API_KEY environment variable is not set")
oai = OpenAI(api_key=openai_api_key)

# Voice AI Agent System Prompt
AGENT_SYSTEM_PROMPT = """You are a helpful voice AI assistant having a natural phone conversation. 
Be conversational and engaging - respond naturally like a human would.
Keep responses under 80 words and sound natural for speech.
Don't always ask questions - sometimes just respond and let the conversation flow naturally.
Be friendly and helpful. Avoid sounding like a Q&A session or robotic assistant."""

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
    tlogging.error("Twilio credentials are not set")
    raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")

# Initialize GCS client
storage_client = storage.Client(project=PROJECT_ID)
bucket = storage_client.bucket(BUCKET_NAME)

# Global conversation storage
conversations = {}

def add_to_conversation(call_sid: str, user_message: str, ai_response: str):
    """Add exchange to ongoing conversation in memory"""
    if call_sid not in conversations:
        conversations[call_sid] = {
            "call_sid": call_sid,
            "start_time": datetime.utcnow().isoformat(),
            "exchanges": []
        }
    
    conversations[call_sid]["exchanges"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "user": user_message,
        "ai": ai_response
    })
    
    tlogging.info(f"Added exchange to {call_sid} - total exchanges: {len(conversations[call_sid]['exchanges'])}")

def store_final_conversation(call_sid: str, audio_url: str = None):
    """Store complete conversation to GCS when call ends"""
    try:
        if call_sid not in conversations:
            tlogging.warning(f"No conversation data found for {call_sid}")
            return None
            
        conversation_data = conversations[call_sid]
        conversation_data["end_time"] = datetime.utcnow().isoformat()
        conversation_data["audio_url"] = audio_url
        conversation_data["status"] = "completed"
        
        # Create full transcript
        full_transcript = []
        for exchange in conversation_data.get("exchanges", []):
            full_transcript.append(f"User: {exchange['user']}")
            full_transcript.append(f"AI: {exchange['ai']}")
        
        conversation_data["full_transcript"] = "\n".join(full_transcript)
        
        # Save single final file
        blob = bucket.blob(f"conversations/{call_sid}.json")
        blob.upload_from_string(
            json.dumps(conversation_data, indent=2),
            content_type="application/json"
        )
        
        tlogging.info(f"✅ Stored final conversation for {call_sid} - {len(conversation_data.get('exchanges', []))} exchanges")
        
        # Clean up memory
        del conversations[call_sid]
        return conversation_data
        
    except Exception as e:
        tlogging.error(f"Error in store_final_conversation: {e}")
        return None

def store_conversation_data(call_sid: str, transcript: str, ai_response: str, audio_url: str = None):
    """Legacy function for backward compatibility"""
    add_to_conversation(call_sid, transcript, ai_response)

@app.get("/")
async def health_check():
    """Health check endpoint for GCP Load Balancer"""
    return {"status": "healthy", "service": "voice-ai-agent"}

@app.get("/conversations")
async def list_conversations():
    """List recent conversations from GCS"""
    try:
        blobs = list(bucket.list_blobs(prefix="conversations/", max_results=10))
        conversations = []
        for blob in blobs:
            conversations.append({
                "name": blob.name,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "size": blob.size
            })
        return {"conversations": conversations, "count": len(conversations)}
    except Exception as e:
        return {"error": str(e), "conversations": []}

@app.get("/active_calls")
async def active_calls():
    """Check active calls in memory"""
    return {
        "active_calls": list(conversations.keys()),
        "count": len(conversations),
        "details": {call_id: len(conv["exchanges"]) for call_id, conv in conversations.items()}
    }

@app.post("/test")
@app.get("/test")
async def test_endpoint(request: Request):
    """Test endpoint to verify Twilio connectivity"""
    tlogging.info("Test endpoint called")
    tlogging.info(f"Method: {request.method}")
    tlogging.info(f"Headers: {dict(request.headers)}")
    
    if request.method == "POST":
        try:
            form = await request.form()
            tlogging.info(f"Form data: {dict(form)}")
        except Exception as e:
            tlogging.error(f"Error reading form: {e}")
    
    return {"status": "test successful", "method": request.method}

@app.post("/twilio/webhook")
async def incoming_call(request: Request):
    """
    Initial handler: starts a conversation flow.
    """
    try:
        tlogging.info("Processing incoming call webhook")
        twiml = VoiceResponse()
        
        # For call recording, we'll store conversation data as we go
        # Full call recording can be enabled in Twilio Console
        
        # Start conversation with greeting
        twiml.say(
            "Hi, How can I help you today?",
            voice="Polly.Joanna", 
            language="en-US"
        )
        
        # Gather user input for conversation
        gather = twiml.gather(
            num_digits=0,  # No digit collection, just speech
            speech_timeout="auto",
            speech_model="experimental_conversations",
            action=f"{BASE_URL}/twilio/conversation",
            method="POST",
            input="speech"
        )
        
        # If no speech detected, give prompt
        twiml.say(
            "I'm listening. Please speak your question or request.",
            voice="Polly.Joanna",
            language="en-US"
        )
        
        twiml_str = str(twiml)
        tlogging.info(f"Initial TwiML response: {twiml_str}")
        return Response(content=twiml_str, media_type="application/xml")

    except Exception:
        tlogging.exception("Error in incoming_call")
        fallback = VoiceResponse()
        fallback.say("Sorry, an error occurred. Goodbye.", voice="Polly.Joanna", language="en-US")
        fallback.hangup()
        return Response(content=str(fallback), media_type="application/xml")

@app.post("/twilio/conversation") 
async def conversation_handler(request: Request):
    """
    Handles ongoing conversation with real-time speech processing.
    """
    try:
        tlogging.info("Processing conversation")
        form_data = {}
        
        try:
            form = await request.form()
            form_data = dict(form)
            tlogging.info(f"Conversation form data: {list(form_data.keys())}")
        except Exception as e:
            tlogging.error(f"Error parsing conversation data: {e}")
        
        # Get speech result from Twilio's speech recognition
        speech_result = form_data.get("SpeechResult", "")
        call_sid = form_data.get("CallSid", "")
        
        tlogging.info(f"User said: {speech_result}")
        
        # Check if user wants to end call
        if speech_result and speech_result.lower().strip() in ["no", "nope", "nothing", "bye", "goodbye", "that's all", "no thanks"]:
            twiml = VoiceResponse()
            twiml.say("Great! Thanks for calling. Have a wonderful day!", voice="Polly.Joanna", language="en-US")
            
            # Store final conversation
            try:
                store_final_conversation(call_sid)
                tlogging.info(f"Stored conversation after user said: {speech_result}")
            except Exception as e:
                tlogging.error(f"Error storing final conversation: {e}")
                
            twiml.hangup()
            return Response(content=str(twiml), media_type="application/xml")
        
        if not speech_result:
            # No speech detected - end call after timeout
            twiml = VoiceResponse()
            twiml.say("I didn't hear anything. Thanks for calling, have a great day!", voice="Polly.Joanna", language="en-US")
            
            # Store final conversation
            try:
                store_final_conversation(call_sid)
                tlogging.info(f"Stored conversation after timeout")
            except Exception as e:
                tlogging.error(f"Error storing final conversation: {e}")
                
            twiml.hangup()
            return Response(content=str(twiml), media_type="application/xml")
        
        # Generate AI response with conversation context
        try:
            # Build conversation history for context
            messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
            
            # Add previous exchanges if they exist
            if call_sid in conversations:
                for exchange in conversations[call_sid]["exchanges"]:
                    messages.append({"role": "user", "content": exchange["user"]})
                    messages.append({"role": "assistant", "content": exchange["ai"]})
            
            # Add current user input
            messages.append({"role": "user", "content": speech_result})
            
            chat_completion = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            ai_response = chat_completion.choices[0].message.content
            tlogging.info(f"AI response: {ai_response[:100]}...")
        except Exception as e:
            tlogging.error(f"OpenAI error: {e}")
            ai_response = "I'm having trouble processing that right now. Could you try asking something else?"
        
        # Store conversation exchange
        try:
            add_to_conversation(call_sid, speech_result, ai_response)
        except Exception as e:
            tlogging.error(f"Storage error: {e}")
        
        # Continue conversation - KEEP IT ALIVE!
        twiml = VoiceResponse()
        twiml.say(ai_response, voice="Polly.Joanna", language="en-US")
        
        # Wait for next user input - NO HANGUP CODE HERE!
        twiml.gather(
            num_digits=0,
            speech_timeout="auto",
            speech_model="experimental_conversations", 
            action=f"{BASE_URL}/twilio/conversation",
            method="POST",
            input="speech",
            timeout=15
        )
        
        # Fallback if no response for 15 seconds - ONLY THEN end
        twiml.say("Thanks for calling! Have a great day!", voice="Polly.Joanna", language="en-US")
        twiml.hangup()
        
        return Response(content=str(twiml), media_type="application/xml")
        
    except Exception:
        tlogging.exception("Error in conversation_handler")
        fallback = VoiceResponse()
        fallback.say("I apologize for the technical difficulty. Please try calling again.", voice="Polly.Joanna", language="en-US")
        fallback.hangup()
        return Response(content=str(fallback), media_type="application/xml")

@app.post("/twilio/recording")
async def recording_callback(request: Request):
    """
    Recording callback: fetches audio, transcribes, stores, and replies.
    """
    try:
        tlogging.info("Processing recording callback")
        
        # Debug request information
        tlogging.info(f"Request method: {request.method}")
        tlogging.info(f"Request headers: {dict(request.headers)}")
        tlogging.info(f"Request URL: {request.url}")
        
        # Check content type and try to parse the form data
        content_type = request.headers.get("content-type", "")
        tlogging.info(f"Content-Type: {content_type}")
        
        form_data = {}
        try:
            if "application/x-www-form-urlencoded" in content_type:
                form = await request.form()
                form_data = dict(form)
                tlogging.info(f"Form data keys: {list(form_data.keys())}")
                # Log first few form values for debugging
                for key in list(form_data.keys())[:5]:  # Only log first 5 keys
                    value = str(form_data.get(key))[:100] if form_data.get(key) else None  # Truncate long values
                    tlogging.info(f"Form data - {key}: {value}")
            else:
                # Try to read as JSON or text
                body = await request.body()
                tlogging.info(f"Request body (first 500 chars): {body.decode('utf-8')[:500]}")
                # Try to parse as URL-encoded manually
                if body:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(body.decode('utf-8'))
                    form_data = {k: v[0] if v else None for k, v in parsed.items()}
                    tlogging.info(f"Manually parsed form data: {form_data}")
        except Exception as e:
            tlogging.error(f"Error parsing request data: {e}")
            # Return a proper TwiML response instead of raising an error
            fallback = VoiceResponse()
            fallback.say("Sorry, I couldn't process the recording. Please try again.", voice="Polly.Joanna", language="en-US")
            fallback.hangup()
            return Response(content=str(fallback), media_type="application/xml")
        
        call_sid = form_data.get("CallSid")
        recording_url = form_data.get("RecordingUrl")
        
        tlogging.info(f"Received callback - CallSid: {call_sid}, RecordingUrl: {recording_url}")
        
        if not call_sid or not recording_url:
            tlogging.error(f"Missing required parameters - CallSid: {call_sid}, RecordingUrl: {recording_url}")
            # Return a proper TwiML response instead of raising an error
            fallback = VoiceResponse()
            fallback.say("Sorry, there was an issue with the recording. Please try again.", voice="Polly.Joanna", language="en-US")
            fallback.hangup()
            return Response(content=str(fallback), media_type="application/xml")

        # Fetch audio with Basic Auth
        auth = aiohttp.BasicAuth(login=TWILIO_ACCOUNT_SID, password=TWILIO_AUTH_TOKEN)
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{recording_url}.wav", auth=auth) as resp:
                resp.raise_for_status()
                audio_data = await resp.read()

        # Save audio to GCS
        blob_audio = bucket.blob(f"audio/{call_sid}.wav")
        blob_audio.upload_from_string(audio_data, content_type="audio/wav")

        # Transcribe audio using OpenAI Whisper
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        try:
            tlogging.info("Starting audio transcription")
            with open(temp_file_path, "rb") as audio_file:
                tlogging.info(f"Audio file size: {os.path.getsize(temp_file_path)} bytes")
                transcript = oai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            text = transcript if isinstance(transcript, str) else transcript.text
            tlogging.info(f"Transcription completed: {text[:100]}...")
        except Exception as e:
            tlogging.error(f"Transcription error: {e}")
            tlogging.error(f"API key prefix: {openai_api_key[:15]}...")
            text = "Hello! I received your voice message. How can I help you today?"
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        # Generate AI response using GPT-4o-mini (legacy recording endpoint)
        tlogging.info("Generating AI response")
        try:
            chat_completion = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                max_tokens=150,
                temperature=0.7
            )
            ai_response = chat_completion.choices[0].message.content
            tlogging.info(f"AI response generated: {ai_response[:100]}...")
        except Exception as e:
            tlogging.error(f"OpenAI API error: {e}")
            # Fallback response if OpenAI fails
            ai_response = f"I heard you say: {text}. Thank you for your message!"

        # Store conversation data in GCS
        store_conversation_data(call_sid, text, ai_response)

        # Reply via TwiML
        tlogging.info(f"Creating TwiML response with message: {ai_response[:50]}...")
        response = VoiceResponse()
        response.say(ai_response, voice="Polly.Joanna", language="en-US")
        response.pause(length=1)  # Add a short pause before hanging up
        response.hangup()
        
        twiml_str = str(response)
        tlogging.info(f"TwiML response: {twiml_str}")
        return Response(content=twiml_str, media_type="application/xml")

    except Exception:
        tlogging.exception("Error in recording_callback")
        fallback = VoiceResponse()
        fallback.say("Sorry, I couldn't process your message. Goodbye.", voice="Polly.Joanna", language="en-US")
        fallback.hangup()
        return Response(content=str(fallback), media_type="application/xml")

@app.post("/twilio/call_recording_complete")
async def call_recording_complete(request: Request):
    """Handle call recording completion webhook (if recording enabled in Twilio Console)"""
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        recording_url = form_data.get('RecordingUrl')
        
        tlogging.info(f"Call recording completed for {call_sid}: {recording_url}")
        
        # Download and store the recording in GCS if available
        if recording_url and call_sid:
            try:
                import requests
                auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                response = requests.get(f"{recording_url}.wav", auth=auth)
                
                if response.status_code == 200:
                    blob = bucket.blob(f"recordings/{call_sid}.wav")
                    blob.upload_from_string(response.content, content_type="audio/wav")
                    gcs_audio_url = f"gs://{BUCKET_NAME}/recordings/{call_sid}.wav"
                    tlogging.info(f"Stored call recording for {call_sid}")
                    
            except Exception as e:
                tlogging.error(f"Error storing recording: {e}")
        
        return Response(status_code=200)
        
    except Exception as e:
        tlogging.error(f"Error in call_recording_complete: {e}")
        return Response(status_code=500)

@app.post("/twilio/call_status")
async def call_status(request: Request):
    """Handle call status webhook for call completion - SAVES COMPLETE CONVERSATION"""
    try:
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        call_status = form_data.get('CallStatus')
        
        tlogging.info(f"🔥 Call status update: {call_sid} - {call_status}")
        
        # When call actually ends, save the COMPLETE conversation
        if call_status == 'completed':
            if call_sid in conversations:
                conversation_data = store_final_conversation(call_sid)
                if conversation_data:
                    exchange_count = len(conversation_data.get('exchanges', []))
                    tlogging.info(f"✅ SAVED COMPLETE CONVERSATION: {call_sid} with {exchange_count} exchanges")
                else:
                    tlogging.error(f"❌ Failed to save conversation for {call_sid}")
            else:
                tlogging.warning(f"⚠️ No conversation data found for completed call {call_sid}")
        
        return Response(status_code=200)
        
    except Exception as e:
        tlogging.error(f"❌ Error in call_status: {e}")
        return Response(status_code=500)