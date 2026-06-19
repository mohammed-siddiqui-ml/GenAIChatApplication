import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DataSourceFormModal } from '../DataSourceFormModal';

describe('DataSourceFormModal', () => {
  const mockOnClose = vi.fn();
  const mockOnSubmit = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // TC-011: Validate required field (name)
  it('should show error when name field is empty', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    // Try to submit without filling name
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument();
    });

    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  // TC-012: Validate JSON config field
  it('should show error for invalid JSON in config field', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    // Fill name
    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Source');

    // Enter invalid JSON
    const configInput = screen.getByLabelText(/Config/);
    await user.clear(configInput);
    await user.paste('{{invalid json}}');

    // Try to submit
    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid JSON format')).toBeInTheDocument();
    });

    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  // TC-030: Config field - reject non-object JSON
  it('should reject array as config', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Source');

    const configInput = screen.getByLabelText(/Config/);
    await user.clear(configInput);
    await user.paste('[1, 2, 3]');

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText('Config must be a valid JSON object')
      ).toBeInTheDocument();
    });
  });

  // TC-032: Valid cron expression
  it('should accept valid cron expression', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Source');

    const cronInput = screen.getByLabelText(/Sync Schedule/);
    await user.type(cronInput, '0 2 * * *');

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });
  });

  // TC-034: Reject invalid cron format
  it('should reject invalid cron expression', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Source');

    const cronInput = screen.getByLabelText(/Sync Schedule/);
    await user.type(cronInput, 'invalid cron');

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Invalid cron expression/)).toBeInTheDocument();
    });

    expect(mockOnSubmit).not.toHaveBeenCalled();
  });

  // TC-035: Allow empty cron (optional field)
  it('should allow empty cron schedule', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Source');

    // Leave cron empty

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalled();
    });
  });

  // TC-016: Pre-fill form in edit mode
  it('should pre-fill form with initial data in edit mode', async () => {
    const initialData = {
      id: 1,
      name: 'Existing Source',
      type: 'jira' as const,
      config: { url: 'https://jira.com', project_key: 'PROJ' },
      sync_schedule: '0 1 * * *',
      is_active: true,
    };

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        initialData={initialData}
        isSubmitting={false}
      />
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue('Existing Source')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('0 1 * * *')).toBeInTheDocument();
    expect(screen.getByText('Update')).toBeInTheDocument();
  });

  // TC-018: Disable type field in edit mode
  it('should disable type field in edit mode', async () => {
    const initialData = {
      id: 1,
      name: 'Test',
      type: 'confluence' as const,
      config: {},
      sync_schedule: '',
      is_active: true,
    };

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        initialData={initialData}
        isSubmitting={false}
      />
    );

    // The select has aria-disabled on the actual select div
    // MUI Select doesn't associate the label with the combobox in accessible name,
    // so we query for all comboboxes and find the disabled one (Type field)
    const comboboxes = screen.getAllByRole('combobox');
    const disabledCombobox = comboboxes.find(
      (cb) => cb.getAttribute('aria-disabled') === 'true'
    );
    expect(disabledCombobox).toBeDefined();
    expect(disabledCombobox).toHaveAttribute('aria-disabled', 'true');
  });

  // TC-008: Fill form with valid data and submit
  it('should submit form with valid data', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const nameInput = screen.getByLabelText(/Name/);
    await user.type(nameInput, 'Test Confluence');

    const configInput = screen.getByLabelText(/Config/);
    await user.clear(configInput);
    await user.paste('{"url": "https://test.com"}');

    const cronInput = screen.getByLabelText(/Sync Schedule/);
    await user.type(cronInput, '0 3 * * *');

    const submitButton = screen.getByText('Create');
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Test Confluence',
          type: 'confluence',
          sync_schedule: '0 3 * * *',
          is_active: true,
        })
      );
    });
  });

  // Close modal
  it('should call onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();

    render(
      <DataSourceFormModal
        open
        onClose={mockOnClose}
        onSubmit={mockOnSubmit}
        isSubmitting={false}
      />
    );

    const cancelButton = screen.getByText('Cancel');
    await user.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });
});
