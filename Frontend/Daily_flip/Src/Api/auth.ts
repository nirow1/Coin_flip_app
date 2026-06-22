import client from './client';

export interface RegisterData{
    username: string;
    email: string;
    password: string;
    country: string;
    dob: string; // ISO format: YYYY-MM-DD
}

export interface TokenResponse {
    token: string;
    token_type: string;
};


export const register = (data: RegisterData) =>
  client.post('/auth/register', data);

export const login = (email: string, password: string) =>
  client.post('/auth/login', { email, password });