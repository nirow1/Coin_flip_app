import client from './client';

export interface GameResponse {
  id: number;
  status: string;
  start_date: string;
  flip_time: string;
  prize_pool: number;
  current_player_count: number;
  initial_player_count: number | null;
}

export const getOpenGame = () => client.get<GameResponse>('/game/open');
