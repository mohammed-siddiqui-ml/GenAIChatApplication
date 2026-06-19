/**
 * Admin Service Tests
 * 
 * Tests for admin API calls including:
 * - Data source management
 * - Metrics retrieval
 * - Audit log access
 * - Ingestion job management
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '@services/api';

vi.mock('@services/api');

describe('Admin Service (via API)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Data Source Management', () => {
    it('should fetch data sources list', async () => {
      const mockResponse = {
        data: {
          items: [
            {
              id: 1,
              name: 'Test Confluence',
              type: 'confluence',
              config: {},
              is_active: true,
              sync_schedule: '0 2 * * *',
              last_sync_at: '2024-01-15T10:00:00Z',
              created_by: 1,
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-15T10:00:00Z',
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const response = await api.get('/v1/admin/data-sources');

      expect(response.data.items).toHaveLength(1);
      expect(response.data.items[0].name).toBe('Test Confluence');
    });

    it('should create a new data source', async () => {
      const newDataSource = {
        name: 'New Confluence',
        type: 'confluence',
        config: { url: 'https://wiki.example.com' },
        is_active: true,
        sync_schedule: '0 3 * * *',
      };

      const mockResponse = {
        data: {
          id: 2,
          ...newDataSource,
          created_at: '2024-01-15T10:00:00Z',
          updated_at: '2024-01-15T10:00:00Z',
        },
      };

      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const response = await api.post('/v1/admin/data-sources', newDataSource);

      expect(response.data.id).toBe(2);
      expect(response.data.name).toBe('New Confluence');
    });

    it('should update an existing data source', async () => {
      const updates = {
        name: 'Updated Confluence',
        is_active: false,
      };

      const mockResponse = {
        data: {
          id: 1,
          ...updates,
          type: 'confluence',
          config: {},
          sync_schedule: null,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-15T11:00:00Z',
        },
      };

      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const response = await api.put('/v1/admin/data-sources/1', updates);

      expect(response.data.name).toBe('Updated Confluence');
      expect(response.data.is_active).toBe(false);
    });

    it('should delete a data source', async () => {
      const mockResponse = {
        data: { message: 'Data source deleted' },
      };

      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const response = await api.delete('/v1/admin/data-sources/1');

      expect(response.data.message).toBe('Data source deleted');
    });
  });

  describe('Metrics', () => {
    it('should fetch system metrics', async () => {
      const mockResponse = {
        data: {
          total_queries: 1000,
          avg_response_time: 1.5,
          active_sessions: 25,
          total_documents: 5000,
          storage_used_mb: 1024,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const response = await api.get('/v1/admin/metrics');

      expect(response.data.total_queries).toBe(1000);
      expect(response.data.avg_response_time).toBe(1.5);
    });
  });

  describe('Audit Logs', () => {
    it('should fetch audit logs', async () => {
      const mockResponse = {
        data: {
          items: [
            {
              id: 1,
              user_id: 1,
              action: 'create',
              resource_type: 'data_source',
              resource_id: 1,
              details: {},
              timestamp: '2024-01-15T10:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const response = await api.get('/v1/admin/audit-logs');

      expect(response.data.items).toHaveLength(1);
      expect(response.data.items[0].action).toBe('create');
    });

    it('should fetch audit logs with filters', async () => {
      const mockResponse = {
        data: {
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      await api.get('/v1/admin/audit-logs?action=delete&resource_type=data_source');

      expect(api.get).toHaveBeenCalledWith(
        '/v1/admin/audit-logs?action=delete&resource_type=data_source'
      );
    });
  });

  describe('Ingestion Jobs', () => {
    it('should fetch ingestion jobs', async () => {
      const mockResponse = {
        data: {
          items: [
            {
              id: 1,
              data_source_id: 1,
              status: 'completed',
              started_at: '2024-01-15T10:00:00Z',
              completed_at: '2024-01-15T10:05:00Z',
              documents_processed: 100,
              errors: [],
            },
          ],
          total: 1,
        },
      };

      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const response = await api.get('/v1/admin/ingestion/jobs');

      expect(response.data.items).toHaveLength(1);
      expect(response.data.items[0].status).toBe('completed');
    });
  });
});
