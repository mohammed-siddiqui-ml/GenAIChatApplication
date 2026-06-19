import { createContext, useContext, useMemo, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '../types';
import * as authService from '../services/authService';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(() => {
    // Initialize user state from localStorage (UI state only)
    const savedUser = localStorage.getItem('user');
    return savedUser ? (JSON.parse(savedUser) as User) : null;
  });
  const [isLoading, setIsLoading] = useState(true);

  // Function to refresh user data from backend
  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await authService.getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        // Store user info in localStorage for UI state persistence
        localStorage.setItem('user', JSON.stringify(currentUser));
      } else {
        setUser(null);
        localStorage.removeItem('user');
      }
    } catch (error) {
      // If getCurrentUser fails, user is not authenticated
      setUser(null);
      localStorage.removeItem('user');
    }
  }, []);

  // Initialize auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      try {
        // Try to get current user if we have stored user data
        // This validates the JWT cookie is still valid
        if (localStorage.getItem('user')) {
          await refreshUser();
        }
      } catch (error) {
        // Silent fail - user is just not authenticated
        console.error('Auth initialization error:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const loginResponse = await authService.login(email, password);
      setUser(loginResponse.user);
      // Store user info in localStorage for UI state only
      // JWT token is stored in HTTP-only cookie by backend
      localStorage.setItem('user', JSON.stringify(loginResponse.user));
    } catch (error) {
      setUser(null);
      localStorage.removeItem('user');
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.logout();
    } catch (error) {
      // Log error but continue with logout
      console.error('Logout error:', error);
    } finally {
      setUser(null);
      localStorage.removeItem('user');
      setIsLoading(false);
    }
  }, []);

  const contextValue = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isAdmin: user?.isAdmin ?? false,
      isLoading,
      login,
      logout,
      refreshUser,
    }),
    [user, isLoading, login, logout, refreshUser]
  );

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
}
