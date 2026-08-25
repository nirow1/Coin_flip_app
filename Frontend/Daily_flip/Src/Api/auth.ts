import client from './client';

export interface RegisterData{
    username: string;
    email: string;
    password: string;
    country: string;
    dob: string; // ISO format: YYYY-MM-DD
}

export const getMe = () =>
  client.get('/auth/me');

export const logout = () =>
  client.post('/auth/logout');

export const register = (data: RegisterData) =>
  client.post('/auth/register', data);

export const login = (email: string, password: string) =>
  client.post('/auth/login', { email, password });