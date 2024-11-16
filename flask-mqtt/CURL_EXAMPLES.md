# API Test Commands

## Test Basic Connection
```bash
# Test MQTT connection
curl https://bratatouille-bot.fly.dev/test
```

## Rat Control Commands

### Raise Hands
```bash
# Raise right hand only
curl -X POST https://bratatouille-bot.fly.dev/rat/hands \
  -H "Content-Type: application/json" \
  -d '{"right": true, "left": false}'

# Raise both hands
curl -X POST https://bratatouille-bot.fly.dev/rat/hands \
  -H "Content-Type: application/json" \
  -d '{"right": true, "left": true}'
```

### Make Rat Speak
```bash
curl -X POST https://bratatouille-bot.fly.dev/rat/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, I am a robot rat!"}'
```

### Control LED Eyes
```bash
# White glow at full brightness
curl -X POST https://bratatouille-bot.fly.dev/rat/glow \
  -H "Content-Type: application/json" \
  -d '{"brightness": 100, "color": "white"}'

# Red glow at half brightness
curl -X POST https://bratatouille-bot.fly.dev/rat/glow \
  -H "Content-Type: application/json" \
  -d '{"brightness": 50, "color": "red"}'
```

### Send Audio for Processing
```bash
# Send audio file for processing
curl -X POST https://bratatouille-bot.fly.dev/rat/audio \
  -F "audio=@/path/to/audio.wav"
```

## Monitor MQTT Messages
```bash
# Listen to all rat sensor data
mosquitto_sub -h test.mosquitto.org -p 1883 -t "rat/sensors/#" -v

# Listen to commands sent to rat
mosquitto_sub -h test.mosquitto.org -p 1883 -t "rat/commands" -v

# Listen to test channel
mosquitto_sub -h test.mosquitto.org -p 1883 -t "rat/test/alice123" -v
``` 