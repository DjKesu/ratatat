// #include <CodeCell.h>
// #include <DriveCell.h>
// #include "Arduino.h"
// #include <WiFi.h>
// #include <HTTPClient.h>

// // WiFi Configuration
// #define WIFI_SSID "imnotsharingthis"
// #define WIFI_PASSWORD "wecouldbe"

// // Server Configuration
// const char* serverUrl = "https://fba1-99-209-235-170.ngrok-free.app/process-audio";

// //-----COMPONENT PINS----//
// #define SPEAKER_PIN 3
// #define MIC_PIN 1
// #define LEFT_MOTOR_IN1 1
// #define LEFT_MOTOR_IN2 7
// #define RIGHT_MOTOR_IN1 5
// #define RIGHT_MOTOR_IN2 6

// //-----AUDIO CONFIG----//
// #define SAMPLE_RATE 16000
// #define BUFFER_SIZE 320000  // Reduced to 50ms of audio at 16kHz (was 1600)
// #define SAMPLE_INTERVAL_MICROS (1000000 / SAMPLE_RATE)
// #define SQUEAK_FREQ_LOW 3500
// #define SQUEAK_FREQ_HIGH 4500
// #define SQUEAK_DURATION 50

// //--EYES---//
// #define LED_PIN 8  // Single GPIO pin for both LEDs

// // Global variables
// bool shouldSqueak = false;
// bool ledsOn = false;  // Added this declaration at global scope
// int16_t audioBuffer[BUFFER_SIZE];
// unsigned int bufferIndex = 0;
// unsigned long lastSampleTime = 0;
// unsigned long lastUploadTime = 0;
// unsigned long startTime = 0;
// const unsigned long UPLOAD_INTERVAL = 100; // Reduced to 100ms (was 1000ms)

// // LED control functions
// void setupLEDs() {
//     pinMode(LED_PIN, OUTPUT);
//     turnOffLEDs();  // Start with LEDs off
// }

// void turnOnLEDs() {
//     digitalWrite(LED_PIN, HIGH);
//     ledsOn = true;
// }

// void turnOffLEDs() {
//     digitalWrite(LED_PIN, LOW);
//     ledsOn = false;
// }

// void toggleLEDs() {
//     if (ledsOn) {
//         turnOffLEDs();
//     } else {
//         turnOnLEDs();
//     }
// }
// // Motor control structure
// struct MotorControl {
//     bool useLeft;
//     bool useRight;
//     bool leftForward;
//     bool rightForward;
//     int power;
//     bool isEnabled;
// } serverControl;

// // Component objects
// DriveCell leftMotor(LEFT_MOTOR_IN1, LEFT_MOTOR_IN2);
// DriveCell rightMotor(RIGHT_MOTOR_IN1, RIGHT_MOTOR_IN2);
// CodeCell myCodeCell;



// void logTimestamp() {
//     unsigned long runtime = millis() - startTime;
//     Serial.printf("[%8lums] ", runtime);
// }
// void sendAudioData() {
//     logTimestamp();
//     Serial.println("Preparing to send audio data...");

//     HTTPClient http;
//     http.begin(serverUrl);
    
//     // Convert audio buffer to bytes
//     uint8_t* audioBytes = (uint8_t*)malloc(BUFFER_SIZE * 2);
//     if (!audioBytes) {
//         Serial.println("Failed to allocate memory for audio bytes");
//         return;
//     }
    
//     // Pack the 16-bit samples into bytes
//     for(int i = 0; i < BUFFER_SIZE; i++) {
//         audioBytes[i*2] = (audioBuffer[i] >> 8) & 0xFF;
//         audioBytes[i*2 + 1] = audioBuffer[i] & 0xFF;
//     }
    
//     // Create the multipart form data
//     String boundary = "-------------------------" + String(millis());
//     String head = "--" + boundary + "\r\n";
//     head += "Content-Disposition: form-data; name=\"audio_data\"; filename=\"audio.raw\"\r\n";
//     head += "Content-Type: application/octet-stream\r\n\r\n";
//     String tail = "\r\n--" + boundary + "--\r\n";
    
//     uint32_t totalLength = head.length() + (BUFFER_SIZE * 2) + tail.length();
    
//     http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
//     http.addHeader("Content-Length", String(totalLength));
    
//     // Combine all parts into a single buffer
//     uint8_t* fullBuffer = (uint8_t*)malloc(totalLength);
//     if (!fullBuffer) {
//         free(audioBytes);
//         Serial.println("Failed to allocate memory for full buffer");
//         return;
//     }
    
//     // Copy header
//     memcpy(fullBuffer, head.c_str(), head.length());
//     // Copy audio data
//     memcpy(fullBuffer + head.length(), audioBytes, BUFFER_SIZE * 2);
//     // Copy tail
//     memcpy(fullBuffer + head.length() + (BUFFER_SIZE * 2), tail.c_str(), tail.length());
    
//     // Send the complete request
//     int httpResponseCode = http.POST(fullBuffer, totalLength);
    
//     // Free allocated memory
//     free(audioBytes);
//     free(fullBuffer);
    
//     if(httpResponseCode > 0) {
//         logTimestamp();
//         Serial.printf("HTTP Response code: %d\n", httpResponseCode);
//         String response = http.getString();
//         Serial.println("Response: " + response);
//     } else {
//         logTimestamp();
//         Serial.printf("Error sending data. Error code: %d\n", httpResponseCode);
//         Serial.printf("Error: %s\n", http.errorToString(httpResponseCode).c_str());
//     }
    
//     http.end();
// }


// void setup() {
//     Serial.begin(115200);
//     while(!Serial) {
//         delay(100);
//     }
    
//     startTime = millis();
//     logTimestamp();
//     Serial.println("Starting initialization...");
    
//     // Initialize components
//     myCodeCell.Init(LIGHT);
//     leftMotor.Init();
//     rightMotor.Init();
//     setupLEDs();  // Initialize LEDs

    
//     // Initialize server control values
//     serverControl.useLeft = true;
//     serverControl.useRight = true;
//     serverControl.leftForward = true;
//     serverControl.rightForward = true;
//     serverControl.power = 80;
//     serverControl.isEnabled = true;

//     pinMode(LED_PIN, OUTPUT);

//     // Configure ADC for microphone
//     // logTimestamp();
//     // Serial.println("Configuring ADC...");
//     // analogReadResolution(12);
//     // analogSetAttenuation(ADC_11db);

//     // Connect to WiFi
//     WiFi.mode(WIFI_STA);
//     WiFi.disconnect();
//     logTimestamp();
//     Serial.println("Connecting to Wi-Fi");
//     WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

//     while (WiFi.status() != WL_CONNECTED) {
//         delay(500);
//         Serial.print(".");
//     }
    
//     logTimestamp();
//     Serial.println("\nWiFi connected successfully!");
//     Serial.printf("IP address: %s\n", WiFi.localIP().toString().c_str());

//     shouldSqueak = true;
//       pinMode(LED_PIN, OUTPUT);


//     Serial.println("Setup complete! Starting main loop...");
//     delay(1000);
// }

// void loop() {
//     Serial.printf("Enter Main Loop");
//     unsigned long currentMicros = micros();
//     static unsigned long sampleCount = 0;
//     static unsigned long lastStatusLog = 0;

//     digitalWrite(LED_PIN, HIGH);




    
//     // // Sample audio at precise intervals
//     // if(currentMicros - lastSampleTime >= SAMPLE_INTERVAL_MICROS) {
//     //     lastSampleTime = currentMicros;
        
//     //     // Read from microphone
//     //     int sample = analogRead(MIC_PIN);
//     //     sampleCount++;
        
//     //     // Convert 12-bit ADC to 16-bit signed
//     //     int16_t processed_sample = (sample - 2048) * 16;
        
//     //     // Store in buffer
//     //     audioBuffer[bufferIndex] = processed_sample;
//     //     bufferIndex++;
        
//     //     // When buffer is full, send the data
//     //     if(bufferIndex >= BUFFER_SIZE) {
//     //         if(millis() - lastUploadTime >= UPLOAD_INTERVAL) {
//     //             if(WiFi.status() == WL_CONNECTED) {
//     //                 // sendAudioData();
//     //                 lastUploadTime = millis();
                    
//     //                 logTimestamp();
//     //                 Serial.printf("Audio data sent. Samples processed: %lu\n", sampleCount);
//     //             } else {
//     //                 logTimestamp();
//     //                 Serial.println("ERROR: WiFi disconnected! Attempting to reconnect...");
//     //                 WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
//     //             }
//     //         }
//     //         bufferIndex = 0;
//     //     }
//     // }
    
//     // Status logging
//     // if(millis() - lastStatusLog >= 5000) {
//     //     logTimestamp();
//     //     Serial.printf("Status - Samples: %lu, Buffer: %d/%d, WiFi RSSI: %d dBm\n",
//     //                  sampleCount, bufferIndex, BUFFER_SIZE, WiFi.RSSI());
//     //     lastStatusLog = millis();
//     // }
// }

