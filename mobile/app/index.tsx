import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
import { View, Image, ActivityIndicator } from 'react-native';
import { loadTokens, getAccessToken } from '@/lib/authStore';

export default function Index() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    (async () => {
      await loadTokens();
      setAuthed(!!getAccessToken());
      setReady(true);
    })();
  }, []);

  if (!ready) {
    return (
      <View className="flex-1 items-center justify-center bg-white dark:bg-neutral-950">
        <Image
          source={require('@/assets/images/icon.png')}
          style={{ width: 80, height: 80, borderRadius: 40, marginBottom: 24 }}
        />
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return <Redirect href={(authed ? '/(app)' : '/(auth)/sign-in') as any} />;
}
