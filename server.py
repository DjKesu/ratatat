import datetime
import wave
import os
import json
import logging
import functools
import time
from typing import List, Optional
from io import BytesIO
import base64
import numpy as np
from pydantic import BaseModel
import requests
import ollama
from openai import OpenAI
import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response
import io

ELEVEN_LABS_API_KEY = "sk_53d147734d29301d6076fb1feec28f76ef8650f4cd13a9b7"
VOICE_ID = "nXUMivg97yAaSqlaJWJG"
CHUNK_SIZE = 1024
SAMPLE_RATE = 16000
CHAT_HISTORY_FILE = "chat_history.json"

ELEVEN_LABS_CONFIG = {
    "base_url": "https://api.elevenlabs.io/v1/text-to-speech",
    "headers": {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVEN_LABS_API_KEY
    },
    "model_id": "eleven_monolingual_v1",
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.5
    }
}

app = FastAPI(
    title="Vision and Audio API Server",
    description="A server that processes images and audio using various models",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_timing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

client = OpenAI()

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class ChatHistory(BaseModel):
    session_id: str
    messages: List[Message]

class ChatResponse(BaseModel):
    status: str
    response: str
    chat_history: List[Message]

class GenerateResponseRequest(BaseModel):
    transcription: str
    session_id: Optional[str] = None

class TextToSpeechRequest(BaseModel):
    text: str

class RecipeState(BaseModel):
    session_id: str
    current_stage: int
    last_completed_step: int
    waiting_for: str
    start_time: str
    milk_added_time: Optional[str] = None

class RecipeContext(BaseModel):
    recipe_stage: str
    last_completed_step: int
    waiting_for: str

RECIPE_STAGES = {
    "SETUP": 1,
    "MEASURE_CEREAL": 2,
    "ADD_MILK": 3,
    "ADD_TOPPINGS": 4,
    "FINAL_CHECK": 5
}

VISION_SYSTEM_PROMPT = """You are a precise kitchen assistant analyzing real-time images of cereal preparation. Your role is to:
1. Identify the current step in the recipe based on visual cues
2. Verify if the step is being executed correctly
3. Provide specific, actionable feedback
4. Identify potential issues or safety concerns

For each image, analyze and respond with:
{
  "current_step": "[identified step number and name]",
  "status": "correct" | "incorrect" | "warning",
  "scene_elements": {
    "bowl_present": boolean,
    "cereal_visible": boolean,
    "milk_visible": boolean,
    "toppings_visible": boolean,
    "estimated_fill_levels": {
      "cereal": "empty" | "partial" | "correct" | "overfilled",
      "milk": "none" | "too_low" | "correct" | "too_high"
    }
  },
  "feedback": "[specific feedback about the current state]",
  "next_action": "[what the user should do next]",
  "safety_concerns": "[any identified issues]"
}"""

AUDIO_SYSTEM_PROMPT = """You are a helpful kitchen assistant specializing in guiding users through cereal preparation. 
Maintain context of the current step and provide clear, concise instructions. Keep responses brief and practical.

Current Recipe Stage: {recipe_stage}
Last Completed Step: {last_step}
Waiting For: {waiting_for}

Remember to:
1. Give one clear instruction at a time
2. Use kitchen-friendly language
3. Mention safety reminders when relevant
4. Keep responses under 3 sentences
5. Maintain awareness of recipe progress"""

def log_timing(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        endpoint_name = func.__name__
        
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            processing_time = end_time - start_time
            
            logger.info(f"Endpoint: {endpoint_name} - Processing Time: {processing_time:.2f} seconds")
            
            if isinstance(result, dict):
                result["timing"] = {
                    "endpoint": endpoint_name,
                    "processing_time_seconds": processing_time
                }
            return result
            
        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            logger.error(f"Endpoint: {endpoint_name} - Error - Processing Time: {processing_time:.2f} seconds - Error: {str(e)}")
            raise
            
    return wrapper

async def encode_image_file(file: UploadFile) -> str:
    """Read and encode the uploaded file to base64"""
    contents = await file.read()
    return base64.b64encode(contents).decode('utf-8')

def load_chat_history() -> dict:
    """Load chat history from file"""
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_chat_history(history: dict):
    """Save chat history to file"""
    with open(CHAT_HISTORY_FILE, 'w') as f:
        json.dump(history, f, default=str)

COOKING_SYSTEM_PROMPT = """You are an experienced and passionate culinary assistant. 
Help users with cooking advice, recipe suggestions, ingredient substitutions, 
and kitchen techniques. Keep responses practical and easy to follow, using 
everyday language. If users ask about dietary restrictions or food allergies, 
remind them to verify ingredients for their specific needs. Maintain a warm, 
encouraging tone while being concise and clear. Only give one step at a time. Keep answers short."""

@app.post("/analyze-image", response_model=dict)
@log_timing
async def analyze_image(
    file: UploadFile = File(...),
    prompt: Optional[str] = "What is in this image?"
):
    """Analyze an uploaded image using the Ollama vision model"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image"
        )
    
    try:
        start_time = time.time()
        image_data = await encode_image_file(file)
        
        response = ollama.chat(
            model='llama3.2-vision',
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_data]
            }]
        )
        
        end_time = time.time()
        
        return {
            "status": "success",
            "prompt": prompt,
            "model": "ollama_vision",
            "analysis": response,
            "processing_time": end_time - start_time
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image: {str(e)}"
        )

@app.post("/analyze-image-openai", response_model=dict)
@log_timing
async def analyze_image_openai(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    model: Optional[str] = "gpt-4o-mini"
):
    """Analyze an uploaded image using OpenAI's vision model with recipe context"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")
    
    try:
        start_time = time.time()
        image_data = await encode_image_file(file)
        
        # Get recipe state if session_id provided
        recipe_state = None
        if session_id:
            recipe_states = load_recipe_states()
            recipe_state = recipe_states.get(session_id)
        
        # Customize prompt based on recipe state
        prompt = VISION_SYSTEM_PROMPT
        if recipe_state:
            prompt += f"\nCurrent recipe stage: {recipe_state.current_stage}"
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        
        analysis = response.choices[0].message.content
        
        # Update recipe state if provided
        if recipe_state and isinstance(analysis, dict):
            update_recipe_state(session_id, analysis)
        
        end_time = time.time()
        
        return {
            "status": "success",
            "recipe_context": recipe_state.dict() if recipe_state else None,
            "analysis": {
                "model": model,
                "created_at": response.created,
                "message": {
                    "role": "assistant",
                    "content": analysis
                },
                "total_duration": (end_time - start_time) * 1000000000
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.post("/text-completions", response_model=dict)
@log_timing
async def text_completions(
    system_prompt: Optional[str] = None,
    prompt: str = None,
):
    """
    Generate text completions using the Llama3.2 model
    """
    if not system_prompt:
        system_prompt = "You are a helpful cooking assistant."
        
    response = ollama.chat(
        model='llama3.2',
        messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt}]
    )
    
    return {
        "status": "success",
        "prompt": prompt,
        "analysis": response
    }

@app.get("/health")
@log_timing
async def health_check():
    """
    Simple health check endpoint
    """
    return {"status": "healthy"}

@app.post("/audio/speech-to-text")
@log_timing
async def speech_to_text(file: UploadFile = File(...)):
    """
    Convert speech to text using OpenAI's Whisper model
    """
    try:
        # Save uploaded file temporarily
        temp_audio_path = f"temp_audio_{int(time.time())}.m4a"
        with open(temp_audio_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)

        # Transcribe with OpenAI Whisper
        with open(temp_audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        # Clean up temp file
        os.remove(temp_audio_path)

        if not transcription.text.strip():
            raise HTTPException(status_code=400, detail="No speech detected")

        return {
            "status": "success",
            "transcription": transcription.text
        }

    except Exception as e:
        logging.error(f"Error in speech-to-text: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cooking/generate-response", response_model=ChatResponse)
@log_timing
async def generate_cooking_response(request: GenerateResponseRequest):
    """Generate cooking-focused response with recipe context"""
    try:
        # Get recipe state
        recipe_states = load_recipe_states()
        recipe_state = recipe_states.get(request.session_id, {
            "current_stage": RECIPE_STAGES["SETUP"],
            "last_completed_step": 0,
            "waiting_for": "bowl placement",
            "start_time": datetime.datetime.now().isoformat()
        })
        
        # Format audio prompt with context
        context = RecipeContext(
            recipe_stage=list(RECIPE_STAGES.keys())[recipe_state["current_stage"] - 1],
            last_completed_step=recipe_state["last_completed_step"],
            waiting_for=recipe_state["waiting_for"]
        )
        
        system_prompt = AUDIO_SYSTEM_PROMPT.format(
            recipe_stage=context.recipe_stage,
            last_step=context.last_completed_step,
            waiting_for=context.waiting_for
        )
        
        # Generate response with context
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.transcription}
            ]
        )

        ai_response = completion.choices[0].message.content
        
        # Update chat history
        chat_histories = load_chat_history()
        session_history = chat_histories.get(request.session_id, {"messages": []})
        session_history["messages"].append({
            "role": "user",
            "content": request.transcription,
            "timestamp": datetime.datetime.now().isoformat()
        })
        session_history["messages"].append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        chat_histories[request.session_id] = session_history
        save_chat_history(chat_histories)

        return ChatResponse(
            status="success",
            response=ai_response,
            chat_history=session_history["messages"]
        )

    except Exception as e:
        logging.error(f"Error in generate-response: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Add endpoint to fetch chat history
@app.get("/cooking/chat-history/{session_id}")
async def get_chat_history(session_id: str):
    """
    Retrieve chat history for a specific session
    """
    try:
        chat_histories = load_chat_history()
        if session_id not in chat_histories:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return {
            "status": "success",
            "chat_history": chat_histories[session_id]["messages"]
        }
        
    except Exception as e:
        logging.error(f"Error fetching chat history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Add endpoint to list all sessions
@app.get("/cooking/sessions")
async def get_sessions():
    """
    Retrieve list of all chat sessions
    """
    try:
        chat_histories = load_chat_history()
        sessions = [
            {
                "session_id": session_id,
                "message_count": len(history["messages"]),
                "last_updated": max(msg["timestamp"] for msg in history["messages"]) if history["messages"] else None
            }
            for session_id, history in chat_histories.items()
        ]
        
        return {
            "status": "success",
            "sessions": sessions
        }
        
    except Exception as e:
        logging.error(f"Error fetching sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/audio/text-to-speech")
@log_timing
async def text_to_speech(request: TextToSpeechRequest):
    """
    Convert text to speech using ElevenLabs and return audio data
    """
    try:
        eleven_labs_url = f"{ELEVEN_LABS_CONFIG['base_url']}/{VOICE_ID}"
        
        data = {
            "text": request.text,
            "model_id": ELEVEN_LABS_CONFIG["model_id"],
            "voice_settings": ELEVEN_LABS_CONFIG["voice_settings"]
        }

        # Make request to ElevenLabs
        response = requests.post(
            eleven_labs_url,
            json=data,
            headers=ELEVEN_LABS_CONFIG["headers"],
            stream=True
        )

        if not response.ok:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"ElevenLabs API error: {response.text}"
            )

        # Collect audio data
        audio_data = io.BytesIO()
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                audio_data.write(chunk)
        
        # Reset buffer position
        audio_data.seek(0)

        # Return audio data with appropriate headers
        return Response(
            content=audio_data.read(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3",
                "Access-Control-Expose-Headers": "Content-Length",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        logger.error(f"Error in text-to-speech: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/audio/complete-interaction")
@log_timing
async def complete_audio_interaction(file: UploadFile = File(...)):
    """Combined endpoint for full audio interaction chain"""
    try:
        # Step 1: Speech to Text
        transcription_result = await speech_to_text(file)
        transcription = transcription_result["transcription"]

        # Step 2: Generate Response
        request = GenerateResponseRequest(transcription=transcription)
        response_result = await generate_cooking_response(request)
        ai_response = response_result.response

        # Step 3: Text to Speech
        tts_request = TextToSpeechRequest(text=ai_response)
        audio_response = await text_to_speech(tts_request)

        return Response(
            content=audio_response.body,
            media_type="audio/mpeg",
            headers={
                "X-Transcription": transcription,
                "X-Response": ai_response,
                "Content-Disposition": "attachment; filename=response.mp3",
                "Access-Control-Expose-Headers": "X-Transcription, X-Response"
            }
        )

    except Exception as e:
        logger.error(f"Error in complete-interaction: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-audio-chain")
@log_timing
async def test_audio_chain():
    """
    Test endpoint for the complete audio processing chain
    """
    try:
        test_text = "This is a test of the audio processing chain."
        
        # First get AI response
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": test_text}]
        )

        ai_response = completion.choices[0].message.content

        # Then convert to speech
        eleven_labs_url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVEN_LABS_API_KEY
        }

        data = {
            "text": ai_response,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response = requests.post(
            eleven_labs_url,
            json=data,
            headers=headers,
            stream=True
        )

        return StreamingResponse(
            response.iter_content(chunk_size=CHUNK_SIZE),
            media_type="audio/mpeg",
            headers={
                "X-Original-Text": test_text,
                "X-AI-Response": ai_response
            }
        )

    except Exception as e:
        logging.error(f"Error in test-audio-chain endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-audio", response_model=dict)
@log_timing
async def process_audio(audio_data: bytes = File(...)):
    """
    Process incoming audio data and save as WAV file
    """
    try:
        logger.info("Received audio data")
        logger.info(f"Received {len(audio_data)} bytes of data")
        
        # Convert bytes to 16-bit integers
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        logger.info(f"Converted to {len(audio_array)} samples")
        
        # Generate filename with timestamp
        filename = f'audio_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.wav'
        filepath = os.path.join('audio_files', filename)
        
        # Create directory if it doesn't exist
        os.makedirs('audio_files', exist_ok=True)
        
        # Save as WAV file
        with wave.open(filepath, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 2 bytes per sample
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio_array.tobytes())
        
        logger.info(f"Saved audio file: {filename}")
        
        return {
            'status': 'success',
            'message': 'Audio received and saved',
            'filename': filename,
            'samples': len(audio_array),
            'duration_ms': len(audio_array) * 1000 / SAMPLE_RATE
        }
        
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

def load_recipe_states() -> dict:
    """Load recipe states from file"""
    if os.path.exists('recipe_states.json'):
        with open('recipe_states.json', 'r') as f:
            return json.load(f)
    return {}

def save_recipe_states(states: dict):
    """Save recipe states to file"""
    with open('recipe_states.json', 'w') as f:
        json.dump(states, f, default=str)

def update_recipe_state(session_id: str, analysis: dict):
    """Update recipe state based on vision analysis"""
    states = load_recipe_states()
    current_state = states.get(session_id, {
        "current_stage": RECIPE_STAGES["SETUP"],
        "last_completed_step": 0,
        "waiting_for": "bowl placement",
        "start_time": datetime.datetime.now().isoformat()
    })
    
    # Update state based on analysis
    if analysis.get("current_step"):
        current_state["current_stage"] = int(analysis["current_step"].split()[0])
    if analysis.get("next_action"):
        current_state["waiting_for"] = analysis["next_action"]
    
    # Track milk addition time
    if (current_state["current_stage"] == RECIPE_STAGES["ADD_MILK"] and 
        not current_state.get("milk_added_time")):
        current_state["milk_added_time"] = datetime.datetime.now().isoformat()
    
    states[session_id] = current_state
    save_recipe_states(states)

@app.get("/recipe/state/{session_id}")
async def get_recipe_state(session_id: str):
    """Get current recipe state for a session"""
    try:
        states = load_recipe_states()
        if session_id not in states:
            raise HTTPException(status_code=404, detail="Recipe session not found")
            
        return {
            "status": "success",
            "recipe_state": states[session_id]
        }
        
    except Exception as e:
        logging.error(f"Error fetching recipe state: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)