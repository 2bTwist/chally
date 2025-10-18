import axios from 'axios';
import { API_BASE_URL, getTimezone } from './env';
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './authStore';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// ----- REQUEST interceptor: add default headers + bearer -----
api.interceptors.request.use(async (config) => {
  config.headers = config.headers ?? {};
  config.headers['Accept'] = 'application/json';
  config.headers['Content-Type'] = 'application/json';
  config.headers['X-Client-Timezone'] = getTimezone();

  const access = getAccessToken();
  if (access) config.headers['Authorization'] = `Bearer ${access}`;
  return config;
});

// ----- RESPONSE interceptor: 401 -> refresh once, then retry -----
let refreshing = false;
let queue: Array<{ resolve: (t: string | null) => void }> = [];

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  if (refreshing) {
    return new Promise((resolve) => queue.push({ resolve }));
  }

  refreshing = true;
  try {
    const res = await axios.post<{ access: string; refresh: string }>(
      `${API_BASE_URL}/auth/refresh`,
      null,
      { headers: { Authorization: `Bearer ${refresh}` } }
    );
    await setTokens(res.data.access, res.data.refresh);
    queue.forEach((q) => q.resolve(res.data.access));
    queue = [];
    return res.data.access;
  } catch {
    await clearTokens();
    queue.forEach((q) => q.resolve(null));
    queue = [];
    return null;
  } finally {
    refreshing = false;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error?.response?.status;
    const original = error?.config ?? {};
    const url: string = original?.url || '';

    // avoid loops on login/refresh endpoints
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh');

    if (status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const newAccess = await refreshAccessToken();
      if (newAccess) {
        original.headers = original.headers ?? {};
        original.headers['Authorization'] = `Bearer ${newAccess}`;
        return api.request(original);
      }
    }
    return Promise.reject(error);
  }
);

// ----------- small helper used by /health screen -----------
export type HealthResponse = {
  status: string;
  env: string;
  time: string;
  request_id: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await api.get<HealthResponse>('/health');
  return res.data;
}