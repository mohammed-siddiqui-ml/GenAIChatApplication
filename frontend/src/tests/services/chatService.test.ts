/**
 * ChatService Tests
 * 
 * Tests for the chat service including:
 * - Session management
 * - Query submission (WebSocket and SSE)
 * - Streaming responses
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as chatService from '@services/chatService';
import api from '@services/api';
import socketService from '@services/socket';
import type { Socket } from 'socket.io-client';
import { createMockSocket } from '../mocks/socket';

vi.mock('@services/api');
vi.mock('@services/socket');

describe('ChatService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Session Management', () => {
    it('should create a new session', async () => {
      const mockResponse = {
        data: {
          session_id: 'new-session-123',
          session_token: 'new-token-456',
          created_at: '2024-01-15T10:00:00Z',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const session = await chatService.createSession();

      expect(session.sessionId).toBe('new-session-123');
      expect(session.sessionToken).toBe('new-token-456');
      expect(api.post).toHaveBeenCalledWith('/v1/chat/sessions', expect.any(Object));
    });

    it('should store session in localStorage', async () => {
      const mockResponse = {
        data: {
          session_id: 'test-session',
          session_token: 'test-token',
          created_at: '2024-01-15T10:00:00Z',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      await chatService.createSession();

      const stored = localStorage.getItem('chat_session');
      expect(stored).toBeTruthy();
      
      const parsed = JSON.parse(stored!);
      expect(parsed.sessionId).toBe('test-session');
      expect(parsed.sessionToken).toBe('test-token');
    });

    it('should retrieve session from localStorage', () => {
      const sessionData = {
        sessionId: 'stored-session',
        sessionToken: 'stored-token',
        createdAt: '2024-01-15T10:00:00Z',
      };

      localStorage.setItem('chat_session', JSON.stringify(sessionData));

      const session = chatService.getSession();

      expect(session).toEqual(sessionData);
    });

    it('should return null when no session exists', () => {
      const session = chatService.getSession();
      expect(session).toBeNull();
    });

    it('should clear session from localStorage', () => {
      localStorage.setItem('chat_session', JSON.stringify({
        sessionId: 'test',
        sessionToken: 'token',
        createdAt: '2024-01-15T10:00:00Z',
      }));

      chatService.clearSession();

      expect(localStorage.getItem('chat_session')).toBeNull();
    });

    it('should get or create session when session exists', async () => {
      const existingSession = {
        sessionId: 'existing-session',
        sessionToken: 'existing-token',
        createdAt: '2024-01-15T10:00:00Z',
      };

      localStorage.setItem('chat_session', JSON.stringify(existingSession));

      const session = await chatService.getOrCreateSession();

      expect(session).toEqual(existingSession);
      expect(api.post).not.toHaveBeenCalled();
    });

    it('should create new session when none exists', async () => {
      const mockResponse = {
        data: {
          session_id: 'new-session',
          session_token: 'new-token',
          created_at: '2024-01-15T10:00:00Z',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const session = await chatService.getOrCreateSession();

      expect(session.sessionId).toBe('new-session');
      expect(api.post).toHaveBeenCalled();
    });
  });

  describe('Query Submission', () => {
    beforeEach(() => {
      const sessionData = {
        sessionId: 'test-session',
        sessionToken: 'test-token',
        createdAt: '2024-01-15T10:00:00Z',
      };
      localStorage.setItem('chat_session', JSON.stringify(sessionData));
    });

    it('should send non-streaming query', async () => {
      const mockResponse = {
        data: {
          content: 'Test response',
          sources: [],
          metadata: {},
          session_id: 'test-session',
          message_id: 1,
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const response = await chatService.sendQueryNonStreaming('Test query');

      expect(response.content).toBe('Test response');
      expect(api.post).toHaveBeenCalledWith(
        '/v1/chat/query',
        expect.objectContaining({
          query: 'Test query',
          stream: false,
        }),
        expect.any(Object)
      );
    });

    it('should send query with custom options', async () => {
      const mockResponse = {
        data: {
          content: 'Test response',
          sources: [],
          metadata: {},
          session_id: 'test-session',
          message_id: 1,
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      await chatService.sendQueryNonStreaming('Test query', {
        top_k: 5,
        temperature: 0.5,
      });

      expect(api.post).toHaveBeenCalledWith(
        '/v1/chat/query',
        expect.objectContaining({
          query: 'Test query',
          top_k: 5,
          temperature: 0.5,
        }),
        expect.any(Object)
      );
    });
  });
});
