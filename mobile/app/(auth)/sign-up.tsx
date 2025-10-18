import { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, TextInput, View } from 'react-native';
import { Link, router } from 'expo-router';
import { Screen } from '@/components/ui/Screen';
import { Text } from '@/components/ui/Text';
import { Button } from '@/components/ui/Button';
import { register } from '@/lib/auth';
import { validateEmail, validateUsername, validatePassword, validatePasswordMatch } from '@/lib/validation';

export default function SignUp() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setLoading(true);
    setErr(null);

    // Validate inputs
    const usernameErr = validateUsername(username);
    if (usernameErr) {
      setErr(usernameErr);
      setLoading(false);
      return;
    }

    const emailErr = validateEmail(email);
    if (emailErr) {
      setErr(emailErr);
      setLoading(false);
      return;
    }

    const passwordErr = validatePassword(pw);
    if (passwordErr) {
      setErr(passwordErr);
      setLoading(false);
      return;
    }

    const matchErr = validatePasswordMatch(pw, confirmPw);
    if (matchErr) {
      setErr(matchErr);
      setLoading(false);
      return;
    }

    try {
      await register(username.trim(), email.trim(), pw);
      // Successfully registered - navigate to sign-in
      router.replace('/(auth)/sign-in' as any);
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? 'Sign-up failed';
      setErr(typeof msg === 'string' ? msg : 'Sign-up failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen className="px-6">
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} className="flex-1">
        <View className="flex-1 items-center justify-start pt-16">
          {/* Logo */}
          <Image
            source={require('@/assets/images/icon.png')}
            style={{ width: 56, height: 56, borderRadius: 28, marginBottom: 24 }}
          />

          {/* Title */}
          <Text variant="title" className="mb-2">Chally</Text>
          <Text variant="caption" className="mb-8">Join and start challenging yourself</Text>

          {/* Grouped inputs */}
          <View className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 overflow-hidden mb-5">
            <View className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
              <Text variant="caption" className="mb-1 text-neutral-600 dark:text-neutral-400">Username</Text>
              <TextInput
                value={username}
                onChangeText={setUsername}
                placeholder="Choose a username"
                placeholderTextColor="#9ca3af"
                autoCapitalize="none"
                autoCorrect={false}
                className="p-0 text-base text-neutral-900 dark:text-neutral-100"
              />
            </View>
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
            <View className="px-4 py-3 border-b border-neutral-200 dark:border-neutral-800">
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
            <View className="px-4 py-3">
              <Text variant="caption" className="mb-1 text-neutral-600 dark:text-neutral-400">Confirm Password</Text>
              <TextInput
                value={confirmPw}
                onChangeText={setConfirmPw}
                placeholder="Re-enter your password"
                placeholderTextColor="#9ca3af"
                secureTextEntry
                className="p-0 text-base text-neutral-900 dark:text-neutral-100"
              />
            </View>
          </View>

          {err ? <Text className="text-red-600 mb-3">{err}</Text> : null}

          {/* CTA */}
          <Button
            label={loading ? 'Creating account…' : 'Create Account'}
            onPress={onSubmit}
            loading={loading}
            disabled={loading || !username || !email || !pw || !confirmPw}
            className="w-full max-w-md bg-neutral-900 dark:bg-neutral-50 rounded-2xl py-4"
          />

          {/* Link */}
          <Link href="/(auth)/sign-in" asChild>
            <Text className="mt-6 text-base">Already have an account? <Text className="font-semibold">Sign in</Text></Text>
          </Link>
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}
