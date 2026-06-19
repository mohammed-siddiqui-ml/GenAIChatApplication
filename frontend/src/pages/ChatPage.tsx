import { useState, useEffect } from 'react';
import { Box, Container } from '@mui/material';
import { ChatWindow } from '@components/index';
import { v4 as uuidv4 } from 'uuid';

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string>('');

  useEffect(() => {
    // Generate or retrieve session ID
    let storedSessionId = localStorage.getItem('currentSessionId');

    if (!storedSessionId) {
      storedSessionId = uuidv4();
      localStorage.setItem('currentSessionId', storedSessionId);
    }

    setSessionId(storedSessionId);
  }, []);

  const handleMessageSent = (message: string) => {
    console.log('Message sent:', message);
    // Additional message handling logic can go here
  };

  if (!sessionId) {
    return null; // or a loading spinner
  }

  return (
    <Container
      maxWidth="lg"
      sx={{
        height: 'calc(100vh - 64px)', // Adjust based on your layout header height
        py: 2,
      }}
    >
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <ChatWindow
          sessionId={sessionId}
          title="GenAI Knowledge Assistant"
          onMessageSent={handleMessageSent}
        />
      </Box>
    </Container>
  );
}
