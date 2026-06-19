import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatWindow } from '../ChatWindow';
import type { Message } from '../../../types';

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

// Mock ReactMarkdown
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}));

describe('ChatWindow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSocket.isConnected = true;
  });

  // TC-CW-001: Initial render with default props
  it('should render with default title and connection status', () => {
    render(<ChatWindow sessionId="test-session-123" />);

    // Verify default title
    expect(screen.getByText('Chat Assistant')).toBeInTheDocument();

    // Verify connection status (connected)
    expect(screen.getByText('Connected')).toBeInTheDocument();

    // Verify empty state
    expect(
      screen.getByText('No messages yet. Start a conversation!')
    ).toBeInTheDocument();

    // Verify input is present
    expect(
      screen.getByPlaceholderText('Type your message...')
    ).toBeInTheDocument();
  });

  // TC-CW-002: Render with initial messages
  it('should render with initial messages', () => {
    const initialMessages: Message[] = [
      {
        id: 'user-1',
        content: 'Hello',
        role: 'user',
        timestamp: '2024-01-15T10:00:00Z',
        sessionId: 'test-session-123',
      },
      {
        id: 'asst-1',
        content: 'Hi there!',
        role: 'assistant',
        timestamp: '2024-01-15T10:01:00Z',
        sessionId: 'test-session-123',
      },
    ];

    render(
      <ChatWindow
        sessionId="test-session-123"
        initialMessages={initialMessages}
      />
    );

    // Verify messages are displayed
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there!')).toBeInTheDocument();
  });

  // TC-CW-003: Send message successfully
  it('should send message and show in message list', async () => {
    const user = userEvent.setup();
    const onMessageSent = vi.fn();

    render(
      <ChatWindow sessionId="test-session-123" onMessageSent={onMessageSent} />
    );

    // Type message
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Hello');

    // Click send button
    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    // Verify user message appears
    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });

    // Verify WebSocket sendMessage called
    expect(mockSendMessage).toHaveBeenCalledWith('Hello');

    // Verify parent callback called
    expect(onMessageSent).toHaveBeenCalledWith('Hello');

    // Verify typing indicator shows
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
  });

  // TC-CW-006: Connection status indicator
  it('should show connecting status when not connected', () => {
    mockUseSocket.isConnected = false;

    render(<ChatWindow sessionId="test-session-123" />);

    // Verify "Connecting..." status
    expect(screen.getByText('Connecting...')).toBeInTheDocument();

    // Verify input placeholder reflects connection status
    expect(screen.getByPlaceholderText('Connecting...')).toBeInTheDocument();
  });

  // Custom title
  it('should render with custom title', () => {
    render(<ChatWindow sessionId="test-session-123" title="Custom Chat" />);

    expect(screen.getByText('Custom Chat')).toBeInTheDocument();
  });
});
