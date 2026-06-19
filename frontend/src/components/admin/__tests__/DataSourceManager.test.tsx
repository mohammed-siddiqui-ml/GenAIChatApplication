import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DataSourceManager } from '../DataSourceManager';
import api from '../../../services/api';

// Mock API
vi.mock('../../../services/api');

const mockApi = vi.mocked(api);

// Create test QueryClient with disabled retries
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

// Test wrapper with providers
const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>
  );
};

// Mock data
const mockDataSources = [
  {
    id: 1,
    name: 'Confluence Wiki',
    type: 'confluence',
    config: { url: 'https://wiki.example.com' },
    is_active: true,
    sync_schedule: '0 2 * * *',
    last_sync_at: '2026-06-19T02:00:00Z',
    created_at: '2026-06-01T10:00:00Z',
    updated_at: '2026-06-19T02:05:00Z',
    created_by: 1,
  },
  {
    id: 2,
    name: 'JIRA Projects',
    type: 'jira',
    config: { url: 'https://jira.example.com' },
    is_active: false,
    sync_schedule: null,
    last_sync_at: null,
    created_at: '2026-06-10T14:00:00Z',
    updated_at: '2026-06-10T14:00:00Z',
    created_by: 1,
  },
  {
    id: 3,
    name: 'Onboarding Docs',
    type: 'onboarding',
    config: { storage_path: '/data/onboarding' },
    is_active: true,
    sync_schedule: '0 0 * * 0',
    last_sync_at: null,
    created_at: '2026-06-15T09:00:00Z',
    updated_at: '2026-06-15T09:00:00Z',
    created_by: 1,
  },
];

describe('DataSourceManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // TC-001: Render empty data source list
  it('should render empty state when no data sources exist', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: [], total: 0, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('No data sources found. Create one to get started.')).toBeInTheDocument();
    });

    expect(screen.getByText('Add Data Source')).toBeInTheDocument();
  });

  // TC-002: Render data source list with multiple items
  it('should render data source list with multiple items', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Confluence Wiki')).toBeInTheDocument();
    });

    expect(screen.getByText('JIRA Projects')).toBeInTheDocument();
    expect(screen.getByText('Onboarding Docs')).toBeInTheDocument();
  });

  // TC-003: Display correct status chips
  it('should display correct status chips', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  // TC-004: Format last sync timestamp correctly
  it('should format last sync timestamp correctly', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getAllByText('Never')).toHaveLength(2);
    });
  });

  // TC-005: Display sync schedule
  it('should display sync schedule or "Not scheduled"', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('0 2 * * *')).toBeInTheDocument();
    });

    expect(screen.getByText('0 0 * * 0')).toBeInTheDocument();
    expect(screen.getByText('Not scheduled')).toBeInTheDocument();
  });

  // TC-007: Open create modal
  it('should open create modal when Add Data Source button is clicked', async () => {
    const user = userEvent.setup();
    mockApi.get.mockResolvedValue({
      data: { items: [], total: 0, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Add Data Source')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Add Data Source'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // TC-036: Fetch data sources on mount
  it('should fetch data sources on component mount', async () => {
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith('/v1/admin/data-sources');
    });
  });

  // TC-041: Manual refresh
  it('should refresh data when Refresh button is clicked', async () => {
    const user = userEvent.setup();
    mockApi.get.mockResolvedValue({
      data: { items: mockDataSources, total: 3, limit: 10, offset: 0 },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    mockApi.get.mockClear();
    await user.click(screen.getByText('Refresh'));

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledWith('/v1/admin/data-sources');
    });
  });

  // TC-048: Status Chip - Inactive
  it('should show Inactive chip when is_active is false', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        items: [
          {
            ...mockDataSources[1],
            is_active: false,
            last_sync_at: null,
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Inactive')).toBeInTheDocument();
    });
  });

  // TC-049: Status Chip - Active
  it('should show Active chip when is_active is true and last_sync_at exists', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        items: [
          {
            ...mockDataSources[0],
            is_active: true,
            last_sync_at: '2026-06-19T02:00:00Z',
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  // TC-050: Status Chip - Pending
  it('should show Pending chip when is_active is true and last_sync_at is null', async () => {
    mockApi.get.mockResolvedValue({
      data: {
        items: [
          {
            ...mockDataSources[2],
            is_active: true,
            last_sync_at: null,
          },
        ],
        total: 1,
        limit: 10,
        offset: 0,
      },
    });

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText('Pending')).toBeInTheDocument();
    });
  });

  // Error handling
  it('should display error message when API fails', async () => {
    mockApi.get.mockRejectedValue(new Error('Network error'));

    renderWithProviders(<DataSourceManager />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load data sources/)).toBeInTheDocument();
    });
  });
});
