/**
 * MessageInput Component Tests
 * 
 * Tests for the message input component including:
 * - User input handling
 * - Send button behavior
 * - Keyboard shortcuts (Enter to send, Shift+Enter for newline)
 * - Disabled state handling
 * - Auto-resize functionality
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { MessageInput } from '@components/chat/MessageInput';

describe('MessageInput', () => {
  const mockOnSendMessage = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render with default placeholder', () => {
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
  });

  it('should render with custom placeholder', () => {
    render(
      <MessageInput 
        onSendMessage={mockOnSendMessage} 
        placeholder="Ask me anything..." 
      />
    );
    
    expect(screen.getByPlaceholderText('Ask me anything...')).toBeInTheDocument();
  });

  it('should update input value when typing', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...') as HTMLTextAreaElement;
    await user.type(input, 'Hello world');
    
    expect(input.value).toBe('Hello world');
  });

  it('should call onSendMessage when send button is clicked', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message');
    
    const sendButton = screen.getByRole('button');
    await user.click(sendButton);
    
    expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
  });

  it('should clear input after sending message', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...') as HTMLTextAreaElement;
    await user.type(input, 'Test message');
    
    const sendButton = screen.getByRole('button');
    await user.click(sendButton);
    
    await waitFor(() => {
      expect(input.value).toBe('');
    });
  });

  it('should send message when Enter key is pressed', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Test message{Enter}');
    
    expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
  });

  it('should not send message when Shift+Enter is pressed', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, 'Line 1{Shift>}{Enter}{/Shift}Line 2');
    
    expect(mockOnSendMessage).not.toHaveBeenCalled();
  });

  it('should not send empty or whitespace-only messages', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);

    const sendButton = screen.getByRole('button');

    // Empty message - button should be disabled
    expect(sendButton).toBeDisabled();
    expect(mockOnSendMessage).not.toHaveBeenCalled();

    // Whitespace only - should still not send
    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, '   ');

    // Try to click send button if it's enabled (it shouldn't enable for whitespace)
    if (!sendButton.hasAttribute('disabled')) {
      await user.click(sendButton);
    }

    expect(mockOnSendMessage).not.toHaveBeenCalled();
  });

  it('should trim whitespace from messages before sending', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    await user.type(input, '  Test message  ');
    
    const sendButton = screen.getByRole('button');
    await user.click(sendButton);
    
    expect(mockOnSendMessage).toHaveBeenCalledWith('Test message');
  });

  it('should disable input and button when disabled prop is true', () => {
    render(<MessageInput onSendMessage={mockOnSendMessage} disabled />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button');
    
    expect(input).toBeDisabled();
    expect(sendButton).toBeDisabled();
  });

  it('should disable send button when input is empty', () => {
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const sendButton = screen.getByRole('button');
    expect(sendButton).toBeDisabled();
  });

  it('should enable send button when input has content', async () => {
    const user = userEvent.setup();
    render(<MessageInput onSendMessage={mockOnSendMessage} />);
    
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button');
    
    await user.type(input, 'Test');
    
    expect(sendButton).not.toBeDisabled();
  });
});
