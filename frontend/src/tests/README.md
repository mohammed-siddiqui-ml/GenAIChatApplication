# Frontend Test Suite

This directory contains comprehensive tests for the React frontend application using Vitest and React Testing Library.

## Structure

```
src/tests/
├── README.md                    # This file
├── setup.ts                     # Additional test setup
├── mocks/                       # Mock implementations
│   ├── handlers.ts              # MSW API route handlers
│   ├── server.ts                # MSW server setup
│   └── socket.ts                # WebSocket mock
├── components/                  # Component tests
│   ├── ChatWindow.test.tsx
│   ├── MessageList.test.tsx
│   ├── MessageInput.test.tsx
│   └── DataSourceManager.test.tsx
├── hooks/                       # Hook tests
│   ├── useChat.test.ts
│   ├── useWebSocket.test.ts
│   └── useAuth.test.ts (in contexts/__tests__)
└── services/                    # Service tests
    ├── chatService.test.ts
    ├── authService.test.ts
    └── adminService.test.ts
```

## Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage
```

## Coverage Requirements

The test suite is configured to require minimum 70% coverage across:
- Lines
- Functions
- Branches
- Statements

## Test Technologies

### Vitest
Fast unit test framework compatible with Jest API

### React Testing Library
Testing library focused on testing components from user's perspective

### MSW (Mock Service Worker)
API mocking library for testing HTTP requests

### Testing Best Practices

1. **Test Behavior, Not Implementation**
   - Test what the user sees and does
   - Avoid testing internal state or implementation details

2. **Use Semantic Queries**
   - Prefer `getByRole`, `getByLabelText`, `getByText`
   - Avoid `getByTestId` unless necessary

3. **Async Testing**
   - Use `waitFor` for async operations
   - Use `userEvent` for simulating user interactions

4. **Mock External Dependencies**
   - Mock API calls with MSW
   - Mock WebSocket connections
   - Mock external libraries when needed

## Example Test

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';

describe('MyComponent', () => {
  it('should handle user interaction', async () => {
    const user = userEvent.setup();
    render(<MyComponent />);
    
    const button = screen.getByRole('button', { name: /click me/i });
    await user.click(button);
    
    expect(screen.getByText(/success/i)).toBeInTheDocument();
  });
});
```

## Mocks

### MSW Handlers
Located in `mocks/handlers.ts`, these define mock API responses for:
- Authentication endpoints
- Chat session endpoints
- Admin endpoints (data sources, metrics, audit logs)

### WebSocket Mock
Located in `mocks/socket.ts`, provides a mock Socket.IO client for testing real-time functionality.

## CI Integration

Tests are automatically run in the CI pipeline with coverage reporting.
Minimum coverage thresholds must be met for builds to pass.
