import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChat } from '../useChat';

describe('useChat', () => {
  let mockSocket: any;
  let eventHandlers: Record<string, Function>;

  beforeEach(() => {
    eventHandlers = {};

    mockSocket = {
      on: vi.fn((event: string, handler: Function) => {
        eventHandlers[event] = handler;
        return mockSocket;
      }),
      emit: vi.fn(),
      off: vi.fn(),
      connected: true,
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // TC-006: useChat Sends Message Correctly
  it('TC-006: sends message with correct payload', () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    act(() => {
      result.current.sendMessage('Hello, world!');
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('chat:query', {
      query: 'Hello, world!',
      top_k: 10,
      temperature: 0.7,
    });

    // Check optimistic update
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      content: 'Hello, world!',
      role: 'user',
    });
  });

  // TC-007: useChat Handles Streaming Chunks
  it('TC-007: handles streaming chunks correctly', async () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    // Send message
    act(() => {
      result.current.sendMessage('What is React?');
    });

    // Simulate first chunk
    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'React is ',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1]).toMatchObject({
        content: 'React is ',
        role: 'assistant',
        isStreaming: true,
      });
      expect(result.current.isStreaming).toBe(true);
    });

    // Simulate second chunk
    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'a JavaScript library',
        chunk_index: 1,
        timestamp: new Date().toISOString()
      });
    });

    await waitFor(() => {
      expect(result.current.messages[1].content).toBe('React is a JavaScript library');
      expect(result.current.isStreaming).toBe(true);
    });
  });

  // TC-008: useChat Handles Sources Event
  it('TC-008: stores sources temporarily', async () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    // Send message
    act(() => {
      result.current.sendMessage('Test query');
    });

    // Receive chunk
    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'Response',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    // Receive sources - match backend format
    const testSources = [
      {
        id: '1',
        title: 'React Docs',
        url: 'https://react.dev',
        type: 'documentation',
        similarity: 0.95,
        chunk_index: 0,
        metadata: {}
      },
      {
        id: '2',
        title: 'MDN Web Docs',
        url: 'https://mdn.dev',
        type: 'documentation',
        similarity: 0.87,
        chunk_index: 0,
        metadata: {}
      },
    ];

    act(() => {
      eventHandlers['chat:sources']({ sources: testSources, timestamp: new Date().toISOString() });
    });

    // Sources stored but not yet attached to message
    await waitFor(() => {
      expect(result.current.messages[1].sources).toBeUndefined();
    });
  });

  // TC-009: useChat Finalizes Message on Done Event
  it('TC-009: finalizes message with sources on done event', async () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    // Send message
    act(() => {
      result.current.sendMessage('Test query');
    });

    // Receive chunk
    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'Complete response',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    // Receive sources - need to match backend format
    const testSources = [
      {
        id: '1',
        title: 'React Docs',
        url: 'https://react.dev',
        type: 'documentation',
        similarity: 0.95,
        chunk_index: 0,
        metadata: {}
      },
    ];

    act(() => {
      eventHandlers['chat:sources']({ sources: testSources, timestamp: new Date().toISOString() });
    });

    // Receive done event
    act(() => {
      eventHandlers['chat:done']({});
    });

    await waitFor(() => {
      expect(result.current.messages[1].isStreaming).toBe(false);
      expect(result.current.messages[1].sources).toBeDefined();
      expect(result.current.isStreaming).toBe(false);
    }, { timeout: 2000 });
  });

  // TC-010: useChat Handles Chat Error
  it('TC-010: removes streaming message on error', async () => {
    const onError = vi.fn();
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session', onError }));

    // Send message
    act(() => {
      result.current.sendMessage('Test query');
    });

    // Start streaming
    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'Partial response',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    expect(result.current.messages).toHaveLength(2);

    // Simulate error
    const errorData = { error: 'Failed to retrieve context', timestamp: new Date().toISOString() };
    act(() => {
      eventHandlers['chat:error'](errorData);
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(1); // Only user message remains
      expect(onError).toHaveBeenCalledWith(errorData);
      expect(result.current.isStreaming).toBe(false);
    });
  });

  // TC-011: useChat Optimistic Updates
  it('TC-011: adds user message immediately (optimistic update)', () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    act(() => {
      result.current.sendMessage('Test query');
    });

    // Check that message is added synchronously
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      content: 'Test query',
      role: 'user',
    });
    expect(result.current.messages[0].id).toBeDefined();
    expect(result.current.messages[0].timestamp).toBeDefined();
  });

  // TC-012: useChat Clear Messages
  it('TC-012: clears all messages', async () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    // Send multiple messages
    act(() => {
      result.current.sendMessage('Message 1');
    });

    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'Response 1',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    act(() => {
      eventHandlers['chat:done']({});
    });

    expect(result.current.messages).toHaveLength(2);

    // Clear messages
    act(() => {
      result.current.clearMessages();
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(0);
    });
  });

  // TC-013: Multiple Concurrent Streaming Messages
  it('TC-013: handles multiple messages correctly', async () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    // Send first message
    act(() => {
      result.current.sendMessage('What is TypeScript?');
    });

    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'TypeScript is ',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    expect(result.current.messages).toHaveLength(2);

    // Complete first message
    act(() => {
      eventHandlers['chat:done']({});
    });

    // Send second message
    act(() => {
      result.current.sendMessage('What is React?');
    });

    act(() => {
      eventHandlers['chat:chunk']({
        chunk: 'React is ',
        chunk_index: 0,
        timestamp: new Date().toISOString()
      });
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4);
      expect(result.current.messages[0].content).toBe('What is TypeScript?');
      expect(result.current.messages[1].content).toBe('TypeScript is ');
      expect(result.current.messages[2].content).toBe('What is React?');
      expect(result.current.messages[3].content).toBe('React is ');
    });
  });

  // Test cleanup on unmount
  it('cleans up event listeners on unmount', () => {
    const { unmount } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    expect(mockSocket.on).toHaveBeenCalledWith('chat:chunk', expect.any(Function));
    expect(mockSocket.on).toHaveBeenCalledWith('chat:sources', expect.any(Function));
    expect(mockSocket.on).toHaveBeenCalledWith('chat:done', expect.any(Function));
    expect(mockSocket.on).toHaveBeenCalledWith('chat:error', expect.any(Function));

    unmount();

    expect(mockSocket.off).toHaveBeenCalledWith('chat:chunk', expect.any(Function));
    expect(mockSocket.off).toHaveBeenCalledWith('chat:sources', expect.any(Function));
    expect(mockSocket.off).toHaveBeenCalledWith('chat:done', expect.any(Function));
    expect(mockSocket.off).toHaveBeenCalledWith('chat:error', expect.any(Function));
  });

  // Test sending message with options
  it('sends message with options', () => {
    const { result } = renderHook(() => useChat({ socket: mockSocket, sessionId: 'test-session' }));

    const options = { top_k: 15, temperature: 0.9 };

    act(() => {
      result.current.sendMessage('Test query', options);
    });

    expect(mockSocket.emit).toHaveBeenCalledWith('chat:query', {
      query: 'Test query',
      top_k: 15,
      temperature: 0.9,
    });
  });
});
