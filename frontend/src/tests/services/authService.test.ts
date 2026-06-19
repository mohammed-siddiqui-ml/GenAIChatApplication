/**
 * AuthService Tests
 * 
 * Tests for the authentication service including:
 * - Login
 * - Logout
 * - User retrieval
 * - Token refresh
 * - Authentication status
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as authService from '@services/authService';
import api from '@services/api';

vi.mock('@services/api');

describe('AuthService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('login', () => {
    it('should login successfully with valid credentials', async () => {
      const mockResponse = {
        data: {
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          token_type: 'Bearer',
          user: {
            id: 1,
            email: 'test@example.com',
            role: 'user',
            is_active: true,
          },
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await authService.login('test@example.com', 'password');

      expect(result.user.email).toBe('test@example.com');
      expect(result.user.isAdmin).toBe(false);
      expect(result.tokens.access_token).toBe('access-token');
      expect(api.post).toHaveBeenCalledWith('/v1/auth/login', {
        email: 'test@example.com',
        password: 'password',
      });
    });

    it('should transform admin user correctly', async () => {
      const mockResponse = {
        data: {
          access_token: 'access-token',
          refresh_token: 'refresh-token',
          token_type: 'Bearer',
          user: {
            id: 2,
            email: 'admin@example.com',
            role: 'admin',
            is_active: true,
          },
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await authService.login('admin@example.com', 'password');

      expect(result.user.isAdmin).toBe(true);
      expect(result.user.username).toBe('admin');
    });

    it('should throw error on login failure', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Invalid credentials'));

      await expect(
        authService.login('wrong@example.com', 'wrong')
      ).rejects.toThrow('Invalid credentials');
    });
  });

  describe('logout', () => {
    it('should logout successfully', async () => {
      vi.mocked(api.post).mockResolvedValue({ data: { message: 'Logged out' } });

      await authService.logout();

      expect(api.post).toHaveBeenCalledWith('/v1/auth/logout');
    });

    it('should throw error if logout fails', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Logout failed'));

      await expect(authService.logout()).rejects.toThrow('Logout failed');
    });
  });

  describe('getCurrentUser', () => {
    it('should retrieve current user', async () => {
      const mockResponse = {
        data: {
          id: 1,
          email: 'test@example.com',
          role: 'user',
          is_active: true,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const user = await authService.getCurrentUser();

      expect(user).not.toBeNull();
      expect(user?.email).toBe('test@example.com');
      expect(user?.isAdmin).toBe(false);
      expect(api.get).toHaveBeenCalledWith('/v1/auth/me');
    });

    it('should return null on error', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('Unauthorized'));

      const user = await authService.getCurrentUser();

      expect(user).toBeNull();
    });
  });

  describe('refreshToken', () => {
    it('should refresh access token', async () => {
      const mockResponse = {
        data: {
          access_token: 'new-access-token',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const newToken = await authService.refreshToken('old-refresh-token');

      expect(newToken).toBe('new-access-token');
      expect(api.post).toHaveBeenCalledWith('/v1/auth/refresh', {
        refresh_token: 'old-refresh-token',
      });
    });

    it('should throw error if refresh fails', async () => {
      vi.mocked(api.post).mockRejectedValue(new Error('Invalid refresh token'));

      await expect(
        authService.refreshToken('invalid-token')
      ).rejects.toThrow('Invalid refresh token');
    });
  });

  describe('isAuthenticated', () => {
    it('should return true when user is authenticated', async () => {
      const mockResponse = {
        data: {
          id: 1,
          email: 'test@example.com',
          role: 'user',
          is_active: true,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const isAuth = await authService.isAuthenticated();

      expect(isAuth).toBe(true);
    });

    it('should return false when user is not authenticated', async () => {
      vi.mocked(api.get).mockRejectedValue(new Error('Unauthorized'));

      const isAuth = await authService.isAuthenticated();

      expect(isAuth).toBe(false);
    });
  });
});
