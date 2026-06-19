/**
 * MSW (Mock Service Worker) Request Handlers
 * 
 * Defines mock API responses for testing
 */

import { http, HttpResponse } from 'msw';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE_URL}/v1/auth/login`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string };
    
    if (body.email === 'admin@test.com' && body.password === 'password') {
      return HttpResponse.json({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        token_type: 'Bearer',
        user: {
          id: 1,
          email: 'admin@test.com',
          role: 'admin',
          is_active: true,
        },
      });
    }
    
    return HttpResponse.json(
      { detail: 'Invalid credentials' },
      { status: 401 }
    );
  }),

  http.post(`${API_BASE_URL}/v1/auth/logout`, () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
  }),

  http.get(`${API_BASE_URL}/v1/auth/me`, () => {
    return HttpResponse.json({
      id: 1,
      email: 'admin@test.com',
      role: 'admin',
      is_active: true,
    });
  }),

  http.post(`${API_BASE_URL}/v1/auth/refresh`, () => {
    return HttpResponse.json({
      access_token: 'new-mock-access-token',
    });
  }),

  // Chat session endpoints
  http.post(`${API_BASE_URL}/v1/chat/sessions`, () => {
    return HttpResponse.json({
      session_id: 'test-session-123',
      session_token: 'test-token-456',
      created_at: new Date().toISOString(),
    });
  }),

  http.post(`${API_BASE_URL}/v1/chat/query`, async ({ request }) => {
    const body = await request.json() as { query: string; stream?: boolean };
    
    if (body.stream) {
      // For SSE streaming, return a readable stream
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode('data: {"type":"chunk","content":"Hello "}\n\n'));
          controller.enqueue(new TextEncoder().encode('data: {"type":"chunk","content":"World"}\n\n'));
          controller.enqueue(new TextEncoder().encode('data: {"type":"done"}\n\n'));
          controller.close();
        },
      });
      
      return new HttpResponse(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
        },
      });
    }
    
    return HttpResponse.json({
      content: 'This is a test response',
      sources: [],
      metadata: {},
      session_id: 'test-session-123',
      message_id: 1,
    });
  }),

  // Admin endpoints
  http.get(`${API_BASE_URL}/v1/admin/data-sources`, () => {
    return HttpResponse.json({
      items: [
        {
          id: 1,
          name: 'Test Confluence',
          type: 'confluence',
          config: { url: 'https://wiki.test.com' },
          is_active: true,
          sync_schedule: '0 2 * * *',
          last_sync_at: '2024-01-15T10:00:00Z',
          created_by: 1,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-15T10:00:00Z',
        },
        {
          id: 2,
          name: 'Test Jira',
          type: 'jira',
          config: { url: 'https://jira.test.com' },
          is_active: true,
          sync_schedule: '0 3 * * *',
          last_sync_at: '2024-01-15T11:00:00Z',
          created_by: 1,
          created_at: '2024-01-02T00:00:00Z',
          updated_at: '2024-01-15T11:00:00Z',
        },
      ],
      total: 2,
      limit: 100,
      offset: 0,
    });
  }),

  http.post(`${API_BASE_URL}/v1/admin/data-sources`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: 2,
      ...body,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),

  http.put(`${API_BASE_URL}/v1/admin/data-sources/:id`, async ({ params, request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: Number(params.id),
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  http.delete(`${API_BASE_URL}/v1/admin/data-sources/:id`, () => {
    return HttpResponse.json({ message: 'Data source deleted' });
  }),

  http.get(`${API_BASE_URL}/v1/admin/metrics`, () => {
    return HttpResponse.json({
      total_documents: 500,
      active_documents: 450,
      sessions: {
        total_all_time: 1000,
        active_sessions: 25,
      },
      queries: {
        total_today: 85,
        total_this_week: 540,
        total_this_month: 2100,
        total_all_time: 12500,
      },
      average_response_time_ms: 1500,
      database: {
        database_size_bytes: 1048576000,
        database_size_mb: 1000,
        total_embeddings: 5000,
      },
      ingestion: {
        total_jobs: 100,
        successful_jobs: 95,
        failed_jobs: 5,
        success_rate: 0.95,
        last_successful_run: '2024-01-15T10:00:00Z',
        last_failed_run: '2024-01-10T08:30:00Z',
      },
      timestamp: new Date().toISOString(),
    });
  }),

  http.get(`${API_BASE_URL}/v1/admin/audit-logs`, () => {
    return HttpResponse.json({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
  }),
];
