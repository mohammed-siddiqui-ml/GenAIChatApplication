import { useEffect, useRef, memo } from 'react';
import { Box, Paper, Typography, Link, Chip } from '@mui/material';
import { List, ListImperativeAPI } from 'react-window';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../../types';
import { TypingIndicator } from './TypingIndicator';

interface MessageListProps {
  messages: Message[];
  isTyping?: boolean;
  containerHeight?: number;
}

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = memo(({ message }: MessageBubbleProps) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 2,
        px: 2,
      }}
    >
      <Box sx={{ maxWidth: '70%', minWidth: '100px' }}>
        <Paper
          elevation={1}
          sx={{
            px: 2,
            py: 1.5,
            backgroundColor: isUser
              ? 'primary.main'
              : isSystem
                ? 'grey.100'
                : 'background.paper',
            color: isUser ? 'white' : 'text.primary',
            borderRadius: 2,
            border: isSystem ? '1px solid' : 'none',
            borderColor: 'divider',
          }}
        >
          {isUser || isSystem ? (
            <Typography
              variant="body1"
              sx={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {message.content}
            </Typography>
          ) : (
            <Box sx={{ '& p': { margin: 0 }, '& pre': { overflowX: 'auto' } }}>
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </Box>
          )}

          {/* Source Citations */}
          {message.sources && message.sources.length > 0 && (
            <Box
              sx={{
                mt: 2,
                pt: 2,
                borderTop: '1px solid',
                borderColor: isUser ? 'rgba(255,255,255,0.3)' : 'divider',
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  mb: 1,
                  display: 'block',
                  fontWeight: 600,
                  color: isUser ? 'rgba(255,255,255,0.9)' : 'text.secondary',
                }}
              >
                📚 Sources ({message.sources.length}):
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {message.sources.map((source, index) => (
                  <Box
                    key={source.id}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                      flexWrap: 'wrap',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: isUser ? 'rgba(255,255,255,0.8)' : 'text.secondary',
                        fontWeight: 500,
                      }}
                    >
                      [{index + 1}]
                    </Typography>
                    <Chip
                      label={source.type}
                      size="small"
                      variant="outlined"
                      sx={{
                        textTransform: 'capitalize',
                        borderColor: isUser ? 'rgba(255,255,255,0.5)' : undefined,
                        color: isUser ? 'rgba(255,255,255,0.9)' : undefined,
                      }}
                    />
                    {source.url ? (
                      <Link
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        variant="caption"
                        sx={{
                          color: isUser ? 'rgba(255,255,255,0.95)' : 'primary.main',
                          textDecoration: 'none',
                          fontWeight: 500,
                          '&:hover': {
                            textDecoration: 'underline',
                            color: isUser ? 'white' : 'primary.dark',
                          },
                        }}
                      >
                        {source.title}
                      </Link>
                    ) : (
                      <Typography
                        variant="caption"
                        sx={{
                          color: isUser ? 'rgba(255,255,255,0.9)' : 'text.primary',
                          fontWeight: 500,
                        }}
                      >
                        {source.title}
                      </Typography>
                    )}
                    {(source.relevanceScore !== undefined || source.similarity !== undefined) && (
                      <Chip
                        label={`${Math.round((source.similarity || source.relevanceScore || 0) * 100)}% match`}
                        size="small"
                        color="success"
                        variant="outlined"
                        sx={{
                          ml: 'auto',
                          borderColor: isUser ? 'rgba(255,255,255,0.5)' : undefined,
                          color: isUser ? 'rgba(255,255,255,0.9)' : undefined,
                        }}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </Paper>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ ml: 1, mt: 0.5, display: 'block' }}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );
});

MessageBubble.displayName = 'MessageBubble';

export function MessageList({
  messages,
  isTyping = false,
  containerHeight = 600,
}: MessageListProps) {
  const listRef = useRef<ListImperativeAPI | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (listRef.current && messages.length > 0) {
      listRef.current.scrollToRow({
        index: messages.length - 1,
        align: 'end',
        behavior: 'smooth',
      });
    }
  }, [messages.length, isTyping]);

  // Create row component with messages in closure
  // eslint-disable-next-line react/no-unstable-nested-components
  function RowRenderer({ index }: { index: number }) {
    const message = messages[index];
    if (!message) return null;
    return <MessageBubble message={message} />;
  }

  if (messages.length === 0 && !isTyping) {
    return (
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: containerHeight,
        }}
      >
        <Typography color="text.secondary">
          No messages yet. Start a conversation!
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      ref={containerRef}
      sx={{ flex: 1, overflow: 'hidden', height: containerHeight }}
    >
      <List<Record<string, never>>
        listRef={listRef}
        defaultHeight={containerHeight}
        rowCount={messages.length}
        rowHeight={120}
        overscanCount={5}
        rowComponent={RowRenderer}
        rowProps={{} as Record<string, never>}
      />
      <TypingIndicator show={isTyping} />
    </Box>
  );
}
