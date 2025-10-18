import { api } from './api';
import { setTokens, clearTokens } from './authStore';

export type TokenPair = { access: string; refresh: string };
export type UserPublic = { id: string; email: string; username: string; created_at: string };

export async function login(email: string, password: string): Promise<UserPublic> {
  const response = await api.post('/auth/login', { email, password });
  const { access, refresh } = response.data;
  
  // Ensure tokens are strings
  if (typeof access !== 'string' || typeof refresh !== 'string') {
    throw new Error('Invalid token format received from server');
  }
  
  await setTokens(access, refresh);
  const me = await api.get<UserPublic>('/auth/me');
  return me.data;
}

export async function register(username: string, email: string, password: string): Promise<UserPublic> {
  // Register returns UserPublic (just user info, no tokens)
  const response = await api.post<UserPublic>('/auth/register', { username, email, password });
  return response.data;
}

export async function logout() {
  await clearTokens();
}
