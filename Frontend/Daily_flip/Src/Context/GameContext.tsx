import { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { getBalance } from '../Api/game';
import { AuthContext } from './AuthContext';

export const GameContext = React.createContext({
  balance: number|null,
  refreshBalance: () => Promise<void>,
});

export function GameProvider({ children }: { children: React.ReactNode }) {
  const [gameState, setGameState] = useState({
    currentGame: null,
    gameHistory: [],
    isLoading: false,
  });