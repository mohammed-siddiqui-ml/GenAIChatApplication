import { BrowserRouter as Router } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-gray-50">
          <header className="bg-white shadow">
            <div className="max-w-7xl mx-auto py-6 px-4">
              <h1 className="text-3xl font-bold text-gray-900">
                GenAI Knowledge Retrieval System
              </h1>
            </div>
          </header>
          <main className="max-w-7xl mx-auto py-6 px-4">
            <p className="text-gray-600">Chat interface coming soon...</p>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  )
}

export default App
