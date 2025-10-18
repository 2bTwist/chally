import { StyleSheet } from 'react-native';
import { router } from 'expo-router';

import { View } from '@/components/Themed';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Text } from '@/components/ui/Text';
import { Screen } from '@/components/ui/Screen';
import { logout } from '@/lib/auth';

export default function HomeScreen() {
  const handleLogout = async () => {
    await logout();
    router.replace('/(auth)/sign-in' as any);
  };

  return (
    <Screen>
      <View style={styles.container}>
        <Text variant="title" className="mb-2">Welcome to Chally</Text>
        <Text variant="body" className="mb-8 text-center px-6">
          Stay accountable with your community
        </Text>
        
        <Card className="mb-4 w-full max-w-sm">
          <Text variant="subtitle" className="mb-3 text-center">Quick Actions</Text>
          <View className="gap-3">
            <Button 
              label="🩺 API Health"
              onPress={() => router.push('/health' as any)}
              className="w-full"
            />
            <Button 
              label="🚪 Sign Out"
              variant="outline"
              onPress={handleLogout}
              className="w-full"
            />
          </View>
        </Card>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
});
