import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { login as apiLogin, register as apiRegister, RegisterData } from '../Api/auth';

interface User {
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await apiLogin(email, password);
      
      const { access_token } = res.data;
      
      localStorage.setItem('token', access_token);
      setToken(access_token);
      
      const payload = JSON.parse(atob(access_token.split('.')[1]));
      
      setUser({ email: payload.sub });
    } catch (err: any) {
      console.error("Login failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: RegisterData) => {
    try{
      const res = await apiRegister(data);
      
    }catch(err: any){
      console.error("Register failed:", err);
    }
  };
  
  return (
    <AuthContext.Provider value={{ user, token, isLoading, login }}>
      {children}
    </AuthContext.Provider>
  );
}