import { createContext, useState, ReactNode, useEffect } from 'react';
import { login as apiLogin, register as apiRegister, RegisterData, getMe as apiGetMe, logout as apiLogout } from '../Api/auth';

interface User {
  email: string;
}

interface AuthContextType {
  user: User | null;
  /** True while restoring session from cookie on app start. */
  isInitializing: boolean;
  /** True while login/register request is in flight. */
  isLoading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  getMe: () => Promise<void>;
  register: (data: RegisterData) => Promise<boolean>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isLoading, setIsLoading] = useState(false);

  const login = async (email: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      const res = await apiLogin(email, password);

      if (res.data.ok) {
        setUser({ email });
        return true;
      }
      return false;
    } catch (err) {
      console.error("Login failed:", err);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const getMe = async () => {
    setIsInitializing(true);
    try {
      const res = await apiGetMe();
      setUser({ email: res.data.email });
    } catch (err) {
      console.error("Get me failed:", err);
      setUser(null);
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    getMe();
  }, []);

  const register = async (data: RegisterData): Promise<boolean> => {
    setIsLoading(true);
    try {
      const res = await apiRegister(data);
      return res != null;
    } catch (err) {
      console.error("Register failed:", err);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, isInitializing, isLoading, login, getMe, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
