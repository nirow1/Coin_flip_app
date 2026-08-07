import { createContext, useState, useContext, useEffect, type ReactNode } from 'react';
import { getBalance } from '../Api/wallet';
import { getOpenGame, GameResponse } from '../Api/game';
import { AuthContext } from './AuthContext';

interface GameContextType {
  balance: number | null;
  refreshBalance: () => Promise<void>;
  liveGame: GameResponse | null;
  refreshLiveGame: () => Promise<void>;
}

export const GameContext = createContext<GameContextType>({} as GameContextType);

export function GameProvider({ children }: { children: ReactNode }) {
  const { token } = useContext(AuthContext);
  const [balance, setBalance] = useState<number | null>(null);
  const [liveGame, setLiveGame] = useState<GameResponse | null>(null);

  const refreshBalance = async () => {
    try {
      if (!token) {
        setBalance(null);
        return;
      }
      const res = await getBalance();
      setBalance(res.data.balance);
    } catch (err) {
      console.error("Failed to fetch balance:", err);
    }
  };

  const refreshLiveGame = async () => {
    try {
      const res = await getOpenGame();
      setLiveGame(res.data);
    } catch (err) {
      console.error("Failed to fetch live game:", err);
      setLiveGame(null);
    }
  };

  useEffect(() => {
    refreshLiveGame();
  }, []);

  useEffect(() => {
    if (token) {
      refreshBalance();
    } else {
      setBalance(null);
    }
  }, [token]);

  return (
    <GameContext.Provider value={{ balance, refreshBalance, liveGame, refreshLiveGame }}>
      {children}
    </GameContext.Provider>
  );
}
