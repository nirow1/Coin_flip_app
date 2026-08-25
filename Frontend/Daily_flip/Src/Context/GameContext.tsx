import { createContext, useState, useContext, useEffect, type ReactNode } from 'react';
import { getBalance } from '../Api/wallet';
import { getOpenGame, joinGame as joinGameApi, getCurrentGames, GameResponse } from '../Api/game';
import { AuthContext } from './AuthContext';


interface GameContextType {
  balance: number | null;
  refreshBalance: () => Promise<void>;
  liveGame: GameResponse | null;
  refreshLiveGame: () => Promise<void>;
  currentGames: GameResponse[];
  joinGame: (side: "heads" | "tails") => Promise<void>;
  joining: boolean;
  joinError: string | null;
  hasJoined: boolean;
}

export const GameContext = createContext<GameContextType>({} as GameContextType);

export function GameProvider({ children }: { children: ReactNode }) {
  const [balance, setBalance] = useState<number | null>(null);
  const [liveGame, setLiveGame] = useState<GameResponse | null>(null);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [hasJoined, setHasJoined] = useState(false);
  const [currentGames, setCurrentGames] = useState<GameResponse[]>([]);
  const { user, isInitializing } = useContext(AuthContext);

  const refreshBalance = async () => {
    try {
      if (!user) {
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

  const joinGame = async (side: "heads" | "tails") => {
    if (!user) {
      setJoinError("You must be logged in to join a game");
      return;
    }

    setJoining(true);
    setJoinError(null);

    try {
      const res = await joinGameApi(side);
      const game = res.data.game;

      setHasJoined(true);
      setLiveGame(game);
      setCurrentGames((prev) =>
        prev.some((g) => g.id === game.id) ? prev : [...prev, game]
      );
      await refreshBalance();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setJoinError(typeof detail === 'string' ? detail : "Failed to join game");
      console.error("Failed to join game:", err);
    } finally {
      setJoining(false);
    }
  };

  useEffect(() => {
    const load = async () => {
      let open: GameResponse | null = null;
      try {
        const openRes = await getOpenGame();
        open = openRes.data;
        setLiveGame(open);
      } catch (err) {
        console.error("Failed to fetch live game:", err);
        setLiveGame(null);
      }

      if (isInitializing) return;

      if (!user) {
        setBalance(null);
        setCurrentGames([]);
        setHasJoined(false);
        return;
      }

      await refreshBalance();

      try {
        const currentRes = await getCurrentGames();
        setCurrentGames(currentRes.data);
        setHasJoined(open != null && currentRes.data.some((g) => g.id === open.id));
      } catch (err) {
        console.error("Failed to check join status:", err);
        setCurrentGames([]);
        setHasJoined(false);
      }
    };

    load();
  }, [user, isInitializing]);

  return (
    <GameContext.Provider
      value={{
        balance,
        refreshBalance,
        liveGame,
        refreshLiveGame,
        currentGames,
        joinGame,
        joining,
        joinError,
        hasJoined,
      }}
    >
      {children}
    </GameContext.Provider>
  );
}
