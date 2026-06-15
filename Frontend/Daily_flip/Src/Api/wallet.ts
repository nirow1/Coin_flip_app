import client from './client';

export interface BalanceResponse {
    balance: number;
}

export const getBalance = () =>
  client.get<BalanceResponse>('/wallet/balance');