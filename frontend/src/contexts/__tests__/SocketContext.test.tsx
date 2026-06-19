import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { io } from 'socket.io-client';
import { SocketProvider, useSocketContext } from '../SocketContext';

// Mock socket.io-client
vi.mock('socket.io-client');

describe('SocketContext', () => {
  let mockSocket: any;

  beforeEach(() => {
    // Create mock socket instance
    mockSocket = {
      on: vi.fn(),
      emit: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      off: vi.fn(),
      connected: false,
      auth: {},
      io: {
        opts: {},
      },
    };

    // Mock io() to return our mock socket
    (io as any).mockReturnValue(mockSocket);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // TC-001: SocketContext Provides Socket Instance
  it('TC-001: provides socket instance after connection', async () => {
    function TestComponent() {
      const { socket, isConnected, connect } = useSocketContext();

      return (
        <div>
          <div data-testid="socket-exists">{socket ? 'exists' : 'null'}</div>
          <div data-testid="is-connected">{isConnected ? 'true' : 'false'}</div>
          <button onClick={() => connect('token', 'session-id')}>
            Connect
          </button>
        </div>
      );
    }

    render(
      <SocketProvider>
        <TestComponent />
      </SocketProvider>
    );

    // Initially no socket
    expect(screen.getByTestId('socket-exists').textContent).toBe('null');
    expect(screen.getByTestId('is-connected').textContent).toBe('false');

    // Connect
    screen.getByText('Connect').click();

    await waitFor(() => {
      expect(screen.getByTestId('socket-exists').textContent).toBe('exists');
      expect(mockSocket.on).toHaveBeenCalledWith(
        'connect',
        expect.any(Function)
      );
      expect(mockSocket.on).toHaveBeenCalledWith(
        'disconnect',
        expect.any(Function)
      );
    });
  });

  // TC-002: SocketContext Updates Connection State
  it('TC-002: updates connection state on connect/disconnect events', async () => {
    let connectHandler: Function;
    let disconnectHandler: Function;

    mockSocket.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'connect') connectHandler = handler;
      if (event === 'disconnect') disconnectHandler = handler;
      return mockSocket;
    });

    function TestComponent() {
      const { isConnected, connect } = useSocketContext();
      return (
        <div>
          <div data-testid="connection-state">
            {isConnected ? 'connected' : 'disconnected'}
          </div>
          <button onClick={() => connect('token', 'session-id')}>
            Connect
          </button>
        </div>
      );
    }

    render(
      <SocketProvider>
        <TestComponent />
      </SocketProvider>
    );

    // Initially disconnected
    expect(screen.getByTestId('connection-state').textContent).toBe(
      'disconnected'
    );

    // Trigger connection
    screen.getByText('Connect').click();

    // Simulate connect event
    await waitFor(() => {
      expect(mockSocket.on).toHaveBeenCalled();
    });

    mockSocket.connected = true;
    connectHandler!();

    await waitFor(() => {
      expect(screen.getByTestId('connection-state').textContent).toBe(
        'connected'
      );
    });

    // Simulate disconnect event
    mockSocket.connected = false;
    disconnectHandler!();

    await waitFor(() => {
      expect(screen.getByTestId('connection-state').textContent).toBe(
        'disconnected'
      );
    });
  });

  // TC-014: Connection Cleanup on Unmount
  it('TC-014: cleans up socket connection on unmount', async () => {
    function TestComponent() {
      const { socket, connect } = useSocketContext();
      return (
        <div>
          <div data-testid="socket-status">{socket ? 'mounted' : 'null'}</div>
          <button onClick={() => connect('token', 'session-id')}>
            Connect
          </button>
        </div>
      );
    }

    const { unmount } = render(
      <SocketProvider>
        <TestComponent />
      </SocketProvider>
    );

    // Connect first
    screen.getByText('Connect').click();

    await waitFor(() => {
      expect(mockSocket.on).toHaveBeenCalled();
    });

    unmount();

    expect(mockSocket.disconnect).toHaveBeenCalled();
    expect(mockSocket.off).toHaveBeenCalledWith('connect');
    expect(mockSocket.off).toHaveBeenCalledWith('disconnect');
  });

  // Test provider without children
  it('provides context value without errors', () => {
    const { container } = render(
      <SocketProvider>
        <div>test</div>
      </SocketProvider>
    );
    expect(container).toBeTruthy();
  });

  // Test error when using context outside provider
  it('throws error when useSocketContext used outside provider', () => {
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});

    function TestComponent() {
      useSocketContext();
      return <div>should not render</div>;
    }

    expect(() => render(<TestComponent />)).toThrow(
      'useSocketContext must be used within SocketProvider'
    );

    consoleError.mockRestore();
  });
});
