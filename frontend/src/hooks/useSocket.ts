import { useEffect, useRef, useState } from 'react';
import { socketService } from '../services/socket';
import type { Message, ApiError } from '../types';

interface UseSocketOptions {
  sessionId: string;
  onMessage?: (message: Message) => void;
  onTyping?: (isTyping: boolean) => void;
  onError?: (error: ApiError) => void;
  autoConnect?: boolean;
}

export function useSocket({
  sessionId,
  onMessage,
  onTyping,
  onError,
  autoConnect = true,
}: UseSocketOptions) {
  const socketRef = useRef(socketService);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!autoConnect || !sessionId) return undefined;

    const socket = socketRef.current;
    const socketInstance = socket.connect(sessionId);

    // Track connection state
    const handleConnect = () => {
      console.log('Socket connected!');
      setIsConnected(true);
    };

    const handleDisconnect = () => {
      console.log('Socket disconnected!');
      setIsConnected(false);
    };

    const handleConnectError = (error: Error) => {
      console.error('Socket connection error:', error);
      setIsConnected(false);
    };

    // Listen to connection events
    socketInstance.on('connect', handleConnect);
    socketInstance.on('disconnect', handleDisconnect);
    socketInstance.on('connect_error', handleConnectError);

    // Set initial state
    setIsConnected(socketInstance.connected);

    if (onMessage) {
      socket.onMessage(onMessage);
    }

    if (onTyping) {
      socket.onTyping(onTyping);
    }

    if (onError) {
      socket.onError(onError);
    }

    return () => {
      socketInstance.off('connect', handleConnect);
      socketInstance.off('disconnect', handleDisconnect);
      socketInstance.off('connect_error', handleConnectError);
      socket.disconnect();
    };
  }, [sessionId, onMessage, onTyping, onError, autoConnect]);

  const sendMessage = (message: string) => {
    socketRef.current.sendMessage(message, sessionId);
  };

  return {
    sendMessage,
    isConnected,
  };
}
