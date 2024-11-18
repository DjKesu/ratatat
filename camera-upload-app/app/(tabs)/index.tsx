import { View, StyleSheet } from 'react-native';
import CameraComponent from '../../components/CameraComponent';
import VoiceChat from '../../components/VoiceChat';

export default function TabOneScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.cameraContainer}>
        <CameraComponent />
      </View>
      <VoiceChat />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  cameraContainer: {
    flex: 1,
  },
});