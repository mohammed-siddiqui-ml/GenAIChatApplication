import { useEffect, useCallback, useState } from 'react';
import { useSocketContext } from '@contexts/SocketContext';

interface UseWebSocketOptions {
  sessionToken: string;
  sessionId: string;
  autoConnect?: boolean;
}

interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  error: Error | null;
}

/**
 * Custom hook for managing WebSocket connection lifecycle
 * 
 * Handles:
 * - Connection establishment with session authentication
 * - Automatic reconnection on disconnect
 * - Connection state management
 * - Error handling and recovery
 * 
 * @param options - Configuration options
 * @returns Connection state and control functions
 */
export function useWebSocket({
  sessionToken,
  sessionId,
  autoConnect = true,
}: UseWebSocketOptions) {
  const { socket, isConnected, connect, disconnect } = useSocketContext();
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Handle connection
  const handleConnect = useCallback(() => {
    if (!sessionToken || !sessionId) {
      setError(new Error('Session token and session ID are required'));
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      connect(sessionToken, sessionId);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Connection failed'));
      setIsConnecting(false);
    }
  }, [sessionToken, sessionId, connect]);

  // Handle disconnect
  const handleDisconnect = useCallback(() => {
    disconnect();
    setIsConnecting(false);
  }, [disconnect]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && sessionToken && sessionId && !isConnected) {
      handleConnect();
    }

    return () => {
      // Cleanup on unmount
      if (socket) {
        handleDisconnect();
      }
    };
  }, [autoConnect, sessionToken, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update connecting state based on connection status
  useEffect(() => {
    if (isConnected) {
      setIsConnecting(false);
      setError(null);
    }
  }, [isConnected]);

  // Listen for connection errors
  useEffect(() => {
    if (!socket) return undefined;

    const handleError = (err: Error) => {
      setError(err);
      setIsConnecting(false);
    };

    socket.on('connect_error', handleError);
    socket.on('error', handleError);

    return () => {
      socket.off('connect_error', handleError);
      socket.off('error', handleError);
    };
  }, [socket]);

  const connectionState: ConnectionState = {
    isConnected,
    isConnecting,
    error,
  };

  return {
    ...connectionState,
    connect: handleConnect,
    disconnect: handleDisconnect,
    socket,
  };
}
