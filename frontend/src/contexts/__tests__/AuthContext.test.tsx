import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthContext';
import * as authService from '../../services/authService';
import type { User } from '../../types';

// Mock authService
vi.mock('../../services/authService');

const mockUser: User = {
  id: '1',
  username: 'testuser',
  email: 'test@example.com',
  isAdmin: false,
  createdAt: '2024-01-01T00:00:00Z',
};

const mockAdminUser: User = {
  id: '2',
  username: 'adminuser',
  email: 'admin@example.com',
  isAdmin: true,
  createdAt: '2024-01-01T00:00:00Z',
};

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('useAuth hook', () => {
    it('should throw error when used outside AuthProvider', () => {
      // Suppress console.error for this test since we expect an error
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within AuthProvider');

      consoleError.mockRestore();
    });
  });

  describe('AuthProvider', () => {
    it('should initialize with null user when localStorage is empty', async () => {
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isAdmin).toBe(false);
    });

    it('should initialize with stored user and validate with backend', async () => {
      localStorage.setItem('user', JSON.stringify(mockUser));
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      // Initial state from localStorage
      expect(result.current.user).toEqual(mockUser);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(authService.getCurrentUser).toHaveBeenCalled();
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('should clear user if backend validation fails', async () => {
      localStorage.setItem('user', JSON.stringify(mockUser));
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(localStorage.getItem('user')).toBeNull();
    });

    it('should handle login successfully', async () => {
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockResolvedValue({
        user: mockUser,
        tokens: { access_token: 'token', refresh_token: 'refresh' },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await result.current.login('test@example.com', 'password');

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      expect(authService.login).toHaveBeenCalledWith(
        'test@example.com',
        'password'
      );
      expect(result.current.isAuthenticated).toBe(true);
      expect(localStorage.getItem('user')).toBe(JSON.stringify(mockUser));
    });

    it('should handle login failure', async () => {
      const error = new Error('Invalid credentials');
      vi.mocked(authService.login).mockRejectedValue(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        result.current.login('test@example.com', 'wrong')
      ).rejects.toThrow('Invalid credentials');
      expect(result.current.user).toBeNull();
      expect(localStorage.getItem('user')).toBeNull();
    });

    it('should handle logout successfully', async () => {
      localStorage.setItem('user', JSON.stringify(mockUser));
      vi.mocked(authService.getCurrentUser).mockResolvedValue(mockUser);
      vi.mocked(authService.logout).mockResolvedValue();

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      await result.current.logout();

      await waitFor(() => {
        expect(result.current.user).toBeNull();
      });

      expect(authService.logout).toHaveBeenCalled();
      expect(result.current.isAuthenticated).toBe(false);
      expect(localStorage.getItem('user')).toBeNull();
    });

    it('should handle refreshUser successfully', async () => {
      const updatedUser = { ...mockUser, username: 'updated' };
      localStorage.setItem('user', JSON.stringify(mockUser));
      vi.mocked(authService.getCurrentUser)
        .mockResolvedValueOnce(mockUser)
        .mockResolvedValueOnce(updatedUser);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await result.current.refreshUser();

      await waitFor(() => {
        expect(result.current.user?.username).toBe('updated');
      });

      expect(localStorage.getItem('user')).toBe(JSON.stringify(updatedUser));
    });

    it('should set isAdmin correctly for admin user', async () => {
      vi.mocked(authService.getCurrentUser).mockResolvedValue(null);
      vi.mocked(authService.login).mockResolvedValue({
        user: mockAdminUser,
        tokens: { access_token: 'token', refresh_token: 'refresh' },
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await result.current.login('admin@example.com', 'password');

      await waitFor(() => {
        expect(result.current.isAdmin).toBe(true);
      });

      expect(result.current.user?.isAdmin).toBe(true);
    });

    it('should manage loading state during login', async () => {
      let resolveLogin: (value: any) => void;
      const loginPromise = new Promise((resolve) => {
        resolveLogin = resolve;
      });

      vi.mocked(authService.login).mockReturnValue(loginPromise as any);

      const { result } = renderHook(() => useAuth(), {
        wrapper: AuthProvider,
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const loginCall = result.current.login('test@example.com', 'password');

      await waitFor(() => {
        expect(result.current.isLoading).toBe(true);
      });

      resolveLogin!({
        user: mockUser,
        tokens: { access_token: 'token', refresh_token: 'refresh' },
      });

      await loginCall;

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });
});
