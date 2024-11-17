import { CameraView, CameraType, useCameraPermissions } from 'expo-camera';
import { useState, useEffect, useRef } from 'react';
import { Button, StyleSheet, Text, TouchableOpacity, View, ScrollView } from 'react-native';
import * as FileSystem from 'expo-file-system';

type AnalysisResponse = {
  status?: string;
  prompt?: string;
  model?: string;
  processing_time?: number;
  analysis?: {
    model: string;
    created_at: string;
    message: {
      role: string;
      content: string;
    };
    total_duration?: number;
  };
  error?: string;
};

export default function App() {
  const [facing, setFacing] = useState<CameraType>('back');
  const [permission, requestPermission] = useCameraPermissions();
  const [isCapturing, setIsCapturing] = useState(false);
  const [ollamaResponse, setOllamaResponse] = useState<AnalysisResponse | null>(null);
  const [openAIResponse, setOpenAIResponse] = useState<AnalysisResponse | null>(null);
  const cameraRef = useRef(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  const startPeriodicCapture = async () => {
    setIsCapturing(true);
    intervalRef.current = setInterval(captureAndAnalyze, 100000);
    captureAndAnalyze(); // Initial capture
  };

  const stopPeriodicCapture = () => {
    setIsCapturing(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  const analyzeWithEndpoint = async (formData: FormData, endpoint: string): Promise<AnalysisResponse> => {
    const response = await fetch(`https://c6bd-99-209-235-170.ngrok-free.app/${endpoint}`, {
      method: 'POST',
      body: formData,
      headers: {
        'Accept': 'application/json',
      },
    });

    const responseText = await response.text();
    if (!response.ok) {
      throw new Error(`Failed to analyze image: ${response.status} ${responseText}`);
    }

    return JSON.parse(responseText);
  };

  const captureAndAnalyze = async () => {
    if (!cameraRef.current) return;

    try {
      const photo = await (cameraRef.current as CameraView).takePictureAsync({
        quality: 0.7,
      });

      const fileInfo = await FileSystem.getInfoAsync(photo?.uri || '');
      const fileData = {
        uri: photo?.uri || '',
        type: 'image/jpeg',
        name: 'photo.jpg',
        size: fileInfo.size
      } as any;

      // Create FormData instances for both requests
      const ollamaFormData = new FormData();
      const openAIFormData = new FormData();
      ollamaFormData.append('file', fileData);
      openAIFormData.append('file', fileData);

      // Make parallel requests to both endpoints
      const [ollamaResult, openAIResult] = await Promise.all([
        analyzeWithEndpoint(ollamaFormData, 'analyze-image'),
        analyzeWithEndpoint(openAIFormData, 'analyze-image-openai')
      ]);

      setOllamaResponse(ollamaResult);
      setOpenAIResponse(openAIResult);

    } catch (error) {
      console.error('Error capturing/analyzing image:', error);
      const errorResponse = {
        status: 'error',
        error: (error as Error).message || 'Error analyzing image'
      };
      setOllamaResponse(errorResponse);
      setOpenAIResponse(errorResponse);
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const ModelResponse = ({ response, title }: { response: AnalysisResponse | null, title: string }) => {
    if (!response) return null;

    return (
      <View style={styles.modelResponseContainer}>
        <Text style={styles.modelTitle}>{title}</Text>
        
        {response.status === 'error' ? (
          <Text style={styles.errorText}>{response.error}</Text>
        ) : (
          <>
            <View style={styles.timingContainer}>
              <Text style={styles.timingText}>
                Total Processing Time: {formatDuration(response.processing_time || 0)}
              </Text>
              {response.analysis?.total_duration && (
                <Text style={styles.timingText}>
                  Model Time: {formatDuration(response.analysis.total_duration / 1e6)}
                </Text>
              )}
            </View>

            <View style={styles.responseContent}>
              <Text style={styles.label}>Model:</Text>
              <Text style={styles.value}>{response.analysis?.model}</Text>

              <Text style={styles.label}>Analysis:</Text>
              <Text style={styles.value}>
                {response.analysis?.message.content}
              </Text>
            </View>
          </>
        )}
      </View>
    );
  };

  if (!permission) return <View />;

  if (!permission.granted) {
    return (
      <View style={styles.container}>
        <Text style={styles.message}>We need your permission to show the camera</Text>
        <Button onPress={requestPermission} title="grant permission" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView 
        ref={cameraRef}
        style={styles.camera} 
        facing={facing}
      >
        <View style={styles.buttonContainer}>
          <TouchableOpacity style={styles.button} onPress={() => setFacing(current => (current === 'back' ? 'front' : 'back'))}>
            <Text style={styles.text}>Flip Camera</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.button, isCapturing ? styles.activeButton : {}]} 
            onPress={isCapturing ? stopPeriodicCapture : startPeriodicCapture}
          >
            <Text style={styles.text}>
              {isCapturing ? 'Stop Capture' : 'Start Capture'}
            </Text>
          </TouchableOpacity>
        </View>
      </CameraView>

      <ScrollView style={styles.responseContainer}>
        <View style={styles.responseHeader}>
          <Text style={styles.responseTitle}>Model Comparison</Text>
          {isCapturing && (
            <Text style={styles.captureStatus}>
              Next capture in: {100 - (Math.floor(Date.now() / 1000) % 100)}s
            </Text>
          )}
        </View>

        <ModelResponse title="Ollama" response={ollamaResponse} />
        <ModelResponse title="OpenAI" response={openAIResponse} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  message: {
    textAlign: 'center',
    paddingBottom: 10,
  },
  camera: {
    flex: 0.5,
  },
  buttonContainer: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: 'transparent',
    margin: 64,
  },
  button: {
    flex: 1,
    alignSelf: 'flex-end',
    alignItems: 'center',
    padding: 10,
  },
  activeButton: {
    backgroundColor: 'rgba(255, 0, 0, 0.3)',
    borderRadius: 10,
  },
  text: {
    fontSize: 24,
    fontWeight: 'bold',
    color: 'white',
  },
  responseContainer: {
    flex: 0.5,
    backgroundColor: '#f5f5f5',
    padding: 15,
  },
  responseHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  responseTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  captureStatus: {
    fontSize: 14,
    color: '#666',
  },
  modelResponseContainer: {
    marginBottom: 20,
    backgroundColor: 'white',
    borderRadius: 10,
    padding: 10,
  },
  modelTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 10,
  },
  timingContainer: {
    backgroundColor: '#e0e0e0',
    padding: 10,
    borderRadius: 5,
    marginBottom: 10,
  },
  timingText: {
    fontSize: 12,
    color: '#444',
  },
  responseContent: {
    padding: 5,
  },
  label: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#444',
    marginTop: 10,
  },
  value: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
  },
  errorText: {
    color: 'red',
    fontSize: 16,
    padding: 10,
  }
});