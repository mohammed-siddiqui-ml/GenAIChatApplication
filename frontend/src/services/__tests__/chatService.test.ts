import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as chatService from '../chatService';
import api from '../api';
import socketService from '../socket';
import type { QueryResponse, SourceCitation, StreamEvent } from '../chatService';

// Mock the api module
vi.mock('../api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

// Mock the socket service
vi.mock('../socket', () => ({
  default: {
    connect: vi.fn(),
  },
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock navigator.userAgent
Object.defineProperty(navigator, 'userAgent', {
  value: 'Mozilla/5.0 Test Browser',
  configurable: true,
});

describe('chatService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Session Management', () => {
    const mockSessionData = {
      sessionId: 'test-session-123',
      sessionToken: 'test-token-abc',
      createdAt: '2024-01-15T10:00:00.000Z',
    };

    const mockSessionResponse = {
      session_id: 'test-session-123',
      session_token: 'test-token-abc',
      created_at: '2024-01-15T10:00:00.000Z',
    };

    // TC-001: Create New Session Successfully
    it('should create a new session successfully', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: mockSessionResponse });

      const result = await chatService.createSession();

      expect(api.post).toHaveBeenCalledWith('/v1/chat/sessions', {
        user_agent: 'Mozilla/5.0 Test Browser',
        ip_address: null,
      });
      expect(result).toEqual(mockSessionData);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'chat_session',
        JSON.stringify(mockSessionData)
      );
    });

    // TC-002: Get Existing Session from localStorage
    it('should get existing session from localStorage', () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const result = chatService.getSession();

      expect(result).toEqual(mockSessionData);
      expect(localStorageMock.getItem).toHaveBeenCalledWith('chat_session');
    });

    // TC-003: Get or Create Session - Existing Session
    it('should return existing session without creating new one', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const result = await chatService.getOrCreateSession();

      expect(result).toEqual(mockSessionData);
      expect(api.post).not.toHaveBeenCalled();
    });

    // TC-004: Get or Create Session - No Existing Session
    it('should create new session when none exists', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: mockSessionResponse });

      const result = await chatService.getOrCreateSession();

      expect(api.post).toHaveBeenCalledWith('/v1/chat/sessions', expect.any(Object));
      expect(result).toEqual(mockSessionData);
    });

    // TC-005: Clear Session
    it('should clear session from localStorage', () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      chatService.clearSession();

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('chat_session');
      expect(chatService.getSession()).toBeNull();
    });

    // TC-006: Handle Corrupted Session Data in localStorage
    it('should handle corrupted session data gracefully', () => {
      localStorageMock.setItem('chat_session', 'invalid-json{');

      const result = chatService.getSession();

      expect(result).toBeNull();
    });

    // TC-007: Session Creation API Failure
    it('should throw error when session creation fails', async () => {
      const mockError = new Error('Network error');
      vi.mocked(api.post).mockRejectedValueOnce(mockError);

      await expect(chatService.createSession()).rejects.toThrow('Failed to create chat session');
      expect(localStorageMock.setItem).not.toHaveBeenCalled();
    });
  });

  describe('WebSocket Query Submission', () => {
    const mockSessionData = {
      sessionId: 'test-session-123',
      sessionToken: 'test-token-abc',
      createdAt: '2024-01-15T10:00:00.000Z',
    };

    // TC-008: WebSocket Query Streaming Success
    it('should send query via WebSocket and handle streaming events', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockSocket = {
        on: vi.fn((event, handler) => {
          // Store handlers for immediate callback
          if (event === 'chat:chunk') {
            setTimeout(() => handler({ content: 'Test response' }), 0);
          } else if (event === 'chat:sources') {
            setTimeout(() => handler({ sources: [] }), 10);
          } else if (event === 'chat:done') {
            setTimeout(() => handler({ metadata: { duration: 1.5 } }), 20);
          }
        }),
        off: vi.fn(),
        emit: vi.fn(),
      };

      vi.mocked(socketService.connect).mockReturnValueOnce(mockSocket as any);

      const streamCallback = vi.fn();
      await chatService.sendQueryWebSocket('Test query', streamCallback);

      expect(socketService.connect).toHaveBeenCalledWith('test-session-123');
      expect(mockSocket.emit).toHaveBeenCalledWith('chat:query', {
        query: 'Test query',
        top_k: 10,
        temperature: 0.7,
      });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Test response' });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'sources', sources: [] });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'done', metadata: { duration: 1.5 } });
      expect(mockSocket.off).toHaveBeenCalledTimes(4);
    });

    // TC-012: Query with Custom Options
    it('should send query with custom options', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockSocket = {
        on: vi.fn((event, handler) => {
          if (event === 'chat:done') {
            setTimeout(() => handler({ metadata: {} }), 0);
          }
        }),
        off: vi.fn(),
        emit: vi.fn(),
      };

      vi.mocked(socketService.connect).mockReturnValueOnce(mockSocket as any);

      const streamCallback = vi.fn();
      await chatService.sendQueryWebSocket('Test query', streamCallback, {
        top_k: 5,
        temperature: 0.9,
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('chat:query', {
        query: 'Test query',
        top_k: 5,
        temperature: 0.9,
      });
    });

    // TC-016: WebSocket Error Event
    it('should handle WebSocket error event', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockSocket = {
        on: vi.fn((event, handler) => {
          if (event === 'chat:error') {
            setTimeout(() => handler({ error: 'Query processing failed' }), 0);
          }
        }),
        off: vi.fn(),
        emit: vi.fn(),
      };

      vi.mocked(socketService.connect).mockReturnValueOnce(mockSocket as any);

      const streamCallback = vi.fn();

      await expect(chatService.sendQueryWebSocket('Test query', streamCallback)).rejects.toThrow(
        'Query processing failed'
      );
      expect(streamCallback).toHaveBeenCalledWith({
        type: 'error',
        error: 'Query processing failed',
      });
      expect(mockSocket.off).toHaveBeenCalledTimes(4);
    });
  });

  describe('SSE Query Submission', () => {
    const mockSessionData = {
      sessionId: 'test-session-123',
      sessionToken: 'test-token-abc',
      createdAt: '2024-01-15T10:00:00.000Z',
    };

    // TC-009: SSE Query Streaming Success
    it('should send query via SSE and handle streaming events', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const sseData = [
        'data: {"type":"chunk","content":"Machine learning is"}\n\n',
        'data: {"type":"chunk","content":" a subset of AI"}\n\n',
        'data: {"type":"sources","sources":[]}\n\n',
        'data: {"type":"done","metadata":{"duration":1.5}}\n\n',
      ].join('');

      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(sseData),
          })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();
      await chatService.sendQuerySSE('Test query', streamCallback);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/v1/chat/query'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-Session-Token': 'test-token-abc',
          }),
        })
      );
      expect(streamCallback).toHaveBeenCalledWith({
        type: 'chunk',
        content: 'Machine learning is',
      });
      expect(streamCallback).toHaveBeenCalledWith({
        type: 'chunk',
        content: ' a subset of AI',
      });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'sources', sources: [] });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'done', metadata: { duration: 1.5 } });
    });

    // TC-013: SSE Event Parsing - Multiple Chunks
    it('should process multiple chunk events correctly', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const sseData = [
        'data: {"type":"chunk","content":"Part 1"}\n\n',
        'data: {"type":"chunk","content":"Part 2"}\n\n',
        'data: {"type":"chunk","content":"Part 3"}\n\n',
        'data: {"type":"done","metadata":{}}\n\n',
      ].join('');

      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(sseData),
          })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();
      await chatService.sendQuerySSE('Test query', streamCallback);

      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Part 1' });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Part 2' });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Part 3' });
    });

    // TC-014: SSE Buffer Handles Incomplete Messages
    it('should buffer incomplete SSE messages', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"chu'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('nk","content":"Test"}\n\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"done","metadata":{}}\n\n'),
          })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();
      await chatService.sendQuerySSE('Test query', streamCallback);

      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Test' });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'done', metadata: {} });
    });

    // TC-015: SSE Invalid JSON Handling
    it('should handle invalid JSON in SSE events gracefully', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const sseData = [
        'data: {invalid-json}\n\n',
        'data: {"type":"chunk","content":"Valid"}\n\n',
        'data: {"type":"done","metadata":{}}\n\n',
      ].join('');

      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(sseData),
          })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();
      await chatService.sendQuerySSE('Test query', streamCallback);

      // Should still process valid events
      expect(streamCallback).toHaveBeenCalledWith({ type: 'chunk', content: 'Valid' });
      expect(streamCallback).toHaveBeenCalledWith({ type: 'done', metadata: {} });
    });

    // TC-017: SSE Fetch Network Error
    it('should handle network errors', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      global.fetch = vi.fn().mockRejectedValueOnce(new Error('Network error'));

      const streamCallback = vi.fn();

      await expect(chatService.sendQuerySSE('Test query', streamCallback)).rejects.toThrow();
      expect(streamCallback).toHaveBeenCalledWith({
        type: 'error',
        error: 'Network error',
      });
    });

    // TC-018: SSE Non-200 Response Status
    it('should throw error on non-200 response', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockResponse = {
        ok: false,
        statusText: 'Internal Server Error',
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();

      await expect(chatService.sendQuerySSE('Test query', streamCallback)).rejects.toThrow(
        'Query failed: Internal Server Error'
      );
    });
  });

  describe('Automatic Fallback', () => {
    const mockSessionData = {
      sessionId: 'test-session-123',
      sessionToken: 'test-token-abc',
      createdAt: '2024-01-15T10:00:00.000Z',
    };

    // TC-010: Automatic WebSocket to SSE Fallback
    it('should fallback to SSE when WebSocket fails', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      const mockSocket = {
        on: vi.fn((event, handler) => {
          if (event === 'chat:error') {
            setTimeout(() => handler({ error: 'WebSocket error' }), 0);
          }
        }),
        off: vi.fn(),
        emit: vi.fn(),
      };

      vi.mocked(socketService.connect).mockReturnValueOnce(mockSocket as any);

      const sseData = 'data: {"type":"done","metadata":{}}\n\n';
      const mockReader = {
        read: vi.fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(sseData),
          })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      global.fetch = vi.fn().mockResolvedValueOnce(mockResponse);

      const streamCallback = vi.fn();

      await chatService.sendQuery('Test query', streamCallback);

      expect(global.fetch).toHaveBeenCalled();
      expect(streamCallback).toHaveBeenCalledWith({ type: 'done', metadata: {} });
    });
  });

  describe('Non-Streaming Query', () => {
    const mockSessionData = {
      sessionId: 'test-session-123',
      sessionToken: 'test-token-abc',
      createdAt: '2024-01-15T10:00:00.000Z',
    };

    const mockQueryResponse: QueryResponse = {
      content: 'Machine learning is a subset of AI...',
      sources: [],
      metadata: { duration: 1.5 },
      session_id: 'test-session-123',
      message_id: 42,
    };

    // TC-011: Non-Streaming Query Success
    it('should send non-streaming query successfully', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      vi.mocked(api.post).mockResolvedValueOnce({ data: mockQueryResponse });

      const result = await chatService.sendQueryNonStreaming('Test query');

      expect(api.post).toHaveBeenCalledWith(
        '/v1/chat/query',
        {
          query: 'Test query',
          stream: false,
          top_k: 10,
          temperature: 0.7,
        },
        {
          headers: {
            'X-Session-Token': 'test-token-abc',
          },
        }
      );
      expect(result).toEqual(mockQueryResponse);
    });

    // TC-019: Query Without Session Creates Session
    it('should create session automatically if none exists', async () => {
      const mockSessionResponse = {
        session_id: 'test-session-123',
        session_token: 'test-token-abc',
        created_at: '2024-01-15T10:00:00.000Z',
      };

      vi.mocked(api.post)
        .mockResolvedValueOnce({ data: mockSessionResponse })
        .mockResolvedValueOnce({ data: mockQueryResponse });

      const result = await chatService.sendQueryNonStreaming('Test query');

      expect(api.post).toHaveBeenCalledWith('/v1/chat/sessions', expect.any(Object));
      expect(api.post).toHaveBeenCalledWith(
        '/v1/chat/query',
        expect.any(Object),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Session-Token': 'test-token-abc',
          }),
        })
      );
      expect(result).toEqual(mockQueryResponse);
    });

    // TC-020: Session Token Included in All Requests
    it('should include session token in request headers', async () => {
      localStorageMock.setItem('chat_session', JSON.stringify(mockSessionData));

      vi.mocked(api.post).mockResolvedValueOnce({ data: mockQueryResponse });

      await chatService.sendQueryNonStreaming('Test query');

      expect(api.post).toHaveBeenCalledWith(
        '/v1/chat/query',
        expect.any(Object),
        expect.objectContaining({
          headers: {
            'X-Session-Token': 'test-token-abc',
          },
        })
      );
    });
  });
});
