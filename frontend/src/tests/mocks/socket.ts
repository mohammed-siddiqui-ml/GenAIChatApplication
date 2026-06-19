/**
 * WebSocket Mock for Testing
 * 
 * Provides a mock Socket.IO client for testing real-time functionality
 */

import { vi } from 'vitest';
import type { Socket } from 'socket.io-client';

export interface MockSocket extends Partial<Socket> {
  id: string;
  connected: boolean;
  on: ReturnType<typeof vi.fn>;
  off: ReturnType<typeof vi.fn>;
  emit: ReturnType<typeof vi.fn>;
  connect: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
}

export function createMockSocket(overrides?: Partial<MockSocket>): MockSocket {
  const eventHandlers = new Map<string, Array<(...args: any[]) => void>>();

  const mockSocket: MockSocket = {
    id: 'mock-socket-id',
    connected: true,
    
    on: vi.fn((event: string, handler: (...args: any[]) => void) => {
      if (!eventHandlers.has(event)) {
        eventHandlers.set(event, []);
      }
      eventHandlers.get(event)!.push(handler);
      return mockSocket as Socket;
    }),
    
    off: vi.fn((event: string, handler?: (...args: any[]) => void) => {
      if (handler) {
        const handlers = eventHandlers.get(event);
        if (handlers) {
          const index = handlers.indexOf(handler);
          if (index > -1) {
            handlers.splice(index, 1);
          }
        }
      } else {
        eventHandlers.delete(event);
      }
      return mockSocket as Socket;
    }),
    
    emit: vi.fn((event: string, ...args: any[]) => {
      // Simulate server responses
      setTimeout(() => {
        if (event === 'chat:query') {
          const handlers = eventHandlers.get('chat:chunk');
          if (handlers) {
            handlers.forEach(h => h({ chunk: 'Test ', chunk_index: 0, timestamp: new Date().toISOString() }));
            handlers.forEach(h => h({ chunk: 'response', chunk_index: 1, timestamp: new Date().toISOString() }));
          }
          
          const doneHandlers = eventHandlers.get('chat:done');
          if (doneHandlers) {
            doneHandlers.forEach(h => h({ metadata: {} }));
          }
        }
      }, 10);
      
      return mockSocket as Socket;
    }),
    
    connect: vi.fn(() => {
      mockSocket.connected = true;
      const handlers = eventHandlers.get('connect');
      if (handlers) {
        handlers.forEach(h => h());
      }
      return mockSocket as Socket;
    }),
    
    disconnect: vi.fn(() => {
      mockSocket.connected = false;
      const handlers = eventHandlers.get('disconnect');
      if (handlers) {
        handlers.forEach(h => h());
      }
      return mockSocket as Socket;
    }),
    
    ...overrides,
  };

  // Helper function to trigger events (for testing)
  (mockSocket as any).__triggerEvent = (event: string, ...args: any[]) => {
    const handlers = eventHandlers.get(event);
    if (handlers) {
      handlers.forEach(h => h(...args));
    }
  };

  return mockSocket;
}
