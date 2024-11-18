import React, { useState, useEffect, useRef } from 'react';
import { Audio, InterruptionModeIOS, InterruptionModeAndroid } from 'expo-av';
import * as Speech from 'expo-speech';
import { StyleSheet, View, Text, ScrollView, Pressable } from 'react-native';
import * as FileSystem from 'expo-file-system';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

interface ProcessingStatus {
  transcribing: boolean;
  generating: boolean;
  speaking: boolean;
}

// Configuration
const ELEVEN_LABS_API_KEY = "sk_53d147734d29301d6076fb1feec28f76ef8650f4cd13a9b7";
const VOICE_ID = "nXUMivg97yAaSqlaJWJG";
const SERVER_URL = 'https://8a28-99-209-235-170.ngrok-free.app';

const PUB_SUB_SERVER_URL = "https://bratatouille-bot.fly.dev/test"

// Add audio mode configuration constants
const AUDIO_MODE = {
  allowsRecordingIOS: false,
  playsInSilentModeIOS: true,
  staysActiveInBackground: false,
  interruptionModeIOS: InterruptionModeIOS.DoNotMix,
  interruptionModeAndroid: InterruptionModeAndroid.DoNotMix,
  shouldDuckAndroid: false,
  playThroughEarpieceAndroid: false
};

const RECORDING_MODE = {
  ...AUDIO_MODE,
  allowsRecordingIOS: true,
  staysActiveInBackground: true,
};

// Add configuration constants
const ELEVEN_LABS_CONFIG = {
  baseUrl: 'https://api.elevenlabs.io/v1/text-to-speech',
  headers: {
    'Content-Type': 'application/json',
    'xi-api-key': ELEVEN_LABS_API_KEY
  }
};

// Add this new function to handle the LED request
const sendMotionRequest = async () => {
  try {
    const response = await fetch(PUB_SUB_SERVER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        right: true,
        left: true
      })
    });

    if (!response.ok) {
      console.error('motion request failed:', response.status);
    }
  } catch (error) {
    console.error('Error sending motion request:', error);
  }
};

export default function VoiceChat() {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [status, setStatus] = useState('Tap to start');
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [permission, setPermission] = useState<Audio.PermissionResponse>();
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>({
    transcribing: false,
    generating: false,
    speaking: false,
  });
  const [sessionId, setSessionId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);

  useEffect(() => {
    const initialize = async () => {
      await checkPermissions();
      await loadSession();
      await fetchChatHistory();
    };
    
    initialize();
    
    return () => {
      cleanup();
    };
  }, []);

  const loadSession = async () => {
    setSessionId(new Date().toISOString());
  };

  const fetchChatHistory = async () => {
    if (!sessionId) return;
    
    try {
      const response = await fetch(`${SERVER_URL}/cooking/chat-history/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.chat_history) {
          setChatHistory(data.chat_history);
        }
      }
    } catch (error) {
      console.error('Error fetching chat history:', error);
    }
  };

  const cleanup = async () => {
    try {
      if (recording) {
        await recording.stopAndUnloadAsync();
        setRecording(null);
      }
      
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
      }
      
      await Speech.stop();
      
      // Clean up audio directory
      const audioDir = `${FileSystem.cacheDirectory}audio/`;
      await FileSystem.deleteAsync(audioDir, { idempotent: true })
        .catch(console.error);
      
      setIsListening(false);
    } catch (error) {
      console.error('Error in cleanup:', error);
    }
  };

  const checkPermissions = async () => {
    try {
      const permission = await Audio.getPermissionsAsync();
      setPermission(permission);
      
      if (!permission.granted) {
        const newPermission = await Audio.requestPermissionsAsync();
        setPermission(newPermission);
        
        if (!newPermission.granted) {
          setStatus('No permission for audio');
          return false;
        }
      }
      
      await configureAudio();
      return true;
    } catch (error) {
      console.error('Error checking permissions:', error);
      setStatus('Permission check failed');
      return false;
    }
  };

  const configureAudio = async (mode: 'recording' | 'playback') => {
    try {
      await Audio.setAudioModeAsync(
        mode === 'recording' ? RECORDING_MODE : AUDIO_MODE
      );
    } catch (error) {
      console.error('Error configuring audio:', error);
      setStatus('Audio configuration failed');
    }
  };

  const transcribeAudio = async (uri: string) => {
    setProcessingStatus(prev => ({ ...prev, transcribing: true }));
    try {
      const formData = new FormData();
      formData.append('file', {
        uri: uri,
        type: 'audio/m4a',
        name: 'recording.m4a',
      } as any);

      const response = await fetch(`${SERVER_URL}/audio/speech-to-text`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Transcription failed with status ${response.status}`);
      }

      const data = await response.json();
      return data.transcription;
    } finally {
      setProcessingStatus(prev => ({ ...prev, transcribing: false }));
    }
  };

  const generateResponse = async (transcription: string) => {
    setProcessingStatus(prev => ({ ...prev, generating: true }));
    try {
      const response = await fetch(`${SERVER_URL}/cooking/generate-response`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          transcription,
          session_id: sessionId 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(
          `Response generation failed with status ${response.status}: ${
            errorData ? JSON.stringify(errorData) : 'Unknown error'
          }`
        );
      }

      const data = await response.json();
      if (data.chat_history) {
        setChatHistory(data.chat_history);
      }
      return data.response;
    } finally {
      setProcessingStatus(prev => ({ ...prev, generating: false }));
    }
  };

  const speakWithElevenLabs = async (text: string) => {
    setProcessingStatus(prev => ({ ...prev, speaking: true }));
    let audioPath: string | null = null;

    try {
      await configureAudio('playback');

      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }

      const response = await fetch(
        `${ELEVEN_LABS_CONFIG.baseUrl}/${VOICE_ID}`,
        {
          method: 'POST',
          headers: ELEVEN_LABS_CONFIG.headers,
          body: JSON.stringify({
            text,
            model_id: 'eleven_turbo_v2_5',
            voice_settings: {
              stability: 0.5,
              similarity_boost: 0.5
            }
          })
        }
      );

      if (!response.ok) {
        throw new Error(`ElevenLabs API error: ${response.status}`);
      }

      // Create audio directory if it doesn't exist
      const audioDir = `${FileSystem.cacheDirectory}audio/`;
      await FileSystem.makeDirectoryAsync(audioDir, { intermediates: true })
        .catch(() => {});

      // Save audio file
      audioPath = `${audioDir}response_${Date.now()}.mp3`;
      const audioBlob = await response.blob();
      const reader = new FileReader();
      await sendMotionRequest();
      await new Promise((resolve, reject) => {
        reader.onload = async () => {
          try {
            const base64Data = reader.result?.toString().split(',')[1];
            await FileSystem.writeAsStringAsync(
              audioPath!,
              base64Data!,
              { encoding: FileSystem.EncodingType.Base64 }
            );
            resolve(undefined);
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = reject;
        reader.readAsDataURL(audioBlob);
      });

      // Play the audio
      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: audioPath },
        { shouldPlay: true },
        (playbackStatus) => {
          if (playbackStatus.isLoaded) {
            console.log('Audio playback progress:', playbackStatus.positionMillis);
          }
        }
      );

      soundRef.current = newSound;

      // Wait for playback to finish
      await new Promise((resolve, reject) => {
        newSound.setOnPlaybackStatusUpdate(async (status: any) => {
          if (status.didJustFinish) {
            try {
              await newSound.unloadAsync();
              if (audioPath) {
                await FileSystem.deleteAsync(audioPath);
              }
              soundRef.current = null;
              await configureAudio('recording');
              resolve(undefined);
            } catch (error) {
              reject(error);
            }
          } else if (status.error) {
            reject(new Error('Playback error'));
          }
        });
      });

    } catch (error) {
      console.error('Error in speech synthesis:', error);
      
      if (audioPath) {
        await FileSystem.deleteAsync(audioPath).catch(console.error);
      }
      
      // Fallback to system speech
      // try {
      //   await configureAudio('playback');
      //   await Speech.speak(text, {
      //     voice: "com.apple.speech.synthesis.voice.karen",
      //     pitch: 1.0,
      //     rate: 0.9,
      //     volume: 1.0,
      //   });
      // } catch (fallbackError) {
      //   console.error('Fallback speech failed:', fallbackError);
      // }
    } finally {
      setProcessingStatus(prev => ({ ...prev, speaking: false }));
    }
  };

  const startRecording = async () => {
    try {
      if (!permission?.granted) {
        const hasPermission = await checkPermissions();
        if (!hasPermission) return;
      }
  
      await cleanup();
      await configureAudio('recording');
      
      const newRecording = new Audio.Recording();
      await newRecording.prepareToRecordAsync({
        android: {
          extension: '.m4a',
          outputFormat: Audio.AndroidOutputFormat.MPEG_4,
          audioEncoder: Audio.AndroidAudioEncoder.AAC,
          sampleRate: 44100,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        ios: {
          extension: '.m4a',
          outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
          audioQuality: Audio.IOSAudioQuality.HIGH,
          sampleRate: 44100,
          numberOfChannels: 1,
          bitRate: 128000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
        web: {
          mimeType: 'audio/webm',
          bitsPerSecond: 128000,
        },
      });
      
      await newRecording.startAsync();
      setRecording(newRecording);
      setIsListening(true);
      setStatus('Recording...');
    } catch (error) {
      console.error('Error in startRecording:', error);
      setStatus('Failed to start recording');
    }
  };

  const stopRecording = async () => {
    if (!recording) return;

    try {
      setStatus('Processing...');
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      
      if (!uri) {
        throw new Error('No recording URI available');
      }

      const fileInfo = await FileSystem.getInfoAsync(uri);
      if (!fileInfo.exists || fileInfo.size === 0) {
        throw new Error('Recording file is empty or does not exist');
      }

      const transcription = await transcribeAudio(uri);
      const aiResponse = await generateResponse(transcription);
      await speakWithElevenLabs(aiResponse);
      
    } catch (error) {
      console.error('Error processing recording:', error);
      setStatus('Processing failed');
    } finally {
      setRecording(null);
      setIsListening(false);
      setStatus('Tap to start');
    }
  };

  const toggleRecording = async () => {
    if (isListening) {
      await stopRecording();
    } else {
      await startRecording();
    }
  };

  const getStatusText = () => {
    if (processingStatus.transcribing) return 'Transcribing...';
    if (processingStatus.generating) return 'Generating response...';
    if (processingStatus.speaking) return 'Speaking...';
    return status;
  };

  if (!permission?.granted) {
    return (
      <View style={styles.container}>
        <Pressable 
          style={styles.controlButton}
          onPress={checkPermissions}
        >
          <Text style={styles.statusText}>Grant Audio Permission</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Pressable 
        style={[styles.controlButton, isListening && styles.activeButton]}
        onPress={toggleRecording}
      >
        <Text style={styles.statusText}>{getStatusText()}</Text>
        <View style={[styles.indicator, { backgroundColor: isListening ? '#4CAF50' : '#757575' }]} />
      </Pressable>

      <ScrollView style={styles.chatContainer}>
        {chatHistory.map((message, index) => (
          <View 
            key={index} 
            style={[
              styles.messageContainer,
              message.role === 'user' ? styles.userMessage : styles.assistantMessage
            ]}
          >
            <Text style={styles.messageText}>{message.content}</Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(245, 245, 245, 0.95)',
    maxHeight: '30%',
    minHeight: 100,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 10,
    shadowColor: '#000',
    shadowOffset: {
      width: 0,
      height: -2,
    },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
  },
  controlButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 10,
    backgroundColor: 'white',
    borderRadius: 10,
    marginBottom: 10,
  },
  activeButton: {
    backgroundColor: '#E8F5E9',
  },
  statusText: {
    fontSize: 14,
    color: '#333',
  },
  indicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  chatContainer: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  messageContainer: {
    padding: 8,
    marginVertical: 4,
    borderRadius: 8,
    maxWidth: '80%',
  },
  userMessage: {
    alignSelf: 'flex-end',
    backgroundColor: '#DCF8C6',
  },
  assistantMessage: {
    alignSelf: 'flex-start',
    backgroundColor: '#E8E8E8',
  },
  messageText: {
    fontSize: 12,
    color: '#333',
  },
});