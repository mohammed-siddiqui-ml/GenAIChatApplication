/**
 * useChat Hook Tests
 * 
 * Tests for the chat hook including:
 * - Message sending
 * - Streaming response handling
 * - Source citations
 * - Error handling
 * - Optimistic updates
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChat } from '@hooks/useChat';
import { createMockSocket } from '../mocks/socket';

describe('useChat', () => {
  let mockSocket: ReturnType<typeof createMockSocket>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = createMockSocket();
  });

  it('should initialize with empty messages', () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  it('should send message and add to messages optimistically', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThanOrEqual(1);
    });

    // Check that user message was added
    const userMessage = result.current.messages.find(m => m.role === 'user');
    expect(userMessage).toBeDefined();
    expect(userMessage?.content).toBe('Hello');

    expect(mockSocket.emit).toHaveBeenCalledWith('chat:query', {
      query: 'Hello',
      top_k: 10,
      temperature: 0.7,
    });
  });

  it('should set isStreaming to true when sending message', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    // Send message with act to properly handle state updates
    act(() => {
      result.current.sendMessage('Hello');
    });

    // Wait for streaming state to update
    await waitFor(() => {
      expect(result.current.isStreaming).toBe(true);
    });
  });

  it('should handle streaming chunks', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    // Simulate receiving chunks
    act(() => {
      (mockSocket as any).__triggerEvent('chat:chunk', {
        chunk: 'Response ',
        chunk_index: 0,
        timestamp: new Date().toISOString(),
      });
    });

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThanOrEqual(2);
    });

    act(() => {
      (mockSocket as any).__triggerEvent('chat:chunk', {
        chunk: 'text',
        chunk_index: 1,
        timestamp: new Date().toISOString(),
      });
    });

    // Trigger the done event to finalize the message
    act(() => {
      (mockSocket as any).__triggerEvent('chat:done', {
        timestamp: new Date().toISOString(),
      });
    });

    await waitFor(() => {
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant');
      expect(assistantMessage?.content).toBe('Response text');
    });
  });

  it('should handle source citations', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    // Wait for user message to be added
    await waitFor(() => {
      expect(result.current.messages.some(m => m.role === 'user')).toBe(true);
    });

    // Simulate receiving chunk first
    act(() => {
      (mockSocket as any).__triggerEvent('chat:chunk', {
        chunk: 'Answer',
        chunk_index: 0,
        timestamp: new Date().toISOString(),
      });
    });

    // Wait for assistant message to appear
    await waitFor(() => {
      expect(result.current.messages.some(m => m.role === 'assistant')).toBe(true);
    });

    // Simulate receiving sources
    act(() => {
      (mockSocket as any).__triggerEvent('chat:sources', {
        sources: [
          {
            id: '1',
            title: 'Doc 1',
            url: 'https://example.com/doc1',
            type: 'documentation',
            similarity: 0.95,
            chunk_index: 0,
            metadata: {},
          },
        ],
        timestamp: new Date().toISOString(),
      });
    });

    // Simulate completion
    act(() => {
      (mockSocket as any).__triggerEvent('chat:done', {});
    });

    // Wait for sources to be attached and streaming to stop
    await waitFor(() => {
      const assistantMessage = result.current.messages.find(m => m.role === 'assistant');
      expect(assistantMessage?.sources).toBeDefined();
      expect(assistantMessage?.sources?.length).toBe(1);
      expect(assistantMessage?.sources?.[0].title).toBe('Doc 1');
      expect(assistantMessage?.isStreaming).toBe(false);
    });
  });

  it('should set isStreaming to false when done', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    // Send message first
    act(() => {
      result.current.sendMessage('Hello');
    });

    // Wait for isStreaming to become true
    await waitFor(() => {
      expect(result.current.isStreaming).toBe(true);
    });

    act(() => {
      (mockSocket as any).__triggerEvent('chat:chunk', {
        chunk: 'Answer',
        chunk_index: 0,
        timestamp: new Date().toISOString(),
      });
    });

    act(() => {
      (mockSocket as any).__triggerEvent('chat:done', {});
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it('should handle errors and call onError callback', async () => {
    const onError = vi.fn();
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
        onError,
      })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    const errorData = {
      error: 'Test error',
      type: 'server_error',
      timestamp: new Date().toISOString(),
    };

    act(() => {
      (mockSocket as any).__triggerEvent('chat:error', errorData);
    });

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith(errorData);
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it('should clear messages when clearMessages is called', async () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    act(() => {
      result.current.sendMessage('Hello');
    });

    await waitFor(() => {
      expect(result.current.messages.length).toBeGreaterThan(0);
    });

    act(() => {
      result.current.clearMessages();
    });

    await waitFor(() => {
      expect(result.current.messages).toEqual([]);
    });
  });

  it('should not send message when socket is not connected', () => {
    mockSocket.connected = false;

    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    result.current.sendMessage('Hello');

    expect(mockSocket.emit).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
  });

  it('should not send empty query', () => {
    const { result } = renderHook(() =>
      useChat({
        socket: mockSocket as any,
        sessionId: 'test-session',
      })
    );

    result.current.sendMessage('   ');

    expect(mockSocket.emit).not.toHaveBeenCalled();
  });
});
