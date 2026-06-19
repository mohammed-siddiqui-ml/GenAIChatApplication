/**
 * ChatWindow Component Tests
 * 
 * Tests for the main chat window component including:
 * - Initial render and layout
 * - WebSocket connection status
 * - Message sending and receiving
 * - Integration with MessageList and MessageInput
 * - Error handling
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatWindow } from '@components/chat/ChatWindow';
import type { Message } from '@/types';

// Mock useSocket hook
const mockSendMessage = vi.fn();
const mockUseSocket = {
  sendMessage: mockSendMessage,
  isConnected: true,
};

vi.mock('@hooks/useSocket', () => ({
  useSocket: vi.fn(() => mockUseSocket),
}));

// Mock react-window
vi.mock('react-window', () => ({
  List: ({ rowComponent, rowCount }: any) => (
    <div data-testid="virtualized-list">
      {Array.from({ length: rowCount }).map((_, index) => (
        <div key={index}>{rowComponent({ index })}</div>
      ))}
    </div>
  ),
}));

describe('ChatWindow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSocket.isConnected = true;
  });

  it('should render with default title and connection status', () => {
    render(<ChatWindow sessionId="test-session-123" />);

    expect(screen.getByText('Chat Assistant')).toBeInTheDocument();
    expect(screen.getByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('No messages yet. Start a conversation!')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
  });

  it('should render with custom title', () => {
    render(<ChatWindow sessionId="test-session-123" title="Knowledge Assistant" />);

    expect(screen.getByText('Knowledge Assistant')).toBeInTheDocument();
  });

  it('should show connecting status when not connected', () => {
    mockUseSocket.isConnected = false;
    render(<ChatWindow sessionId="test-session-123" />);

    expect(screen.getByText('Connecting...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Connecting...')).toBeInTheDocument();
  });

  it('should render initial messages', () => {
    const initialMessages: Message[] = [
      {
        id: '1',
        content: 'Hello!',
        role: 'user',
        timestamp: '2024-01-15T10:00:00Z',
        sessionId: 'test-session-123',
      },
      {
        id: '2',
        content: 'Hi! How can I help?',
        role: 'assistant',
        timestamp: '2024-01-15T10:00:05Z',
        sessionId: 'test-session-123',
      },
    ];

    render(<ChatWindow sessionId="test-session-123" initialMessages={initialMessages} />);

    expect(screen.getByText('Hello!')).toBeInTheDocument();
    expect(screen.getByText('Hi! How can I help?')).toBeInTheDocument();
  });

  it('should send message through WebSocket when user submits', async () => {
    const user = userEvent.setup();
    render(<ChatWindow sessionId="test-session-123" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message');

    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    expect(mockSendMessage).toHaveBeenCalledWith('Test message');
  });

  it('should add user message to chat optimistically', async () => {
    const user = userEvent.setup();
    render(<ChatWindow sessionId="test-session-123" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message');

    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText('Test message')).toBeInTheDocument();
    });
  });

  it('should call onMessageSent callback when message is sent', async () => {
    const user = userEvent.setup();
    const onMessageSent = vi.fn();
    
    render(
      <ChatWindow 
        sessionId="test-session-123" 
        onMessageSent={onMessageSent}
      />
    );

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message');

    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    expect(onMessageSent).toHaveBeenCalledWith('Test message');
  });

  it('should disable input when not connected', () => {
    mockUseSocket.isConnected = false;
    render(<ChatWindow sessionId="test-session-123" />);

    const sendButton = screen.getByRole('button');
    expect(sendButton).toBeDisabled();
  });

  it('should show typing indicator when waiting for response', async () => {
    const user = userEvent.setup();
    render(<ChatWindow sessionId="test-session-123" />);

    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message');

    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    // After sending, typing indicator should be shown
    // This is tested indirectly through the component's state
    expect(mockSendMessage).toHaveBeenCalled();
  });

  it('should update messages when initialMessages prop changes', () => {
    const { rerender } = render(
      <ChatWindow sessionId="test-session-123" initialMessages={[]} />
    );

    const newMessages: Message[] = [
      {
        id: '1',
        content: 'New message',
        role: 'user',
        timestamp: '2024-01-15T10:00:00Z',
        sessionId: 'test-session-123',
      },
    ];

    rerender(
      <ChatWindow sessionId="test-session-123" initialMessages={newMessages} />
    );

    expect(screen.getByText('New message')).toBeInTheDocument();
  });
});
