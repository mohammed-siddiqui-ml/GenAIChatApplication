import { useState, useCallback, useEffect, useRef } from 'react';
import { Socket } from 'socket.io-client';
import { v4 as uuidv4 } from 'uuid';
import type { Source } from '../types';

interface UseChatOptions {
  socket: Socket | null;
  sessionId: string;
  onError?: (error: { error: string; type?: string; timestamp: string }) => void;
}

interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: string;
  sources?: Source[];
  isStreaming?: boolean;
}

/**
 * Custom hook for chat operations using WebSocket
 * 
 * Handles:
 * - Sending messages via chat:query event
 * - Receiving streaming responses via chat:chunk
 * - Receiving source citations via chat:sources
 * - Receiving completion metadata via chat:done
 * - Error handling via chat:error
 * - Optimistic updates for user messages
 * - Message state management
 * 
 * @param options - Configuration options
 * @returns Chat state and operations
 */
export function useChat({ socket, onError }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamingMessageRef = useRef<string>('');
  const streamingIdRef = useRef<string>('');
  const sourcesRef = useRef<Source[]>([]);

  // Send message to server
  const sendMessage = useCallback(
    (query: string, options?: { top_k?: number; temperature?: number }) => {
      if (!socket || !socket.connected) {
        console.error('Socket not connected');
        return;
      }

      if (!query.trim()) {
        console.error('Query cannot be empty');
        return;
      }

      // Optimistic update - add user message immediately
      const userMessage: ChatMessage = {
        id: uuidv4(),
        content: query,
        role: 'user',
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);

      // Reset streaming state
      setIsStreaming(true);
      streamingMessageRef.current = '';
      streamingIdRef.current = uuidv4();
      sourcesRef.current = [];

      // Emit query to server
      socket.emit('chat:query', {
        query,
        top_k: options?.top_k || 10,
        temperature: options?.temperature || 0.7,
      });
    },
    [socket]
  );

  // Handle incoming message chunks
  useEffect(() => {
    if (!socket) return undefined;

    const handleChunk = (data: {
      chunk: string;
      chunk_index: number;
      timestamp: string;
    }) => {
      streamingMessageRef.current += data.chunk;

      // Update the streaming message in state
      setMessages((prev) => {
        const existingIndex = prev.findIndex(
          (msg) => msg.id === streamingIdRef.current
        );

        const streamingMessage: ChatMessage = {
          id: streamingIdRef.current,
          content: streamingMessageRef.current,
          role: 'assistant',
          timestamp: data.timestamp,
          isStreaming: true,
        };

        if (existingIndex >= 0) {
          // Update existing streaming message
          const newMessages = [...prev];
          newMessages[existingIndex] = streamingMessage;
          return newMessages;
        }
        // Add new streaming message
        return [...prev, streamingMessage];
      });
    };

    const handleSources = (data: {
      sources: Array<{
        id: string;
        title: string;
        url: string;
        type: string;
        similarity: number;
        chunk_index: number;
        metadata: Record<string, unknown>;
      }>;
      timestamp: string;
    }) => {
      // Store sources to attach to final message
      sourcesRef.current = data.sources.map((src) => ({
        id: src.id,
        title: src.title,
        type: src.type as 'confluence' | 'issue' | 'onboarding' | 'documentation',
        url: src.url,
        excerpt: '', // Backend doesn't send excerpt in this event
        relevanceScore: src.similarity,
      }));
    };

    const handleDone = () => {
      // Capture the current streaming ID and sources before resetting
      const currentStreamingId = streamingIdRef.current;
      const currentSources = [...sourcesRef.current];

      // Finalize the streaming message with sources
      setMessages((prev) => {
        const index = prev.findIndex((msg) => msg.id === currentStreamingId);

        if (index >= 0) {
          const newMessages = [...prev];
          newMessages[index] = {
            ...newMessages[index],
            isStreaming: false,
            sources: currentSources.length > 0 ? currentSources : undefined,
          };
          return newMessages;
        }
        return prev;
      });

      // Set streaming to false after updating message
      setIsStreaming(false);

      // Reset refs after state updates are queued
      streamingMessageRef.current = '';
      streamingIdRef.current = '';
      sourcesRef.current = [];
    };

    const handleError = (data: {
      error: string;
      type?: string;
      timestamp: string;
    }) => {
      console.error('Chat error:', data);

      // Remove streaming message if exists
      const currentStreamingId = streamingIdRef.current;
      if (currentStreamingId) {
        setMessages((prev) =>
          prev.filter((msg) => msg.id !== currentStreamingId)
        );
      }

      // Set streaming to false after filtering
      setIsStreaming(false);

      // Reset refs
      streamingMessageRef.current = '';
      streamingIdRef.current = '';
      sourcesRef.current = [];

      // Call error callback if provided
      if (onError) {
        onError(data);
      }
    };

    // Register event listeners
    socket.on('chat:chunk', handleChunk);
    socket.on('chat:sources', handleSources);
    socket.on('chat:done', handleDone);
    socket.on('chat:error', handleError);

    // Cleanup
    return () => {
      socket.off('chat:chunk', handleChunk);
      socket.off('chat:sources', handleSources);
      socket.off('chat:done', handleDone);
      socket.off('chat:error', handleError);
    };
  }, [socket, onError]);

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    clearMessages,
  };
}
