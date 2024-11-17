import datetime
import wave
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import ollama
import base64
import uvicorn
from typing import Optional
import io
from openai import OpenAI
import time
import os 
import logging
import functools
import numpy as np
from scipy import signal
import soundfile as sf
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_timing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000

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
            
            # Add timing info to response if it's a dict
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

app = FastAPI(
    title="Vision API Server",
    description="A server that processes images using various vision models",
    version="1.0.0"
)

# Initialize OpenAI client
client = OpenAI()

async def encode_image_file(file: UploadFile) -> str:
    """
    Read and encode the uploaded file to base64
    """
    contents = await file.read()
    return base64.b64encode(contents).decode('utf-8')


@app.post("/analyze-image", response_model=dict)
@log_timing
async def analyze_image(
    file: UploadFile = File(...),
    prompt: Optional[str] = "What is in this image?"
):
    """
    Analyze an uploaded image using the Ollama vision model
    """
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
    prompt: Optional[str] = "What is in this image?",
    model: Optional[str] = "gpt-4o-mini"
):
    """
    Analyze an uploaded image using OpenAI's vision model
    
    Parameters:
    - file: The image file to analyze
    - prompt: Custom prompt to use for analysis (optional)
    - model: OpenAI model to use (optional, defaults to gpt-4o-mini)
    
    Returns:
    - JSON response with the model's analysis
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be an image"
        )
    
    try:
        start_time = time.time()
        
        # Encode the image
        image_data = await encode_image_file(file)
        
        # Create the message with the base64 image
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
        
        end_time = time.time()
        
        return {
            "status": "success",
            "prompt": prompt,
            "model": "openai_vision",
            "analysis": {
                "model": model,
                "created_at": response.created,
                "message": {
                    "role": "assistant",
                    "content": response.choices[0].message.content
                },
                "total_duration": (end_time - start_time) * 1000000000  # Convert to nanoseconds for consistency
            },
            "processing_time": end_time - start_time
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing image with OpenAI: {str(e)}"
        )

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)