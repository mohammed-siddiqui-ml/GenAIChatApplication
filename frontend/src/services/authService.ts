/**
 * Authentication Service
 * 
 * Provides authentication functions for login, logout, and user management.
 * JWT tokens are stored in HTTP-only cookies (managed by backend).
 * User state is persisted in localStorage for UI state only.
 */

import api from './api';
import type { User } from '../types';

/**
 * Login request payload
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * Login response from backend
 */
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: number;
    email: string;
    role: string;
    is_active: boolean;
  };
}

/**
 * User response from backend
 */
export interface UserResponse {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
}

/**
 * Transform backend user response to frontend User type
 */
function transformUser(backendUser: UserResponse): User {
  return {
    id: backendUser.id.toString(),
    username: backendUser.email.split('@')[0] || backendUser.email,
    email: backendUser.email,
    isAdmin: backendUser.role === 'admin',
    createdAt: new Date().toISOString(), // Backend doesn't return this, using current time
  };
}

/**
 * Login user with email and password
 * 
 * @param email - User email
 * @param password - User password
 * @returns Login response with user data
 * @throws Error if login fails
 */
export async function login(email: string, password: string): Promise<{ user: User; tokens: { access_token: string; refresh_token: string } }> {
  try {
    const response = await api.post<LoginResponse>('/v1/auth/login', {
      email,
      password,
    });

    // Backend sets HTTP-only cookie automatically
    // Store refresh token in memory or secure storage if needed
    const user = transformUser(response.data.user);

    return {
      user,
      tokens: {
        access_token: response.data.access_token,
        refresh_token: response.data.refresh_token,
      },
    };
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
}

/**
 * Logout current user
 * Clears HTTP-only cookie and removes local user state
 * 
 * @throws Error if logout fails
 */
export async function logout(): Promise<void> {
  try {
    await api.post('/v1/auth/logout');
    // Backend clears HTTP-only cookie automatically
  } catch (error) {
    console.error('Logout error:', error);
    // Even if backend logout fails, clear local state
    throw error;
  }
}

/**
 * Get current authenticated user
 * Validates JWT token from HTTP-only cookie
 * 
 * @returns Current user or null if not authenticated
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await api.get<UserResponse>('/v1/auth/me');
    return transformUser(response.data);
  } catch (error) {
    console.error('Get current user error:', error);
    return null;
  }
}

/**
 * Refresh access token using refresh token
 * 
 * @param refreshToken - Refresh token
 * @returns New access token
 * @throws Error if refresh fails
 */
export async function refreshToken(refreshToken: string): Promise<string> {
  try {
    const response = await api.post<{ access_token: string }>('/v1/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data.access_token;
  } catch (error) {
    console.error('Token refresh error:', error);
    throw error;
  }
}

/**
 * Check if user is authenticated by validating the cookie
 * 
 * @returns True if user is authenticated
 */
export async function isAuthenticated(): Promise<boolean> {
  try {
    const user = await getCurrentUser();
    return user !== null;
  } catch (error) {
    return false;
  }
}
