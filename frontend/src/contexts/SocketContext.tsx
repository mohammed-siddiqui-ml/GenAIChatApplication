import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { io, Socket } from 'socket.io-client';

interface SocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  connect: (sessionToken: string, sessionId: string) => void;
  disconnect: () => void;
}

const SocketContext = createContext<SocketContextType | undefined>(undefined);

export const useSocketContext = () => {
  const context = useContext(SocketContext);
  if (!context) {
    throw new Error('useSocketContext must be used within SocketProvider');
  }
  return context;
};

interface SocketProviderProps {
  children: ReactNode;
}

export function SocketProvider({ children }: SocketProviderProps) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

  const connect = useCallback(
    (sessionToken: string, sessionId: string) => {
      // Disconnect existing socket if any
      if (socket?.connected) {
        socket.disconnect();
      }

      // Create new socket connection
      const newSocket = io(wsUrl, {
        auth: {
          token: sessionToken,
          sessionId,
        },
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
      });

      // Connection event handlers
      newSocket.on('connect', () => {
        console.log('Socket.IO connected:', newSocket.id);
        setIsConnected(true);
      });

      newSocket.on('disconnect', (reason) => {
        console.log('Socket.IO disconnected:', reason);
        setIsConnected(false);
      });

      newSocket.on('connect_error', (error) => {
        console.error('Socket.IO connection error:', error);
        setIsConnected(false);
      });

      // Store socket instance
      setSocket(newSocket);

      // Explicitly connect the socket (auto-connects by default, but explicit for tests)
      newSocket.connect();
    },
    [socket, wsUrl]
  );

  const disconnect = useCallback(() => {
    if (socket) {
      socket.disconnect();
      setSocket(null);
      setIsConnected(false);
    }
  }, [socket]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (socket) {
        // Remove all event listeners before disconnecting
        socket.off('connect');
        socket.off('disconnect');
        socket.off('connect_error');
        socket.disconnect();
      }
    };
  }, [socket]);

  const contextValue = useMemo(
    () => ({
      socket,
      isConnected,
      connect,
      disconnect,
    }),
    [socket, isConnected, connect, disconnect]
  );

  return (
    <SocketContext.Provider value={contextValue}>
      {children}
    </SocketContext.Provider>
  );
}
