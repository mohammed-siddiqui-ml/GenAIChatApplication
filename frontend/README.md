# GenAI Knowledge Retrieval System - Frontend

React + TypeScript frontend for the GenAI Chat-Based Knowledge Retrieval System.

## Tech Stack

- **React 18.2** - UI library
- **TypeScript 5.3** - Type safety
- **Vite 5.0** - Build tool and dev server
- **Material-UI 5.15** - Component library
- **React Query** - Server state management
- **Socket.IO Client** - Real-time WebSocket communication
- **React Router** - Client-side routing
- **Zustand** - Client state management
- **ESLint + Prettier** - Code quality and formatting

## Getting Started

### Prerequisites

- Node.js 18+ and npm

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env
```

### Development

```bash
# Start development server
npm run dev

# Run ESLint
npm run lint

# Fix ESLint issues
npm run lint:fix

# Format code with Prettier
npm run format

# Type check
npm run type-check
```

### Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
src/
├── components/     # Reusable UI components
├── contexts/       # React contexts (Theme, Auth)
├── hooks/          # Custom React hooks
├── pages/          # Page components
├── services/       # API and Socket.IO services
├── types/          # TypeScript type definitions
├── utils/          # Utility functions
├── App.tsx         # Root component
└── main.tsx        # Application entry point
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint issues
- `npm run format` - Format code with Prettier
- `npm run type-check` - Run TypeScript type checking

## Environment Variables

See `.env.example` for required environment variables.

## Docker

```bash
# Build image
docker build -t chat-frontend .

# Run container
docker run -p 3000:3000 chat-frontend
```
