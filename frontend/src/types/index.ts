// Common types for the application

export interface User {
  id: string;
  username: string;
  email: string;
  isAdmin: boolean;
  createdAt: string;
}

export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: string;
  sources?: Source[];
  sessionId: string;
}

export interface Source {
  id: string;
  title: string;
  type: 'confluence' | 'issue' | 'onboarding' | 'documentation';
  url: string;
  excerpt: string;
  relevanceScore?: number;
}

export interface ChatSession {
  id: string;
  userId?: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface DataSource {
  id: string;
  name: string;
  type: 'confluence' | 'issue_tracker' | 'onboarding';
  status: 'active' | 'inactive' | 'error';
  lastSyncAt?: string;
  configuration: Record<string, unknown>;
}

export interface ApiError {
  message: string;
  code?: string;
  details?: Record<string, unknown>;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// Socket.IO event types
export interface SocketEvents {
  connect: () => void;
  disconnect: () => void;
  message: (message: Message) => void;
  typing: (isTyping: boolean) => void;
  error: (error: ApiError) => void;
}

export type Theme = 'light' | 'dark' | 'system';

export interface AppConfig {
  apiUrl: string;
  wsUrl: string;
  theme: Theme;
}
