import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as authService from '../authService';
import api from '../api';
import type { LoginResponse, UserResponse } from '../authService';

// Mock the api module
vi.mock('../api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('login', () => {
    it('should login successfully with valid credentials', async () => {
      const mockResponse: LoginResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        token_type: 'Bearer',
        user: {
          id: 1,
          email: 'test@example.com',
          role: 'user',
          is_active: true,
        },
      };

      vi.mocked(api.post).mockResolvedValueOnce({ data: mockResponse });

      const result = await authService.login('test@example.com', 'password123');

      expect(api.post).toHaveBeenCalledWith('/v1/auth/login', {
        email: 'test@example.com',
        password: 'password123',
      });
      expect(result.user).toEqual({
        id: '1',
        username: 'test',
        email: 'test@example.com',
        isAdmin: false,
        createdAt: expect.any(String),
      });
      expect(result.tokens.access_token).toBe('mock-access-token');
      expect(result.tokens.refresh_token).toBe('mock-refresh-token');
    });

    it('should throw error on invalid credentials', async () => {
      const mockError = {
        response: {
          status: 401,
          data: { message: 'Invalid credentials' },
        },
      };

      vi.mocked(api.post).mockRejectedValueOnce(mockError);

      await expect(authService.login('test@example.com', 'wrongpassword')).rejects.toEqual(mockError);
      expect(api.post).toHaveBeenCalledWith('/v1/auth/login', {
        email: 'test@example.com',
        password: 'wrongpassword',
      });
    });

    it('should transform admin user correctly', async () => {
      const mockResponse: LoginResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        token_type: 'Bearer',
        user: {
          id: 2,
          email: 'admin@example.com',
          role: 'admin',
          is_active: true,
        },
      };

      vi.mocked(api.post).mockResolvedValueOnce({ data: mockResponse });

      const result = await authService.login('admin@example.com', 'password');

      expect(result.user.isAdmin).toBe(true);
      expect(result.user.username).toBe('admin');
    });
  });

  describe('logout', () => {
    it('should logout successfully', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: {} });

      await expect(authService.logout()).resolves.not.toThrow();
      expect(api.post).toHaveBeenCalledWith('/v1/auth/logout');
    });

    it('should throw error if logout fails', async () => {
      const mockError = new Error('Logout failed');
      vi.mocked(api.post).mockRejectedValueOnce(mockError);

      await expect(authService.logout()).rejects.toThrow('Logout failed');
    });
  });

  describe('getCurrentUser', () => {
    it('should get current user successfully', async () => {
      const mockResponse: UserResponse = {
        id: 1,
        email: 'test@example.com',
        role: 'user',
        is_active: true,
      };

      vi.mocked(api.get).mockResolvedValueOnce({ data: mockResponse });

      const result = await authService.getCurrentUser();

      expect(api.get).toHaveBeenCalledWith('/v1/auth/me');
      expect(result).toEqual({
        id: '1',
        username: 'test',
        email: 'test@example.com',
        isAdmin: false,
        createdAt: expect.any(String),
      });
    });

    it('should return null on unauthorized', async () => {
      const mockError = {
        response: { status: 401, data: { message: 'Unauthorized' } },
      };

      vi.mocked(api.get).mockRejectedValueOnce(mockError);

      const result = await authService.getCurrentUser();

      expect(result).toBeNull();
    });
  });

  describe('refreshToken', () => {
    it('should refresh token successfully', async () => {
      const mockResponse = { access_token: 'new-access-token' };

      vi.mocked(api.post).mockResolvedValueOnce({ data: mockResponse });

      const result = await authService.refreshToken('old-refresh-token');

      expect(api.post).toHaveBeenCalledWith('/v1/auth/refresh', {
        refresh_token: 'old-refresh-token',
      });
      expect(result).toBe('new-access-token');
    });

    it('should throw error if refresh fails', async () => {
      const mockError = new Error('Token expired');
      vi.mocked(api.post).mockRejectedValueOnce(mockError);

      await expect(authService.refreshToken('invalid-token')).rejects.toThrow('Token expired');
    });
  });

  describe('isAuthenticated', () => {
    it('should return true when user is authenticated', async () => {
      const mockResponse: UserResponse = {
        id: 1,
        email: 'test@example.com',
        role: 'user',
        is_active: true,
      };

      vi.mocked(api.get).mockResolvedValueOnce({ data: mockResponse });

      const result = await authService.isAuthenticated();

      expect(result).toBe(true);
    });

    it('should return false when user is not authenticated', async () => {
      vi.mocked(api.get).mockRejectedValueOnce(new Error('Unauthorized'));

      const result = await authService.isAuthenticated();

      expect(result).toBe(false);
    });
  });
});