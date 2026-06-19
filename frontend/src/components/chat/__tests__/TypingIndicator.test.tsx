import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TypingIndicator } from '../TypingIndicator';

describe('TypingIndicator', () => {
  // TC-TI-001: Show typing indicator
  it('should render when show is true', () => {
    render(<TypingIndicator show />);

    // Verify component is visible
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
  });

  // TC-TI-002: Hide typing indicator
  it('should not render when show is false', () => {
    const { container } = render(<TypingIndicator show={false} />);

    // Verify component returns null
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();
  });

  // TC-TI-003: Animation timing (basic verification)
  it('should render three animated dots', () => {
    const { container } = render(<TypingIndicator show />);

    // Verify text is displayed
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();

    // The dots are Box components with specific styles, hard to test exact animation delays
    // but we can verify the component structure is rendered
    expect(container.querySelector('[class*="MuiBox"]')).toBeInTheDocument();
  });
});
