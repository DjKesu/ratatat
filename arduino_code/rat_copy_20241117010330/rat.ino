#include <CodeCell.h>
#include <DriveCell.h>
#include "Arduino.h"
#include <WiFi.h>
#include <HTTPClient.h>

// WiFi Configuration
#define WIFI_SSID "imnotsharingthis"
#define WIFI_PASSWORD "wecouldbe"

// Server Configuration
const char* serverUrl = "https://fba1-99-209-235-170.ngrok-free.app/process-audio";

//-----COMPONENT PINS----//
#define SPEAKER_PIN 3
#define MIC_PIN 1
#define LEFT_MOTOR_IN1 1
#define LEFT_MOTOR_IN2 7
#define RIGHT_MOTOR_IN1 5
#define RIGHT_MOTOR_IN2 6

//-----AUDIO CONFIG----//
#define SAMPLE_RATE 16000
#define BUFFER_SIZE 800  // Reduced to 50ms of audio at 16kHz (was 1600)
#define SAMPLE_INTERVAL_MICROS (1000000 / SAMPLE_RATE)
#define SQUEAK_FREQ_LOW 3500
#define SQUEAK_FREQ_HIGH 4500
#define SQUEAK_DURATION 50

// Global variables
bool shouldSqueak = false;
int16_t audioBuffer[BUFFER_SIZE];
unsigned int bufferIndex = 0;
unsigned long lastSampleTime = 0;
unsigned long lastUploadTime = 0;
unsigned long startTime = 0;
const unsigned long UPLOAD_INTERVAL = 100; // Reduced to 100ms (was 1000ms)

// Motor control structure
struct MotorControl {
    bool useLeft;
    bool useRight;
    bool leftForward;
    bool rightForward;
    int power;
    bool isEnabled;
} serverControl;

// Component objects
DriveCell leftMotor(LEFT_MOTOR_IN1, LEFT_MOTOR_IN2);
DriveCell rightMotor(RIGHT_MOTOR_IN1, RIGHT_MOTOR_IN2);
CodeCell myCodeCell;

void logTimestamp() {
    unsigned long runtime = millis() - startTime;
    Serial.printf("[%8lums] ", runtime);
}
void sendAudioData() {
    logTimestamp();
    Serial.println("Preparing to send audio data...");

    HTTPClient http;
    http.begin(serverUrl);
    
    // Convert audio buffer to bytes
    uint8_t* audioBytes = (uint8_t*)malloc(BUFFER_SIZE * 2);
    if (!audioBytes) {
        Serial.println("Failed to allocate memory for audio bytes");
        return;
    }
    
    // Pack the 16-bit samples into bytes
    for(int i = 0; i < BUFFER_SIZE; i++) {
        audioBytes[i*2] = (audioBuffer[i] >> 8) & 0xFF;
        audioBytes[i*2 + 1] = audioBuffer[i] & 0xFF;
    }
    
    // Create the multipart form data
    String boundary = "-------------------------" + String(millis());
    String head = "--" + boundary + "\r\n";
    head += "Content-Disposition: form-data; name=\"audio_data\"; filename=\"audio.raw\"\r\n";
    head += "Content-Type: application/octet-stream\r\n\r\n";
    String tail = "\r\n--" + boundary + "--\r\n";
    
    uint32_t totalLength = head.length() + (BUFFER_SIZE * 2) + tail.length();
    
    http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
    http.addHeader("Content-Length", String(totalLength));
    
    // Combine all parts into a single buffer
    uint8_t* fullBuffer = (uint8_t*)malloc(totalLength);
    if (!fullBuffer) {
        free(audioBytes);
        Serial.println("Failed to allocate memory for full buffer");
        return;
    }
    
    // Copy header
    memcpy(fullBuffer, head.c_str(), head.length());
    // Copy audio data
    memcpy(fullBuffer + head.length(), audioBytes, BUFFER_SIZE * 2);
    // Copy tail
    memcpy(fullBuffer + head.length() + (BUFFER_SIZE * 2), tail.c_str(), tail.length());
    
    // Send the complete request
    int httpResponseCode = http.POST(fullBuffer, totalLength);
    
    // Free allocated memory
    free(audioBytes);
    free(fullBuffer);
    
    if(httpResponseCode > 0) {
        logTimestamp();
        Serial.printf("HTTP Response code: %d\n", httpResponseCode);
        String response = http.getString();
        Serial.println("Response: " + response);
    } else {
        logTimestamp();
        Serial.printf("Error sending data. Error code: %d\n", httpResponseCode);
        Serial.printf("Error: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    
    http.end();
}

// void sendAudioData() {
//     logTimestamp();
//     Serial.println("Preparing to send audio data...");

//     HTTPClient http;
//     http.begin(serverUrl);
    
//     // Just send the raw audio bytes
//     http.addHeader("Content-Type", "application/octet-stream");
    
//     // Convert audio buffer to bytes
//     uint8_t* audioBytes = (uint8_t*)malloc(BUFFER_SIZE * 2);  // 2 bytes per sample
//     if (!audioBytes) {
//         Serial.println("Failed to allocate memory for audio bytes");
//         return;
//     }
    
//     // Pack the 16-bit samples into bytes
//     for(int i = 0; i < BUFFER_SIZE; i++) {
//         audioBytes[i*2] = (audioBuffer[i] >> 8) & 0xFF;     // High byte
//         audioBytes[i*2 + 1] = audioBuffer[i] & 0xFF;        // Low byte
//     }
    
//     // Send the raw audio data
//     int httpResponseCode = http.POST(audioBytes, BUFFER_SIZE * 2);
    
//     free(audioBytes);
    
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

void setup() {
    Serial.begin(115200);
    while(!Serial) {
        delay(100);
    }
    
    startTime = millis();
    logTimestamp();
    Serial.println("Starting initialization...");
    
    // Initialize components
    myCodeCell.Init(LIGHT);
    leftMotor.Init();
    rightMotor.Init();
    
    // Initialize server control values
    serverControl.useLeft = true;
    serverControl.useRight = true;
    serverControl.leftForward = true;
    serverControl.rightForward = true;
    serverControl.power = 80;
    serverControl.isEnabled = true;

    // Configure ADC for microphone
    logTimestamp();
    Serial.println("Configuring ADC...");
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    // Connect to WiFi
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    logTimestamp();
    Serial.println("Connecting to Wi-Fi");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    logTimestamp();
    Serial.println("\nWiFi connected successfully!");
    Serial.printf("IP address: %s\n", WiFi.localIP().toString().c_str());

    shouldSqueak = true;
    Serial.println("Setup complete! Starting main loop...");
    delay(1000);
}

void loop() {
    unsigned long currentMicros = micros();
    static unsigned long sampleCount = 0;
    static unsigned long lastStatusLog = 0;
    
    // Sample audio at precise intervals
    if(currentMicros - lastSampleTime >= SAMPLE_INTERVAL_MICROS) {
        lastSampleTime = currentMicros;
        
        // Read from microphone
        int sample = analogRead(MIC_PIN);
        sampleCount++;
        
        // Convert 12-bit ADC to 16-bit signed
        int16_t processed_sample = (sample - 2048) * 16;
        
        // Store in buffer
        audioBuffer[bufferIndex] = processed_sample;
        bufferIndex++;
        
        // When buffer is full, send the data
        if(bufferIndex >= BUFFER_SIZE) {
            if(millis() - lastUploadTime >= UPLOAD_INTERVAL) {
                if(WiFi.status() == WL_CONNECTED) {
                    sendAudioData();
                    lastUploadTime = millis();
                    
                    logTimestamp();
                    Serial.printf("Audio data sent. Samples processed: %lu\n", sampleCount);
                } else {
                    logTimestamp();
                    Serial.println("ERROR: WiFi disconnected! Attempting to reconnect...");
                    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
                }
            }
            bufferIndex = 0;
        }
    }
    
    // Status logging
    if(millis() - lastStatusLog >= 5000) {
        logTimestamp();
        Serial.printf("Status - Samples: %lu, Buffer: %d/%d, WiFi RSSI: %d dBm\n",
                     sampleCount, bufferIndex, BUFFER_SIZE, WiFi.RSSI());
        lastStatusLog = millis();
    }
}


// #include <CodeCell.h>
// #include <DriveCell.h>
// #include "Arduino.h"
// #include <WiFi.h>
// #include <HTTPClient.h>

// #define WIFI_SSID "imnotsharingthis"
// #define WIFI_PASSWORD "wecouldbe"


// //-----SPEAKER CONFIG----//
// #define SPEAKER_PIN 3  
// #define SQUEAK_FREQ_LOW 3500    // Higher frequency for more rat-like sound
// #define SQUEAK_FREQ_HIGH 4500   // Even higher for the peak of the squeak
// #define SQUEAK_DURATION 50      // Shorter duration for more rapid squeaks
// bool shouldSqueak = false;


// //-----MIC CONFIG------//
// #define MIC_PIN 2
// #define SAMPLE_WINDOW 50

// //-----MOTOR CONFIG----//
// #define LEFT_MOTOR_IN1 1
// #define LEFT_MOTOR_IN2 7
// #define RIGHT_MOTOR_IN1 5
// #define RIGHT_MOTOR_IN2 6



// // Global variables for motor control
// struct MotorControl {
//     bool useLeft;
//     bool useRight;
//     bool leftForward;
//     bool rightForward;
//     int power;
//     bool isEnabled;
// } serverControl;

// // Create DriveCell objects for both motors and CodeCell
// DriveCell leftMotor(LEFT_MOTOR_IN1, LEFT_MOTOR_IN2);
// DriveCell rightMotor(RIGHT_MOTOR_IN1, RIGHT_MOTOR_IN2);
// CodeCell myCodeCell;

// // Variables for sound processing
// unsigned long lastSoundCheck = 0;

// void setup() {
//     Serial.begin(115200);
//     Serial.println("Entered Setup");
    
//     // Initialize components
//     myCodeCell.Init(LIGHT);
//     leftMotor.Init();
//     rightMotor.Init();
    
//     // Initialize server control values
//     serverControl.useLeft = true;
//     serverControl.useRight = true;
//     serverControl.leftForward = true;
//     serverControl.rightForward = true;
//     serverControl.power = 80;
//     serverControl.isEnabled = true;

//     // Wifi setup
//     WiFi.mode(WIFI_STA);
//     WiFi.disconnect();

//     // Connect to WiFi
//     Serial.println("Connecting to Wi-Fi");
//     WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

//     Serial.println(WL_CONNECTED);

//     while (WiFi.status() != WL_CONNECTED) {
//       delay(1000);
//       Serial.println(".");
//     }
//     Serial.println("Connected to Wi-Fi");

//     shouldSqueak = true;
    
//     Serial.println("Setup complete. Ready to communicate with server.");

//     delay(1000);  // Wait for serial monitor to open

// }

// // void playSqueak() {
// //     // Alternate between two frequencies to create a squeaking effect
// //     tone(SPEAKER_PIN, SQUEAK_FREQ_HIGH, SQUEAK_DURATION);
// //     delay(SQUEAK_DURATION);
// //     tone(SPEAKER_PIN, SQUEAK_FREQ_LOW, SQUEAK_DURATION);
// //     delay(SQUEAK_DURATION);
// // }

// void playSqueak() {
//     // Random variation in the starting frequency
//     int startFreq = SQUEAK_FREQ_LOW + random(-200, 200);
//     int endFreq = SQUEAK_FREQ_HIGH + random(-300, 300);
    
//     // Quick rising chirp
//     for(int i = startFreq; i < endFreq; i += 250) {
//         tone(SPEAKER_PIN, i, 15);
//         delay(15);
//     }
//     delay(random(50, 150));  // Random pause between squeaks
// }

// void processSoundInput() {
//     unsigned long startMillis = millis();
//     unsigned int signalMax = 0;
//     unsigned int signalMin = 1024;  // Initialize to max possible value
    
//     // Collect sound data for 50 ms
//     while (millis() - startMillis < SAMPLE_WINDOW) {
//         unsigned int sample = analogRead(MIC_PIN);
//         if (sample < 1024) {  // Valid reading check
//             if (sample > signalMax) {
//                 signalMax = sample;
//             }
//             if (sample < signalMin) {
//                 signalMin = sample;
//             }
//         }
//     }
    
//     // Calculate peak-to-peak amplitude
//     int peakToPeak = signalMax - signalMin;
    
//     // Debug output
//     Serial.print("Sound Level: ");
//     Serial.print(peakToPeak);  // This should now be a positive number
//     Serial.print("\tMax: ");
//     Serial.print(signalMax);
//     Serial.print("\tMin: ");
//     Serial.println(signalMin);
// }

// void pullHair() {
//     if (serverControl.isEnabled) {
//         // Control left motor
//         if (serverControl.useLeft) {
//             leftMotor.Drive(serverControl.leftForward, serverControl.power);
//         } else {
//             leftMotor.Drive(true, 0);  // Stop
//         }
        
//         // Control right motor
//         if (serverControl.useRight) {
//             rightMotor.Drive(serverControl.rightForward, serverControl.power);
//         } else {
//             rightMotor.Drive(true, 0);  // Stop
//         }
//     } else {
//         // Stop both motors if disabled
//         leftMotor.Drive(true, 0);
//         rightMotor.Drive(true, 0);
//     }
// }

// void mockServerUpdates() {
//     // Example: Change direction every 3 seconds
//     if (millis() % 3000 < 1500) {
//         serverControl.leftForward = true;
//         serverControl.rightForward = true;
//         myCodeCell.LED(0XA0, 0x60, 0x00U);  // Orange when moving forward
//     } else {
//         serverControl.leftForward = false;
//         serverControl.rightForward = false;
//         myCodeCell.LED(0x60, 0XA0, 0x00U);  // Green-ish when moving backward
//     }
// }

// void loop() {
//     // Process sound input at regular intervals
//     if (millis() - lastSoundCheck >= SAMPLE_WINDOW) {
//         processSoundInput();
//         lastSoundCheck = millis();
//     }
    
//     // Update motor control based on server values
//     mockServerUpdates();
//     // pullHair();
//     if (shouldSqueak){ 
//       playSqueak();  // This will make it squeak continuously
//      }


//     delay(10);  // Small delay to prevent overwhelming the serial output
// }