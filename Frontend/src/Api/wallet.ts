import client from './client';

export interface BalanceResponse {
  balance: number;
}

export interface CreditsQuoteResponse {
  quote_id: string;
  expires_at: string;
  credits: number;
  amount_sol: string;
  lamports: number;
  fee: string;
  price: string;
  price_source: string;
  cluster: string;
}
export interface CreateOrderResponse {
  order_id: number;
  receive_address: string;
  amount_sol: string;
  reference: string;
  memo: string;
  expires_at: string;
  solana_pay_url: string;
}
export interface OrderStatusResponse {
  order_id: number;
  status: string;
  credits: number;
  expires_at: string;
  paid_tx_hash: string | null;
}

export const getBalance = () => client.get<BalanceResponse>('/wallet/balance');

export const createQuote = (credits: number) =>
  client.post<CreditsQuoteResponse>('/wallet/credits/quote', {
    credits,
    chain: 'solana',
  });
  
export const createOrder = (quoteId: string) =>
  client.post<CreateOrderResponse>('/wallet/credits/orders', {
    quote_id: quoteId,
  });

export const getOrder = (orderId: number) =>
  client.get<OrderStatusResponse>(`/wallet/credits/orders/${orderId}`);