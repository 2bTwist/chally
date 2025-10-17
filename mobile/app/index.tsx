import { Redirect } from 'expo-router';

export default function Index() {
  // Redirect to auth/sign-in on app load
  return <Redirect href="/auth/sign-in" />;
}
