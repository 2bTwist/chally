import { Platform } from 'react-native';

const raw = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

// Ensure no trailing slashes & fix Android emulator localhost.
function normalize(url: string) {
  let u = url.replace(/\/+$/, '');
  if (Platform.OS === 'android' && /(^|\/\/)localhost(?=[:/]|$)/.test(u)) {
    u = u.replace('localhost', '10.0.2.2');
  }
  return u;
}

export const API_BASE_URL = normalize(raw);
export const isDev = __DEV__;

export function getTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}