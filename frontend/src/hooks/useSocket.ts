import { useEffect, useRef, useState, useCallback } from 'react';
import { socketService } from '../services/socket';
import type { Message, ApiError, Source } from '../types';

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

  // State for streaming message assembly
  const streamingMessageRef = useRef<string>('');
  const streamingSourcesRef = useRef<Source[]>([]);
  const isStreamingRef = useRef<boolean>(false);

  // Handle streaming chunks
  const handleChatChunk = useCallback((data: { chunk: string }) => {
    streamingMessageRef.current += data.chunk;
    isStreamingRef.current = true;

    // Notify typing indicator
    if (onTyping) {
      onTyping(true);
    }
  }, [onTyping]);

  // Handle sources
  const handleChatSources = useCallback((data: { sources: Source[] }) => {
    streamingSourcesRef.current = data.sources;
  }, []);

  // Handle completion
  const handleChatDone = useCallback((data: { message_id: number }) => {
    if (isStreamingRef.current && onMessage) {
      // Assemble complete message with sources
      const completeMessage: Message = {
        id: `msg-${data.message_id}`,
        content: streamingMessageRef.current,
        role: 'assistant',
        timestamp: new Date().toISOString(),
        sources: streamingSourcesRef.current,
        sessionId,
      };

      onMessage(completeMessage);

      // Reset streaming state
      streamingMessageRef.current = '';
      streamingSourcesRef.current = [];
      isStreamingRef.current = false;
    }

    // Clear typing indicator
    if (onTyping) {
      onTyping(false);
    }
  }, [onMessage, onTyping, sessionId]);

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

    // Setup RAG streaming event handlers
    socket.onChatChunk(handleChatChunk);
    socket.onChatSources(handleChatSources);
    socket.onChatDone(handleChatDone);

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
      socketInstance.off('chat:chunk');
      socketInstance.off('chat:sources');
      socketInstance.off('chat:done');
      socket.disconnect();
    };
  }, [sessionId, onMessage, onTyping, onError, autoConnect, handleChatChunk, handleChatSources, handleChatDone]);

  const sendMessage = (message: string) => {
    socketRef.current.sendMessage(message, sessionId);
  };

  return {
    sendMessage,
    isConnected,
  };
}
