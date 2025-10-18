import { useState } from 'react';
import { Image, Keyboard, KeyboardAvoidingView, Platform, ScrollView, TextInput, TouchableWithoutFeedback, View } from 'react-native';
import { Link, router } from 'expo-router';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Button } from '@/components/ui/Button';
import { login } from '@/lib/auth';

export default function SignIn() {
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setLoading(true);
    setErr(null);
    try {
      await login(email.trim(), pw);
      router.replace('/(app)' as any);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Sign-in failed';
      setErr(typeof msg === 'string' ? msg : 'Sign-in failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen className="px-6">
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} className="flex-1">
        <TouchableWithoutFeedback onPress={Keyboard.dismiss}>
          <ScrollView 
            contentContainerStyle={{ flexGrow: 1 }}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            <View className="flex-1 items-center justify-start pt-16">
              {/* Logo */}
              <Image
                source={require('@/assets/images/icon.png')}
                style={{ width: 56, height: 56, borderRadius: 28, marginBottom: 24 }}
              />

              {/* Title */}
              <Text variant="title" className="mb-2">Chally</Text>
              <Text variant="caption" className="mb-8">Stay accountable with your community</Text>

          {/* Grouped inputs */}
          <View className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 overflow-hidden mb-5">
            <View className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
              <Text variant="caption" className="mb-1 text-neutral-600 dark:text-neutral-400">Email</Text>
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="Enter your email"
                placeholderTextColor="#9ca3af"
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                className="p-0 text-base text-neutral-900 dark:text-neutral-100"
              />
            </View>
            <View className="px-4 py-3">
              <Text variant="caption" className="mb-1 text-neutral-600 dark:text-neutral-400">Password</Text>
              <TextInput
                value={pw}
                onChangeText={setPw}
                placeholder="Enter your password"
                placeholderTextColor="#9ca3af"
                secureTextEntry
                className="p-0 text-base text-neutral-900 dark:text-neutral-100"
              />
            </View>
          </View>

          {err ? <Text className="text-red-600 mb-3">{err}</Text> : null}

          {/* CTA */}
          <Button
            label={loading ? 'Signing in…' : 'Sign In'}
            onPress={onSubmit}
            disabled={loading || !email || !pw}
            className="w-full max-w-md bg-neutral-900 dark:bg-neutral-50 rounded-2xl py-4"
          />

              {/* Link */}
              <Link href="/(auth)/sign-up" asChild>
                <Text className="mt-6 text-base">Don't have an account? <Text className="font-semibold">Sign up</Text></Text>
              </Link>
            </View>
          </ScrollView>
        </TouchableWithoutFeedback>
      </KeyboardAvoidingView>
    </Screen>
  );
}
