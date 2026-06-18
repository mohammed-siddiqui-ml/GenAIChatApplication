import { Box, Typography, Button, Container } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { Chat as ChatIcon } from '@mui/icons-material';

export function HomePage() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '80vh',
          textAlign: 'center',
        }}
      >
        <Typography variant="h2" component="h1" gutterBottom>
          GenAI Knowledge Retrieval System
        </Typography>
        <Typography
          variant="h5"
          color="text.secondary"
          paragraph
          sx={{ mb: 4 }}
        >
          Get accurate, context-aware responses from multiple knowledge sources
          through an intelligent conversational interface.
        </Typography>
        <Button
          variant="contained"
          size="large"
          startIcon={<ChatIcon />}
          onClick={() => navigate('/chat')}
          sx={{ px: 4, py: 1.5 }}
        >
          Start Chat
        </Button>
      </Box>
    </Container>
  );
}
