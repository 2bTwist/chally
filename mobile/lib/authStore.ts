import * as SecureStore from 'expo-secure-store';

const ACCESS_KEY = 'chally.access';
const REFRESH_KEY = 'chally.refresh';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export async function loadTokens() {
  accessToken = (await SecureStore.getItemAsync(ACCESS_KEY)) ?? null;
  refreshToken = (await SecureStore.getItemAsync(REFRESH_KEY)) ?? null;
}

export function getAccessToken() {
  return accessToken;
}

export function getRefreshToken() {
  return refreshToken;
}

export async function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  await SecureStore.setItemAsync(ACCESS_KEY, access);
  await SecureStore.setItemAsync(REFRESH_KEY, refresh);
}

export async function clearTokens() {
  accessToken = null;
  refreshToken = null;
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}
