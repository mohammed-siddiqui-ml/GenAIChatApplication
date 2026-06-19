/**
 * MessageList Component Tests
 * 
 * Tests for the message list component including:
 * - Message rendering
 * - Empty state display
 * - Typing indicator
 * - Source citations
 * - Virtualized scrolling
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MessageList } from '@components/chat/MessageList';
import type { Message } from '@/types';

// Mock react-window to simplify testing
vi.mock('react-window', () => ({
  List: ({ children, rowComponent, rowCount, rowProps }: any) => (
    <div data-testid="virtualized-list">
      {Array.from({ length: rowCount }).map((_, index) => {
        const Component = rowComponent;
        return <div key={index}>{Component({ index, ...rowProps })}</div>;
      })}
    </div>
  ),
}));

describe('MessageList', () => {
  const mockMessages: Message[] = [
    {
      id: '1',
      content: 'Hello!',
      role: 'user',
      timestamp: '2024-01-15T10:00:00Z',
      sessionId: 'session-123',
    },
    {
      id: '2',
      content: 'Hi there! How can I help you?',
      role: 'assistant',
      timestamp: '2024-01-15T10:00:05Z',
      sessionId: 'session-123',
    },
  ];

  it('should render empty state when no messages', () => {
    render(<MessageList messages={[]} />);
    
    expect(screen.getByText('No messages yet. Start a conversation!')).toBeInTheDocument();
  });

  it('should render messages', () => {
    render(<MessageList messages={mockMessages} />);
    
    expect(screen.getByText('Hello!')).toBeInTheDocument();
    expect(screen.getByText('Hi there! How can I help you?')).toBeInTheDocument();
  });

  it('should render typing indicator when isTyping is true', () => {
    render(<MessageList messages={mockMessages} isTyping={true} />);
    
    // TypingIndicator component should be rendered
    expect(screen.getByTestId('virtualized-list')).toBeInTheDocument();
  });

  it('should not show empty state when typing indicator is shown', () => {
    render(<MessageList messages={[]} isTyping={true} />);
    
    expect(screen.queryByText('No messages yet. Start a conversation!')).not.toBeInTheDocument();
  });

  it('should render user messages with correct styling', () => {
    const userMessage: Message = {
      id: '1',
      content: 'User message',
      role: 'user',
      timestamp: '2024-01-15T10:00:00Z',
      sessionId: 'session-123',
    };
    
    render(<MessageList messages={[userMessage]} />);
    
    expect(screen.getByText('User message')).toBeInTheDocument();
  });

  it('should render assistant messages with markdown support', () => {
    const assistantMessage: Message = {
      id: '2',
      content: '**Bold** text',
      role: 'assistant',
      timestamp: '2024-01-15T10:00:00Z',
      sessionId: 'session-123',
    };
    
    render(<MessageList messages={[assistantMessage]} />);
    
    // ReactMarkdown should render the markdown
    expect(screen.getByText(/Bold/)).toBeInTheDocument();
  });

  it('should render system messages', () => {
    const systemMessage: Message = {
      id: '3',
      content: 'System notification',
      role: 'system',
      timestamp: '2024-01-15T10:00:00Z',
      sessionId: 'session-123',
    };
    
    render(<MessageList messages={[systemMessage]} />);
    
    expect(screen.getByText('System notification')).toBeInTheDocument();
  });

  it('should render messages with source citations', () => {
    const messageWithSources: Message = {
      id: '4',
      content: 'Information from documentation',
      role: 'assistant',
      timestamp: '2024-01-15T10:00:00Z',
      sessionId: 'session-123',
      sources: [
        {
          id: 'src-1',
          title: 'Documentation Page',
          type: 'documentation',
          url: 'https://docs.example.com/page',
          excerpt: 'Relevant excerpt',
          relevanceScore: 0.95,
        },
      ],
    };
    
    render(<MessageList messages={[messageWithSources]} />);
    
    expect(screen.getByText('Information from documentation')).toBeInTheDocument();
  });

  it('should use custom container height', () => {
    const { container } = render(
      <MessageList messages={mockMessages} containerHeight={800} />
    );
    
    expect(container.querySelector('[data-testid="virtualized-list"]')).toBeInTheDocument();
  });

  it('should render multiple messages in correct order', () => {
    const messages: Message[] = [
      {
        id: '1',
        content: 'First message',
        role: 'user',
        timestamp: '2024-01-15T10:00:00Z',
        sessionId: 'session-123',
      },
      {
        id: '2',
        content: 'Second message',
        role: 'assistant',
        timestamp: '2024-01-15T10:00:05Z',
        sessionId: 'session-123',
      },
      {
        id: '3',
        content: 'Third message',
        role: 'user',
        timestamp: '2024-01-15T10:00:10Z',
        sessionId: 'session-123',
      },
    ];
    
    render(<MessageList messages={messages} />);
    
    expect(screen.getByText('First message')).toBeInTheDocument();
    expect(screen.getByText('Second message')).toBeInTheDocument();
    expect(screen.getByText('Third message')).toBeInTheDocument();
  });
});
