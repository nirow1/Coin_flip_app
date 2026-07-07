import client from './client';

export interface BalanceResponse {
    balance: number;
}

export const getBalance = () => {
  const token = localStorage.getItem('token');

  return client.get<BalanceResponse>('/wallet/balance', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
};