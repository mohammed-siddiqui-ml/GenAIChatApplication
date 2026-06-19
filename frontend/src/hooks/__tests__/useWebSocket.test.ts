import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { io } from 'socket.io-client';
import React, { ReactNode } from 'react';
import { useWebSocket } from '../useWebSocket';
import { SocketProvider } from '../../contexts/SocketContext';

// Mock socket.io-client
vi.mock('socket.io-client');

describe('useWebSocket', () => {
  let mockSocket: any;
  let connectHandler: Function;
  let disconnectHandler: Function;
  let connectErrorHandler: Function;
  let errorHandler: Function;

  beforeEach(() => {
    // Create mock socket instance with event handlers
    const eventHandlers: Record<string, Function[]> = {};

    mockSocket = {
      on: vi.fn((event: string, handler: Function) => {
        if (!eventHandlers[event]) eventHandlers[event] = [];
        eventHandlers[event].push(handler);

        if (event === 'connect') connectHandler = handler;
        if (event === 'disconnect') disconnectHandler = handler;
        if (event === 'connect_error') connectErrorHandler = handler;
        if (event === 'error') errorHandler = handler;

        return mockSocket;
      }),
      emit: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      off: vi.fn(),
      connected: false,
      auth: {},
      io: {
        opts: { auth: {} },
      },
    };

    (io as any).mockReturnValue(mockSocket);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const wrapper = ({ children }: { children: ReactNode }) =>
    React.createElement(SocketProvider, null, children);

  // TC-003: useWebSocket Auto-Connects with Valid Credentials
  it('TC-003: auto-connects with valid credentials when autoConnect is true', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test_session_token_123',
          sessionId: '550e8400-e29b-41d4-a716-446655440000',
          autoConnect: true,
        }),
      { wrapper }
    );

    // Should attempt to connect
    await waitFor(() => {
      expect(mockSocket.connect).toHaveBeenCalled();
    });

    expect(result.current.isConnecting).toBe(true);

    // Simulate successful connection
    mockSocket.connected = true;
    connectHandler();

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
      expect(result.current.isConnecting).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });

  // TC-004: useWebSocket Handles Missing Credentials
  it('TC-004: does not connect without credentials', async () => {
    const { result } = renderHook(() => useWebSocket({ autoConnect: true }), {
      wrapper,
    });

    // Wait a bit to ensure no connection attempt
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockSocket.connect).not.toHaveBeenCalled();
    expect(result.current.isConnected).toBe(false);
    expect(result.current.isConnecting).toBe(false);
  });

  // TC-005: useWebSocket Handles Connection Error
  it('TC-005: handles connection errors correctly', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'token',
          sessionId: 'id',
          autoConnect: true,
        }),
      { wrapper }
    );

    await waitFor(() => {
      expect(mockSocket.connect).toHaveBeenCalled();
    });

    // Simulate connection error
    const error = new Error('Authentication failed');
    connectErrorHandler(error);

    await waitFor(() => {
      expect(result.current.error).toEqual(error);
      expect(result.current.isConnected).toBe(false);
    });
  });

  // Test manual connect
  it('manual connect with valid credentials', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'token',
          sessionId: 'id',
          autoConnect: false,
        }),
      { wrapper }
    );

    expect(mockSocket.connect).not.toHaveBeenCalled();

    // Manual connect
    result.current.connect();

    await waitFor(() => {
      expect(mockSocket.connect).toHaveBeenCalled();
    });
  });

  // Test manual disconnect
  it('manual disconnect works correctly', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'token',
          sessionId: 'id',
          autoConnect: true,
        }),
      { wrapper }
    );

    await waitFor(() => {
      expect(mockSocket.connect).toHaveBeenCalled();
    });

    // Connect first
    mockSocket.connected = true;
    connectHandler();

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // Now disconnect
    result.current.disconnect();

    expect(mockSocket.disconnect).toHaveBeenCalled();
  });
});
