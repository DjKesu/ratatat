from flask import Flask, render_template, request, jsonify
from flask_mqtt import Mqtt
import logging
import json
import base64
import requests
import os

app = Flask(__name__)

# mqtt config
app.config['MQTT_BROKER_URL'] = 'test.mosquitto.org'
app.config['MQTT_BROKER_PORT'] = 1883
app.config['WHISPER_API_KEY'] = os.getenv('WHISPER_API_KEY')
app.config['AUDIO_THRESHOLD'] = 0.2  # Adjust based on testing

try:
    mqtt = Mqtt(app)
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")
    mqtt = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rat Control Endpoints
@app.route('/rat/hands', methods=['POST'])
def control_hands():
    """Control rat's hands
    
    curl -X POST https://bratatouille-bot.fly.dev/rat/hands \
        -H "Content-Type: application/json" \
        -d '{"right": true, "left": false}'
    """
    data = request.json
    command = {
        "action": "hands",
        "right": data.get('right', False),
        "left": data.get('left', False)
    }
    mqtt.publish('rat/commands', json.dumps(command))
    return jsonify({"status": "ok"})

@app.route('/rat/speak', methods=['POST'])
def speak():
    """Make rat speak text
    
    curl -X POST https://bratatouille-bot.fly.dev/rat/speak \
        -H "Content-Type: application/json" \
        -d '{"text": "Hello, I am a robot rat!"}'
    """
    data = request.json
    command = {
        "action": "speak",
        "text": data.get('text', '')
    }
    mqtt.publish('rat/commands', json.dumps(command))
    return jsonify({"status": "ok"})

@app.route('/rat/glow', methods=['POST'])
def glow():
    """Control rat's LED eyes
    
    # Full white brightness
    curl -X POST https://bratatouille-bot.fly.dev/rat/glow \
        -H "Content-Type: application/json" \
        -d '{"brightness": 100, "color": "white"}'
    
    # Half red brightness
    curl -X POST https://bratatouille-bot.fly.dev/rat/glow \
        -H "Content-Type: application/json" \
        -d '{"brightness": 50, "color": "red"}'
    """
    data = request.json
    command = {
        "action": "glow",
        "brightness": data.get('brightness', 100),
        "color": data.get('color', 'white')
    }
    mqtt.publish('rat/commands', json.dumps(command))
    return jsonify({"status": "ok"})

# Audio Processing
@app.route('/rat/audio', methods=['POST'])
def process_audio():
    """Process audio file and get rat response
    
    curl -X POST https://bratatouille-bot.fly.dev/rat/audio \
        -F "audio=@/path/to/recording.wav"
    """
    audio_data = request.files['audio'].read()
    
    # Convert to base64 for Whisper API
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    
    # Send to Whisper API
    headers = {
        'Authorization': f'Bearer {app.config["WHISPER_API_KEY"]}',
        'Content-Type': 'application/json'
    }
    
    whisper_response = requests.post(
        'https://api.openai.com/v1/audio/transcriptions',
        headers=headers,
        json={
            'audio': audio_base64,
            'model': 'whisper-1'
        }
    )
    
    text = whisper_response.json().get('text')
    
    # Get response from external AI server
    # This is a placeholder - replace with your actual AI endpoint
    ai_response = requests.post(
        'https://your-ai-server.com/chat',
        json={'input': text}
    ).json()
    
    # Send response to rat for TTS
    command = {
        "action": "speak",
        "text": ai_response['response']
    }
    mqtt.publish('rat/commands', json.dumps(command))
    
    return jsonify({
        "status": "ok",
        "transcription": text,
        "response": ai_response['response']
    })

@app.route('/')
@app.route('/<name>')
def hello(name=None):
    logger.info("Received request on root endpoint")
    return render_template('hello.html', name=name)

@app.route('/test')
def test_publish():
    """Test MQTT connection
    
    curl https://bratatouille-bot.fly.dev/test
    
    # Monitor response:
    mosquitto_sub -h test.mosquitto.org -p 1883 -t "rat/test/alice123" -v
    """
    if mqtt:
        mqtt.publish('rat/test/alice123', 'test message')
        logger.info("Published test message to rat/test/alice123")
        return "Test message sent"
    return "MQTT not connected"

@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    if mqtt is None:
        return
    if rc == 0:
        print("🐀 MY RAT server up")
        mqtt.subscribe('rat/sensors/#')
        mqtt.subscribe('rat/test/alice123')
    else:
        print(f"connection failed: {rc}")

@mqtt.on_message()
def handle_message(client, userdata, message):
    if mqtt is None:
        return
    topic = message.topic
    payload = message.payload.decode()
    print(f"got message on {topic}: {payload}")
    
    if topic == 'rat/sensors/audio_level':
        level = float(payload)
        if level > app.config['AUDIO_THRESHOLD']:
            # Trigger Arduino to start streaming audio
            mqtt.publish('rat/commands', json.dumps({
                "action": "stream_audio",
                "start": True
            }))
    
    elif topic == 'rat/sensors/proximity':
        command = {
            "action": "dance",
            "speed": 100,
            "duration": 1000
        }
        mqtt.publish('rat/commands', json.dumps(command))

   