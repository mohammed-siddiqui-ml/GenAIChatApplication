import { useState, useCallback, useEffect } from 'react';
import { Box, Paper, Typography, Divider } from '@mui/material';
import { useSocket } from '@hooks/useSocket';
import type { Message } from '../../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';

interface ChatWindowProps {
  sessionId: string;
  initialMessages?: Message[];
  title?: string;
  onMessageSent?: (message: string) => void;
}

export function ChatWindow({
  sessionId,
  initialMessages = [],
  title = 'Chat Assistant',
  onMessageSent,
}: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [isTyping, setIsTyping] = useState(false);

  // Handle incoming messages via WebSocket
  const handleMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message]);
    setIsTyping(false);
  }, []);

  // Handle typing indicator
  const handleTyping = useCallback((typing: boolean) => {
    setIsTyping(typing);
  }, []);

  // Handle errors
  const handleError = useCallback(
    (error: { error?: string; message?: string }) => {
      console.error('Socket error:', error);
      // Add error message to chat
      const errorText = error.error || error.message || 'Unknown error occurred';
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        content: `Error: ${errorText}`,
        role: 'system',
        timestamp: new Date().toISOString(),
        sessionId,
      };
      setMessages((prev) => [...prev, errorMessage]);
      setIsTyping(false);
    },
    [sessionId]
  );

  // Initialize WebSocket connection
  const { sendMessage, isConnected } = useSocket({
    sessionId,
    onMessage: handleMessage,
    onTyping: handleTyping,
    onError: handleError,
  });

  // Update messages when initialMessages change
  useEffect(() => {
    if (initialMessages.length > 0) {
      setMessages(initialMessages);
    }
  }, [initialMessages]);

  // Handle sending a message
  const handleSendMessage = useCallback(
    (content: string) => {
      // Create user message
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        content,
        role: 'user',
        timestamp: new Date().toISOString(),
        sessionId,
      };

      // Add to local state immediately for optimistic UI
      setMessages((prev) => [...prev, userMessage]);

      // Send via WebSocket
      sendMessage(content);

      // Notify parent component
      if (onMessageSent) {
        onMessageSent(content);
      }

      // Show typing indicator
      setIsTyping(true);
    },
    [sessionId, sendMessage, onMessageSent]
  );

  return (
    <Paper
      elevation={3}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, backgroundColor: 'primary.main', color: 'white' }}>
        <Typography variant="h6">{title}</Typography>
        <Typography variant="caption" sx={{ opacity: 0.9 }}>
          {isConnected ? 'Connected' : 'Connecting...'}
        </Typography>
      </Box>

      <Divider />

      {/* Message List */}
      <Box
        sx={{
          flex: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <MessageList
          messages={messages}
          isTyping={isTyping}
          containerHeight={500}
        />
      </Box>

      {/* Message Input */}
      <MessageInput
        onSendMessage={handleSendMessage}
        disabled={!isConnected}
        placeholder={isConnected ? 'Type your message...' : 'Connecting...'}
      />
    </Paper>
  );
}
