import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
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

  if (!ready) return null;
  return <Redirect href={authed ? '/(app)' : '/(auth)/sign-in'} />;
}
