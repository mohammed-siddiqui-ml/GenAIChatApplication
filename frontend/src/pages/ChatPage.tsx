import { useState, useEffect } from 'react';
import { Box, Container, CircularProgress, Alert, Button } from '@mui/material';
import { ChatWindow } from '@components/index';
import { getOrCreateSession } from '../services/chatService';

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string>('');
  const [sessionToken, setSessionToken] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  const initSession = async () => {
    setLoading(true);
    setError('');
    try {
      const session = await getOrCreateSession();
      setSessionId(session.sessionId);
      setSessionToken(session.sessionToken);
      // Store token for WebSocket authentication
      localStorage.setItem('token', session.sessionToken);
      console.log('Chat session initialized:', session.sessionId);
    } catch (error) {
      console.error('Failed to initialize chat session:', error);
      setError(error instanceof Error ? error.message : 'Failed to create chat session');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    initSession();
  }, []);

  const handleMessageSent = (message: string) => {
    console.log('Message sent:', message);
    // Additional message handling logic can go here
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ height: 'calc(100vh - 64px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ height: 'calc(100vh - 64px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Box sx={{ textAlign: 'center' }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
          <Button variant="contained" onClick={initSession}>
            Retry
          </Button>
        </Box>
      </Container>
    );
  }

  if (!sessionId || !sessionToken) {
    return (
      <Container maxWidth="lg" sx={{ height: 'calc(100vh - 64px)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <Alert severity="warning">
          Unable to initialize chat session. Please refresh the page.
        </Alert>
      </Container>
    );
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
