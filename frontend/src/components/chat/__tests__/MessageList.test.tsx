import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MessageList } from '../MessageList';
import type { Message } from '../../../types';

// Mock react-window
vi.mock('react-window', () => ({
  List: ({ rowComponent, rowCount }: any) => (
    <div data-testid="virtualized-list">
      {Array.from({ length: rowCount }).map((_, index) => (
        <div key={index} data-testid={`list-row-${index}`}>
          {rowComponent({ index })}
        </div>
      ))}
    </div>
  ),
}));

// Mock ReactMarkdown
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown-content">{children}</div>
  ),
}));

describe('MessageList', () => {
  const mockUserMessage: Message = {
    id: 'user-1',
    content: 'Hello, I need help',
    role: 'user',
    timestamp: '2024-01-15T10:00:00Z',
    sessionId: 'test-session',
  };

  const mockAssistantMessage: Message = {
    id: 'asst-1',
    content: '**Bold** text',
    role: 'assistant',
    timestamp: '2024-01-15T10:01:00Z',
    sessionId: 'test-session',
  };

  const mockSystemMessage: Message = {
    id: 'sys-1',
    content: 'Error: Connection timeout',
    role: 'system',
    timestamp: '2024-01-15T10:02:00Z',
    sessionId: 'test-session',
  };

  // TC-ML-001: Empty state display
  it('should display empty state when no messages', () => {
    render(<MessageList messages={[]} />);

    expect(
      screen.getByText('No messages yet. Start a conversation!')
    ).toBeInTheDocument();
  });

  // TC-ML-002: Render user message
  it('should render user message with correct styling', () => {
    render(<MessageList messages={[mockUserMessage]} />);

    // Verify message content is displayed
    expect(screen.getByText('Hello, I need help')).toBeInTheDocument();

    // Verify timestamp is displayed
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
  });

  // TC-ML-003: Render assistant message with markdown
  it('should render assistant message with markdown', () => {
    render(<MessageList messages={[mockAssistantMessage]} />);

    // Verify markdown content is rendered
    expect(screen.getByTestId('markdown-content')).toBeInTheDocument();
    expect(screen.getByText('**Bold** text')).toBeInTheDocument();
  });

  // TC-ML-004: Render system message
  it('should render system message with plain text', () => {
    render(<MessageList messages={[mockSystemMessage]} />);

    // Verify system message content
    expect(screen.getByText('Error: Connection timeout')).toBeInTheDocument();
  });

  // TC-ML-005: Display source citations
  it('should display source citations for assistant messages', () => {
    const messageWithSources: Message = {
      ...mockAssistantMessage,
      sources: [
        {
          id: 'src-1',
          title: 'API Documentation',
          type: 'documentation',
          url: 'https://example.com/api-docs',
          excerpt: 'API endpoint details...',
        },
        {
          id: 'src-2',
          title: 'PROJ-123: Feature Request',
          type: 'issue',
          url: 'https://jira.example.com/PROJ-123',
          excerpt: 'Feature implementation notes...',
        },
      ],
    };

    render(<MessageList messages={[messageWithSources]} />);

    // Verify "Sources:" label
    expect(screen.getByText('Sources:')).toBeInTheDocument();

    // Verify source links
    expect(screen.getByText('API Documentation')).toBeInTheDocument();
    expect(screen.getByText('PROJ-123: Feature Request')).toBeInTheDocument();

    // Verify links have correct attributes
    const links = screen.getAllByRole('link');
    expect(links[0]).toHaveAttribute('target', '_blank');
    expect(links[0]).toHaveAttribute('rel', 'noopener noreferrer');
  });

  // TC-ML-006: Render multiple messages
  it('should render multiple messages in correct order', () => {
    const messages = [mockUserMessage, mockAssistantMessage, mockSystemMessage];

    render(<MessageList messages={messages} />);

    // Verify all messages are rendered
    expect(screen.getByText('Hello, I need help')).toBeInTheDocument();
    expect(screen.getByText('**Bold** text')).toBeInTheDocument();
    expect(screen.getByText('Error: Connection timeout')).toBeInTheDocument();

    // Verify virtualized list is used
    expect(screen.getByTestId('virtualized-list')).toBeInTheDocument();
  });

  // TC-ML-007: Typing indicator display
  it('should show typing indicator when isTyping is true', () => {
    render(<MessageList messages={[]} isTyping />);

    // Typing indicator should be visible (even with no messages)
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
  });

  it('should hide typing indicator when isTyping is false', () => {
    render(<MessageList messages={[mockUserMessage]} isTyping={false} />);

    // Typing indicator should not be visible
    expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();
  });
});
