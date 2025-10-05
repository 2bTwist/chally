import { StyleSheet } from 'react-native';
import { router } from 'expo-router';
// Force reload

import EditScreenInfo from '@/components/EditScreenInfo';
import { Text as ThemedText, View } from '@/components/Themed';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';

export default function TabOneScreen() {
  return (
    <View style={styles.container}>
      <ThemedText style={styles.title}>PeerPush</ThemedText>
      <View style={styles.separator} lightColor="#eee" darkColor="rgba(255,255,255,0.1)" />
      
      {/* Test Button for NativeWind */}
      <Button
        label="TEST BUTTON - BRIGHT RED"
        className="w-full bg-red-500 p-4 mb-4"
        onPress={() => console.log('Test button pressed')}
      />
      
      {/* Navigation Card */}
      <Card className="mb-4 w-full max-w-sm">
        <Text variant="subtitle" className="mb-3 text-center">Quick Navigation</Text>
        <View className="gap-3">
          <Button 
            label="🎨 Design System"
            onPress={() => router.push('/design-system')}
            className="w-full"
          />
          <Button 
            label="🔐 Auth Mock"
            variant="outline"
            onPress={() => router.push('/auth-mock')}
            className="w-full"
          />
        </View>
      </Card>
      
      <EditScreenInfo path="app/(tabs)/index.tsx" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  separator: {
    marginVertical: 30,
    height: 1,
    width: '80%',
  },
});
