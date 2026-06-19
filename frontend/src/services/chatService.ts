/**
 * Chat Service
 *
 * Provides functions for chat session management and query submission.
 * Supports both REST API with SSE streaming and WebSocket communication.
 */

import api from './api';
import socketService from './socket';

/**
 * Session data stored in localStorage
 */
interface SessionData {
  sessionId: string;
  sessionToken: string;
  createdAt: string;
}

/**
 * Response from session creation endpoint
 */
interface SessionResponse {
  session_id: string;
  session_token: string;
  created_at: string;
}

/**
 * Query request parameters
 */
export interface QueryRequest {
  query: string;
  stream?: boolean;
  top_k?: number;
  temperature?: number;
}

/**
 * Source citation in response
 */
export interface SourceCitation {
  id: number;
  title: string;
  url?: string;
  type: string;
  similarity: number;
  chunk_index: number;
  metadata?: Record<string, unknown>;
}

/**
 * Query response (non-streaming)
 */
export interface QueryResponse {
  content: string;
  sources: SourceCitation[];
  metadata: Record<string, unknown>;
  session_id: string;
  message_id: number;
}

/**
 * Streaming event types
 */
export type StreamEventType = 'chunk' | 'sources' | 'done' | 'error';

/**
 * Streaming event data
 */
export interface StreamEvent {
  type: StreamEventType;
  content?: string;
  sources?: SourceCitation[];
  metadata?: Record<string, unknown>;
  error?: string;
}

/**
 * Callback for streaming events
 */
export type StreamCallback = (event: StreamEvent) => void;

const SESSION_STORAGE_KEY = 'chat_session';

/**
 * Get current session from localStorage
 *
 * @returns Session data or null if no session exists
 */
export function getSession(): SessionData | null {
  const sessionStr = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionStr) return null;

  try {
    return JSON.parse(sessionStr) as SessionData;
  } catch (error) {
    console.error('Failed to parse session data:', error);
    return null;
  }
}

/**
 * Store session in localStorage
 *
 * @param sessionData - Session data to store
 */
function setSession(sessionData: SessionData): void {
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessionData));
}

/**
 * Clear session from localStorage
 */
export function clearSession(): void {
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

/**
 * Create a new chat session
 *
 * Calls POST /api/v1/chat/sessions to create a new session.
 * Stores the session token in localStorage for subsequent requests.
 *
 * @returns Session data
 * @throws Error if session creation fails
 */
export async function createSession(): Promise<SessionData> {
  try {
    // Call backend to create session
    const response = await api.post<SessionResponse>('/v1/chat/sessions', {
      user_agent: navigator.userAgent,
      ip_address: null, // Backend will extract from request
    });

    const sessionData: SessionData = {
      sessionId: response.data.session_id,
      sessionToken: response.data.session_token,
      createdAt: response.data.created_at,
    };

    // Store in localStorage
    setSession(sessionData);

    console.log('Chat session created:', sessionData.sessionId);
    return sessionData;
  } catch (error) {
    console.error('Failed to create chat session:', error);
    throw new Error('Failed to create chat session');
  }
}

/**
 * Get or create session
 *
 * Returns existing session from localStorage, or creates a new one if none exists.
 *
 * @returns Session data
 */
export async function getOrCreateSession(): Promise<SessionData> {
  const existingSession = getSession();
  if (existingSession) {
    return existingSession;
  }
  return createSession();
}

/**
 * Send query using REST API with SSE streaming
 *
 * Uses Server-Sent Events for streaming responses.
 * This is the fallback method when WebSocket is not available.
 *
 * @param query - User query text
 * @param onStream - Callback for streaming events
 * @param options - Optional query parameters
 * @returns Promise that resolves when streaming is complete
 * @throws Error if query submission fails
 */
export async function sendQuerySSE(
  query: string,
  onStream: StreamCallback,
  options?: Partial<QueryRequest>
): Promise<void> {
  const session = await getOrCreateSession();

  try {
    const queryParams: QueryRequest = {
      query,
      stream: true,
      top_k: options?.top_k || 10,
      temperature: options?.temperature || 0.7,
    };

    // Use fetch for SSE streaming
    const response = await fetch(
      `${import.meta.env.VITE_API_URL || '/api'}/v1/chat/query`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': session.sessionToken,
        },
        body: JSON.stringify(queryParams),
      }
    );

    if (!response.ok) {
      throw new Error(`Query failed: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    // Process SSE stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE events in buffer
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const eventData = line.substring(6);
          try {
            const event = JSON.parse(eventData) as StreamEvent;
            onStream(event);
          } catch (error) {
            console.error('Failed to parse SSE event:', error);
          }
        }
      }
    }
  } catch (error) {
    console.error('SSE query error:', error);
    onStream({
      type: 'error',
      error: error instanceof Error ? error.message : 'Query failed',
    });
    throw error;
  }
}

/**
 * Send query using WebSocket
 *
 * Uses Socket.IO for bidirectional real-time communication.
 * This is the primary method for query submission.
 *
 * @param query - User query text
 * @param onStream - Callback for streaming events
 * @param options - Optional query parameters
 * @returns Promise that resolves when streaming is complete
 * @throws Error if query submission fails
 */
export async function sendQueryWebSocket(
  query: string,
  onStream: StreamCallback,
  options?: Partial<QueryRequest>
): Promise<void> {
  const session = await getOrCreateSession();

  return new Promise((resolve, reject) => {
    // Connect to WebSocket
    const socket = socketService.connect(session.sessionId);

    // Set up event handlers
    const cleanup = () => {
      socket.off('chat:chunk', onChunk);
      socket.off('chat:sources', onSources);
      socket.off('chat:done', onDone);
      socket.off('chat:error', onError);
    };

    const onChunk = (data: { content: string }) => {
      onStream({ type: 'chunk', content: data.content });
    };

    const onSources = (data: { sources: SourceCitation[] }) => {
      onStream({ type: 'sources', sources: data.sources });
    };

    const onDone = (data: { metadata: Record<string, unknown> }) => {
      onStream({ type: 'done', metadata: data.metadata });
      cleanup();
      resolve();
    };

    const onError = (data: { error: string }) => {
      onStream({ type: 'error', error: data.error });
      cleanup();
      reject(new Error(data.error));
    };

    // Register event listeners
    socket.on('chat:chunk', onChunk);
    socket.on('chat:sources', onSources);
    socket.on('chat:done', onDone);
    socket.on('chat:error', onError);

    // Send query
    socket.emit('chat:query', {
      query,
      top_k: options?.top_k || 10,
      temperature: options?.temperature || 0.7,
    });
  });
}

/**
 * Send query with automatic fallback
 *
 * Tries WebSocket first, falls back to SSE if WebSocket is unavailable.
 *
 * @param query - User query text
 * @param onStream - Callback for streaming events
 * @param options - Optional query parameters
 * @returns Promise that resolves when streaming is complete
 */
export async function sendQuery(
  query: string,
  onStream: StreamCallback,
  options?: Partial<QueryRequest>
): Promise<void> {
  // Try WebSocket first
  try {
    await sendQueryWebSocket(query, onStream, options);
  } catch (error) {
    console.warn('WebSocket failed, falling back to SSE:', error);
    // Fallback to SSE
    await sendQuerySSE(query, onStream, options);
  }
}

/**
 * Send query without streaming (returns complete response)
 *
 * @param query - User query text
 * @param options - Optional query parameters
 * @returns Complete query response
 * @throws Error if query submission fails
 */
export async function sendQueryNonStreaming(
  query: string,
  options?: Partial<QueryRequest>
): Promise<QueryResponse> {
  const session = await getOrCreateSession();

  try {
    const queryParams: QueryRequest = {
      query,
      stream: false,
      top_k: options?.top_k || 10,
      temperature: options?.temperature || 0.7,
    };

    const response = await api.post<QueryResponse>(
      '/v1/chat/query',
      queryParams,
      {
        headers: {
          'X-Session-Token': session.sessionToken,
        },
      }
    );

    return response.data;
  } catch (error) {
    console.error('Non-streaming query error:', error);
    throw error;
  }
}

export default {
  createSession,
  getOrCreateSession,
  getSession,
  clearSession,
  sendQuery,
  sendQuerySSE,
  sendQueryWebSocket,
  sendQueryNonStreaming,
};
