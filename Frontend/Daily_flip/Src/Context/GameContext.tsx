import { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { getBalance } from '../Api/wallet';
import { AuthContext } from './AuthContext';

export const GameContext = createContext({
  balance: null as number | null,
  refreshBalance: async () => {},
});

export function GameProvider({ children }: { children: React.ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null);

  const refreshBalance = async () => {
    try {
      const res = await getBalance();
      setBalance(res.data.balance);
    } catch (err) {
      console.error("Failed to fetch balance:", err);
    }
  };

  useEffect(() => {
    refreshBalance();
  }, []);

  return (
    <GameContext.Provider value={{ balance, refreshBalance }}>
      {children}
    </GameContext.Provider>
  );
}