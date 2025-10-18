import { api } from './api';
import { setTokens, clearTokens } from './authStore';

export type TokenPair = { access: string; refresh: string };
export type UserPublic = { id: string; email: string; username: string; created_at: string };

export async function login(email: string, password: string): Promise<UserPublic> {
  const tp = await api.post<TokenPair>('/auth/login', { email, password });
  await setTokens(tp.data.access, tp.data.refresh);
  const me = await api.get<UserPublic>('/auth/me');
  return me.data;
}

export async function logout() {
  await clearTokens();
}
