import axios, { InternalAxiosRequestConfig } from 'axios';

const client = axios.create({ baseURL: 'http://localhost:8000' });

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export default client;