/**
 * Test Suite for Task-042: Sentry Frontend Integration
 * 
 * Tests for Sentry utility functions:
 * - TC-FS-01-01: initSentry initializes with valid DSN
 * - TC-FS-01-02: initSentry skips initialization without DSN
 * - TC-FS-02-01: setSentryUser sets user context
 * - TC-FS-02-02: clearSentryUser clears user context
 * - TC-FS-02-03: captureException manually captures errors
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as Sentry from '@sentry/react';
import { initSentry, setSentryUser, clearSentryUser, captureException } from '../sentry';

// Mock Sentry module
vi.mock('@sentry/react', () => ({
  init: vi.fn(),
  setUser: vi.fn(),
  setContext: vi.fn(),
  captureException: vi.fn(),
  BrowserTracing: vi.fn(),
  Replay: vi.fn(),
}));

describe('Sentry Utilities', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    vi.clearAllMocks();
    
    // Reset import.meta.env for each test
    vi.stubEnv('VITE_SENTRY_DSN', '');
    vi.stubEnv('VITE_SENTRY_ENVIRONMENT', '');
    vi.stubEnv('VITE_SENTRY_TRACES_SAMPLE_RATE', '');
    vi.stubEnv('VITE_GIT_COMMIT_SHA', '');
    vi.stubEnv('VITE_APP_VERSION', '');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('initSentry', () => {
    it('TC-FS-01-01: should initialize Sentry with valid DSN', () => {
      // Mock environment variables
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test-frontend@sentry.io/789012');
      vi.stubEnv('VITE_SENTRY_ENVIRONMENT', 'development');
      vi.stubEnv('VITE_SENTRY_TRACES_SAMPLE_RATE', '0.1');
      vi.stubEnv('VITE_GIT_COMMIT_SHA', 'frontend-commit-sha-123');
      
      // Call initSentry
      initSentry();
      
      // Verify Sentry.init was called
      expect(Sentry.init).toHaveBeenCalledTimes(1);
      
      // Verify init was called with correct config
      const initCall = (Sentry.init as any).mock.calls[0][0];
      expect(initCall.dsn).toBe('https://test-frontend@sentry.io/789012');
      expect(initCall.environment).toBe('development');
      expect(initCall.release).toBe('frontend-commit-sha-123');
      expect(initCall.tracesSampleRate).toBe(0.1);
      
      // Verify integrations are configured
      expect(initCall.integrations).toBeDefined();
      expect(initCall.integrations.length).toBeGreaterThan(0);
    });

    it('TC-FS-01-02: should skip initialization when DSN is not configured', () => {
      // Don't set VITE_SENTRY_DSN (leave it empty)
      const consoleInfoSpy = vi.spyOn(console, 'info');
      
      // Call initSentry
      initSentry();
      
      // Verify Sentry.init was NOT called
      expect(Sentry.init).not.toHaveBeenCalled();
      
      // Verify info message was logged
      expect(consoleInfoSpy).toHaveBeenCalledWith(
        expect.stringContaining('DSN not configured')
      );
      
      consoleInfoSpy.mockRestore();
    });

    it('should use app version as fallback when Git SHA is not available', () => {
      // Mock environment variables without Git SHA
      vi.stubEnv('VITE_SENTRY_DSN', 'https://test@sentry.io/123');
      vi.stubEnv('VITE_APP_VERSION', '1.0.0');
      
      // Call initSentry
      initSentry();
      
      // Verify release falls back to app version
      const initCall = (Sentry.init as any).mock.calls[0][0];
      expect(initCall.release).toBe('1.0.0');
    });
  });

  describe('setSentryUser', () => {
    it('TC-FS-02-01: should set user context with provided data', () => {
      // Call setSentryUser
      setSentryUser('user-123', 'test@example.com', 'testuser');
      
      // Verify Sentry.setUser was called with correct data
      expect(Sentry.setUser).toHaveBeenCalledTimes(1);
      expect(Sentry.setUser).toHaveBeenCalledWith({
        id: 'user-123',
        email: 'test@example.com',
        username: 'testuser',
      });
    });

    it('should set user context with only user ID', () => {
      // Call setSentryUser with only ID
      setSentryUser('user-456');
      
      // Verify Sentry.setUser was called
      expect(Sentry.setUser).toHaveBeenCalledWith({
        id: 'user-456',
        email: undefined,
        username: undefined,
      });
    });
  });

  describe('clearSentryUser', () => {
    it('TC-FS-02-02: should clear user context', () => {
      // Call clearSentryUser
      clearSentryUser();
      
      // Verify Sentry.setUser was called with null
      expect(Sentry.setUser).toHaveBeenCalledTimes(1);
      expect(Sentry.setUser).toHaveBeenCalledWith(null);
    });
  });

  describe('captureException', () => {
    it('TC-FS-02-03: should manually capture errors with custom context', () => {
      // Create test error
      const testError = new Error('Test frontend error');
      const customContext = { customKey: 'customValue', requestId: '123' };
      
      // Call captureException
      captureException(testError, customContext);
      
      // Verify setContext was called with custom context
      expect(Sentry.setContext).toHaveBeenCalledWith('custom', customContext);
      
      // Verify captureException was called with the error
      expect(Sentry.captureException).toHaveBeenCalledWith(testError);
    });

    it('should capture errors without context', () => {
      // Create test error
      const testError = new Error('Simple error');
      
      // Call captureException without context
      captureException(testError);
      
      // Verify captureException was called
      expect(Sentry.captureException).toHaveBeenCalledWith(testError);
      
      // Verify setContext was NOT called
      expect(Sentry.setContext).not.toHaveBeenCalled();
    });
  });
});
