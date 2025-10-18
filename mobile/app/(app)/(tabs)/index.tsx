import { StyleSheet } from 'react-native';
import { router } from 'expo-router';

import EditScreenInfo from '@/components/EditScreenInfo';
import { Text as ThemedText, View } from '@/components/Themed';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { logout } from '@/lib/auth';

export default function TabOneScreen() {
  const handleLogout = async () => {
    await logout();
    router.replace('/(auth)/sign-in' as any);
  };

  return (
    <View style={styles.container}>
      <ThemedText style={styles.title}>Chally</ThemedText>
      <View style={styles.separator} lightColor="#eee" darkColor="rgba(255,255,255,0.1)" />
      
      {/* Navigation Card */}
      <Card className="mb-4 w-full max-w-sm">
        <Text variant="subtitle" className="mb-3 text-center">Quick Navigation</Text>
        <View className="gap-3">
          <Button 
            label="🩺 API Health"
            onPress={() => router.push('/health' as any)}
            className="w-full"
          />
          <Button 
            label="� Sign Out"
            variant="outline"
            onPress={handleLogout}
            className="w-full"
          />
        </View>
      </Card>
      
      <EditScreenInfo path="app/(app)/(tabs)/index.tsx" />
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
