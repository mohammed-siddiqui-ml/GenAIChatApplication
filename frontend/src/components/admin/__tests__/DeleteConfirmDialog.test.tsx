import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DeleteConfirmDialog } from '../DeleteConfirmDialog';

describe('DeleteConfirmDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnConfirm = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // TC-021: Open delete confirmation dialog
  it('should display dialog when open prop is true', () => {
    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test Data Source"
        isDeleting={false}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Confirm Delete')).toBeInTheDocument();
  });

  // TC-022: Display data source name
  it('should display data source name in confirmation message', () => {
    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="My Important Source"
        isDeleting={false}
      />
    );

    expect(screen.getByText(/My Important Source/)).toBeInTheDocument();
  });

  // TC-023: Show warning about cascade deletion
  it('should show warning about cascade deletion', () => {
    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting={false}
      />
    );

    expect(
      screen.getByText(/This operation cannot be undone/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Delete the data source permanently/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Remove all associated knowledge documents/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Remove all associated document embeddings/)
    ).toBeInTheDocument();
  });

  // TC-024: Cancel deletion
  it('should call onClose when Cancel button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting={false}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
    expect(mockOnConfirm).not.toHaveBeenCalled();
  });

  // TC-025: Confirm deletion
  it('should call onConfirm when Delete button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting={false}
      />
    );

    const deleteButton = screen.getByText('Delete');
    await user.click(deleteButton);

    expect(mockOnConfirm).toHaveBeenCalled();
  });

  // TC-027: Disable buttons during deletion
  it('should disable buttons when isDeleting is true', () => {
    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting
      />
    );

    const cancelButton = screen.getByText('Cancel');
    const deleteButton = screen.getByText('Deleting...');

    expect(cancelButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
  });

  // Not open
  it('should not display dialog when open prop is false', () => {
    render(
      <DeleteConfirmDialog
        open={false}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting={false}
      />
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  // Error button styling
  it('should style Delete button as error', () => {
    render(
      <DeleteConfirmDialog
        open
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        dataSourceName="Test"
        isDeleting={false}
      />
    );

    const deleteButton = screen.getByText('Delete');
    expect(deleteButton).toHaveClass('MuiButton-containedError');
  });
});
