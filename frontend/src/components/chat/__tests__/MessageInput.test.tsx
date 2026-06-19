import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { MessageInput } from '../MessageInput';

describe('MessageInput', () => {
  // TC-MI-001: Type and send message
  it('should call onSendMessage when send button is clicked', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();

    render(<MessageInput onSendMessage={onSendMessage} />);

    // Type message
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Test message');

    // Click send button
    const sendButton = screen.getByRole('button');
    await user.click(sendButton);

    // Verify callback called with trimmed message
    expect(onSendMessage).toHaveBeenCalledWith('Test message');

    // Verify input cleared
    expect(textarea).toHaveValue('');
  });

  // TC-MI-002: Send message with Enter key
  it('should send message when Enter key is pressed', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();

    render(<MessageInput onSendMessage={onSendMessage} />);

    // Type message
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, 'Hello{Enter}');

    // Verify message sent
    expect(onSendMessage).toHaveBeenCalledWith('Hello');

    // Verify input cleared
    expect(textarea).toHaveValue('');
  });

  // TC-MI-003: New line with Shift+Enter
  it('should add newline when Shift+Enter is pressed', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();

    render(<MessageInput onSendMessage={onSendMessage} />);

    const textarea = screen.getByPlaceholderText('Type your message...');

    // Type line 1
    await user.type(textarea, 'Line 1');

    // Press Shift+Enter
    await user.keyboard('{Shift>}{Enter}{/Shift}');

    // Type line 2
    await user.type(textarea, 'Line 2');

    // Verify both lines in textarea
    expect(textarea).toHaveValue('Line 1\nLine 2');

    // Verify message not sent
    expect(onSendMessage).not.toHaveBeenCalled();
  });

  // TC-MI-004: Disabled state
  it('should disable input and button when disabled prop is true', () => {
    const onSendMessage = vi.fn();

    render(
      <MessageInput
        onSendMessage={onSendMessage}
        disabled
        placeholder="Connecting..."
      />
    );

    // Verify textarea disabled
    const textarea = screen.getByPlaceholderText('Connecting...');
    expect(textarea).toBeDisabled();

    // Verify send button disabled
    const sendButton = screen.getByRole('button');
    expect(sendButton).toBeDisabled();
  });

  // TC-MI-005: Empty message handling
  it('should disable send button when message is empty or whitespace', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();

    render(<MessageInput onSendMessage={onSendMessage} />);

    const sendButton = screen.getByRole('button');

    // Initially disabled (empty)
    expect(sendButton).toBeDisabled();

    // Type spaces only
    const textarea = screen.getByPlaceholderText('Type your message...');
    await user.type(textarea, '   ');

    // Still disabled
    expect(sendButton).toBeDisabled();

    // onSendMessage should not be called
    expect(onSendMessage).not.toHaveBeenCalled();
  });

  // TC-MI-006: Send button enabled with valid text
  it('should enable send button when message has content', async () => {
    const user = userEvent.setup();
    const onSendMessage = vi.fn();

    render(<MessageInput onSendMessage={onSendMessage} />);

    const sendButton = screen.getByRole('button');
    const textarea = screen.getByPlaceholderText('Type your message...');

    // Initially disabled
    expect(sendButton).toBeDisabled();

    // Type valid message
    await user.type(textarea, 'Hello');

    // Button now enabled
    expect(sendButton).not.toBeDisabled();
  });
});
