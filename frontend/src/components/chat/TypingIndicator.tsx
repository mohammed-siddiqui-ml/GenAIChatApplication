import { Box, Typography } from '@mui/material';
import { keyframes } from '@mui/system';

const bounce = keyframes`
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-8px);
  }
`;

interface TypingIndicatorProps {
  show: boolean;
}

export function TypingIndicator({ show }: TypingIndicatorProps) {
  if (!show) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        px: 2,
        py: 1.5,
        mb: 1,
        maxWidth: '70%',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          gap: 0.5,
          alignItems: 'center',
          backgroundColor: 'grey.200',
          borderRadius: 3,
          px: 2,
          py: 1.5,
        }}
      >
        <Typography variant="body2" color="text.secondary" sx={{ mr: 0.5 }}>
          Assistant is typing
        </Typography>
        {[0, 1, 2].map((index) => (
          <Box
            key={index}
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              backgroundColor: 'grey.600',
              animation: `${bounce} 1.4s infinite ease-in-out`,
              animationDelay: `${index * 0.16}s`,
            }}
          />
        ))}
      </Box>
    </Box>
  );
}
