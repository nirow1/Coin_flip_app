import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,
});

client.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toLowerCase();
  if (!UNSAFE.has(method)) return config;
  const csrf = getCookie('csrf_token');
  if (!csrf) return config; // login/register: no cookie yet → don't set header
  config.headers.set('X-CSRF-Token', csrf);
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status !== 401) {
      return Promise.reject(error);
    }

    const config = error.config;
    if (!config){
      return Promise.reject(error);
    }

    type RetryConfig = typeof config & { _retried?: boolean };
    const url = config.url?? '';
    const skipRefresh =
    url.includes('/auth/login') ||
    url.includes('/auth/register') ||
    url.includes('/auth/refresh') ||
    url.includes('/auth/me');
    if (skipRefresh) {
      return Promise.reject(error); 
    }

    if (config._retried) {
      onAuthExpired();
      return Promise.reject(error);
    }

    try{
      await refreshOnce();
      config._retried = true;
      return client.request(config);
    } catch (refreshError) {
      onAuthExpired();
      return Promise.reject(refreshError);
    }    
  }
);

let refreshPromise: Promise<unknown> | null = null;

function refreshOnce() {
  if (!refreshPromise) {
    // call client directly — avoid importing auth.ts (circular import)
    refreshPromise = client.post('/auth/refresh').finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const UNSAFE = new Set(['post', 'put', 'patch', 'delete']);

function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=([^;]*)`)
  );
  return match ? decodeURIComponent(match[1]) : null;
}

let onAuthExpired: () => void = () => {};

export const setOnAuthExpired = (cb: () => void) => {
  onAuthExpired = cb;
};

export default client;
