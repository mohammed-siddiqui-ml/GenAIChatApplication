import { io, Socket } from 'socket.io-client';
import type { Message, ApiError, Source } from '../types';

interface ChatChunkData {
  chunk: string;
  chunk_index: number;
  timestamp: string;
}

interface ChatSourcesData {
  sources: Source[];
  timestamp: string;
}

interface ChatDoneData {
  message_id: number;
  session_id: string;
  metadata: {
    duration_ms: number;
    num_sources: number;
    chunk_count?: number;
  };
}

class SocketService {
  private socket: Socket | null = null;

  private readonly url: string;

  constructor() {
    this.url = import.meta.env.VITE_WS_URL || 'http://localhost:8000';
  }

  connect(sessionId: string): Socket {
    if (this.socket?.connected) {
      return this.socket;
    }

    const token = localStorage.getItem('token');

    this.socket = io(this.url, {
      auth: {
        token,
        sessionId,
      },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.setupEventHandlers();

    return this.socket;
  }

  private setupEventHandlers(): void {
    if (!this.socket) return;

    this.socket.on('connect', () => {
      console.log('Socket connected');
    });

    this.socket.on('disconnect', () => {
      console.log('Socket disconnected');
    });

    this.socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
    });
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  emit(event: string, data: unknown): void {
    if (!this.socket?.connected) {
      console.warn('Socket not connected');
      return;
    }
    this.socket.emit(event, data);
  }

  on<T>(event: string, callback: (data: T) => void): void {
    if (!this.socket) {
      console.warn('Socket not initialized');
      return;
    }
    this.socket.on(event, callback);
  }

  off(event: string, callback?: (...args: unknown[]) => void): void {
    if (!this.socket) return;
    this.socket.off(event, callback);
  }

  sendMessage(message: string, sessionId: string): void {
    // Get session token from localStorage
    const sessionToken = localStorage.getItem('token') || '';
    this.emit('chat:query', { query: message, sessionId, sessionToken });
  }

  onMessage(callback: (message: Message) => void): void {
    this.on<Message>('message', callback);
  }

  onTyping(callback: (isTyping: boolean) => void): void {
    this.on<boolean>('typing', callback);
  }

  onError(callback: (error: ApiError) => void): void {
    this.on<ApiError>('chat:error', callback);
  }

  // New handlers for RAG streaming events
  onChatChunk(callback: (data: ChatChunkData) => void): void {
    this.on<ChatChunkData>('chat:chunk', callback);
  }

  onChatSources(callback: (data: ChatSourcesData) => void): void {
    this.on<ChatSourcesData>('chat:sources', callback);
  }

  onChatDone(callback: (data: ChatDoneData) => void): void {
    this.on<ChatDoneData>('chat:done', callback);
  }

  isConnected(): boolean {
    return this.socket?.connected ?? false;
  }
}

export const socketService = new SocketService();
export default socketService;
