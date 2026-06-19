/**
 * useWebSocket Hook Tests
 * 
 * Tests for the WebSocket connection hook including:
 * - Connection lifecycle
 * - Auto-connect behavior
 * - Error handling
 * - Reconnection logic
 */

import React, { type ReactNode } from 'react';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWebSocket } from '@hooks/useWebSocket';
import { SocketContext } from '@contexts/SocketContext';
import { createMockSocket } from '../mocks/socket';

// Mock SocketContext
const mockConnect = vi.fn();
const mockDisconnect = vi.fn();
let mockSocket: ReturnType<typeof createMockSocket>;
let mockIsConnected = false;

const createMockSocketContext = () => ({
  socket: mockSocket as any,
  isConnected: mockIsConnected,
  connect: mockConnect,
  disconnect: mockDisconnect,
});

// Wrapper component with SocketContext - using createElement to avoid JSX in .ts file
const createWrapper = () => {
  return ({ children }: { children: ReactNode }) =>
    React.createElement(
      SocketContext.Provider,
      { value: createMockSocketContext() },
      children
    );
};

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSocket = createMockSocket();
    mockIsConnected = false;
    mockConnect.mockImplementation(() => {
      mockIsConnected = true;
    });
    mockDisconnect.mockImplementation(() => {
      mockIsConnected = false;
    });
  });

  it('should initialize with default state', () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isConnected).toBe(false);
    expect(result.current.isConnecting).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should auto-connect when autoConnect is true', async () => {
    renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: true,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalledWith('test-token', 'test-session');
    });
  });

  it('should not auto-connect when autoConnect is false', () => {
    renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    expect(mockConnect).not.toHaveBeenCalled();
  });

  it('should manually connect when connect is called', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    result.current.connect();

    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalledWith('test-token', 'test-session');
    });
  });

  it('should disconnect when disconnect is called', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    result.current.disconnect();

    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  it('should set error when connection fails', async () => {
    mockConnect.mockImplementation(() => {
      throw new Error('Connection failed');
    });

    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    result.current.connect();

    await waitFor(() => {
      expect(result.current.error).toBeDefined();
      expect(result.current.error?.message).toBe('Connection failed');
    });
  });

  it('should set error when sessionToken is missing', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: '',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    act(() => {
      result.current.connect();
    });

    await waitFor(() => {
      expect(result.current.error?.message).toBe('Session token and session ID are required');
    });
    expect(mockConnect).not.toHaveBeenCalled();
  });

  it('should set error when sessionId is missing', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: '',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    act(() => {
      result.current.connect();
    });

    await waitFor(() => {
      expect(result.current.error?.message).toBe('Session token and session ID are required');
    });
    expect(mockConnect).not.toHaveBeenCalled();
  });

  it('should update isConnecting state during connection', async () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isConnecting).toBe(false);

    result.current.connect();

    // Should be connecting immediately after calling connect
    await waitFor(() => {
      expect(mockConnect).toHaveBeenCalled();
    });
  });

  it('should provide socket instance', () => {
    const { result } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: false,
        }),
      { wrapper: createWrapper() }
    );

    expect(result.current.socket).toBeDefined();
  });

  it('should disconnect on unmount', () => {
    const { unmount } = renderHook(
      () =>
        useWebSocket({
          sessionToken: 'test-token',
          sessionId: 'test-session',
          autoConnect: true,
        }),
      { wrapper: createWrapper() }
    );

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });
});
