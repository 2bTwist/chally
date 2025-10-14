import axios from 'axios';
import { API_BASE_URL, getTimezone } from './env';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Add default headers per request (keeps simple until Step 3 token handling)
api.interceptors.request.use((config) => {
  // Ensure headers object exists
  config.headers = config.headers || {};
  
  // Set headers individually
  config.headers['Accept'] = 'application/json';
  config.headers['Content-Type'] = 'application/json';
  config.headers['X-Client-Timezone'] = getTimezone();
  
  return config;
});

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