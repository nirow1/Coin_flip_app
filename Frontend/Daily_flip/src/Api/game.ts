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

export interface GamePlayerResponse {
  id: number;
  game_id: number;
  user_id: number;
  side: string | null;
  cashout_decision: string | null;
  round_number: number;
  is_eliminated: boolean;
}

export interface JoinGameResponse {
  player: GamePlayerResponse;
  game: GameResponse;
}

export const getOpenGame = () => client.get<GameResponse>('/game/open');

export const joinGame = (side: 'heads' | 'tails') =>
  client.post<JoinGameResponse>('/game/join', null, { params: { side } });

export const getCurrentGames = () => client.get<GameResponse[]>('/game/current');
