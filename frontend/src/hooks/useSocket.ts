import { useEffect, useRef } from 'react';
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

  useEffect(() => {
    if (!autoConnect || !sessionId) return undefined;

    const socket = socketRef.current;
    socket.connect(sessionId);

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
      socket.disconnect();
    };
  }, [sessionId, onMessage, onTyping, onError, autoConnect]);

  const sendMessage = (message: string) => {
    socketRef.current.sendMessage(message, sessionId);
  };

  return {
    sendMessage,
    isConnected: socketRef.current.isConnected(),
  };
}
