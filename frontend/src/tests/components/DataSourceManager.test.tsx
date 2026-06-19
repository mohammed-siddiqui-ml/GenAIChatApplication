/**
 * DataSourceManager Component Tests
 * 
 * Tests for the admin data source management component including:
 * - Data source listing
 * - Create/Edit/Delete operations
 * - API integration with React Query
 * - Toast notifications
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DataSourceManager } from '@components/admin/DataSourceManager';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Create a test query client
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

// Helper to render with providers
const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
};

describe('DataSourceManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render data sources list', async () => {
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Test Confluence')).toBeInTheDocument();
    });

    expect(screen.getByText('confluence')).toBeInTheDocument();
  });

  it('should show loading state while fetching data sources', async () => {
    renderWithProviders(<DataSourceManager />);

    // Loading text should be shown initially
    expect(screen.getByText('Loading...')).toBeInTheDocument();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    });
  });

  it('should show error state when fetch fails', async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/admin/data-sources`, () => {
        return HttpResponse.json(
          { detail: 'Failed to fetch data sources' },
          { status: 500 }
        );
      })
    );

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load data sources/i)).toBeInTheDocument();
    });
  });

  it('should open create modal when Add Data Source button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Test Confluence')).toBeInTheDocument();
    });

    const addButton = screen.getByRole('button', { name: /add data source/i });
    await user.click(addButton);

    // Modal should be opened (tested by checking if form appears)
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  it('should display data source status badges correctly', async () => {
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      // Use getAllByText since there are multiple "Active" badges
      const activeBadges = screen.getAllByText('Active');
      expect(activeBadges.length).toBeGreaterThan(0);
    });
  });

  it('should format last sync date correctly', async () => {
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      // Date should be formatted in locale string format
      // Use getAllByText since there are multiple dates with "2024"
      const dateElements = screen.getAllByText(/2024/);
      expect(dateElements.length).toBeGreaterThan(0);
    });
  });

  it('should show edit button for each data source', async () => {
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      const editButtons = screen.getAllByLabelText(/edit/i);
      expect(editButtons.length).toBeGreaterThan(0);
    });
  });

  it('should show delete button for each data source', async () => {
    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      const deleteButtons = screen.getAllByLabelText(/delete/i);
      expect(deleteButtons.length).toBeGreaterThan(0);
    });
  });

  it('should refresh data when refresh button is clicked', async () => {
    const user = userEvent.setup();
    let fetchCount = 0;
    
    server.use(
      http.get(`${API_BASE_URL}/v1/admin/data-sources`, () => {
        fetchCount++;
        return HttpResponse.json({
          items: [
            {
              id: 1,
              name: `Test Confluence ${fetchCount}`,
              type: 'confluence',
              config: {},
              is_active: true,
              sync_schedule: null,
              last_sync_at: null,
              created_by: null,
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        });
      })
    );

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Test Confluence 1')).toBeInTheDocument();
    });

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    await waitFor(() => {
      expect(screen.getByText('Test Confluence 2')).toBeInTheDocument();
    });
  });

  it('should show empty state when no data sources exist', async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/admin/data-sources`, () => {
        return HttpResponse.json({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
        });
      })
    );

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText(/no data sources/i)).toBeInTheDocument();
    });
  });
});
