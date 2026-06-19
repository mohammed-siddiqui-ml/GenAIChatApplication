import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, AuthProvider } from '@contexts/index';
import { Layout, ProtectedRoute } from '@components/index';
import { HomePage, ChatPage, LoginPage, AdminPage } from '@pages/index';
import { queryClient } from '@utils/index';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <Router>
            <Layout>
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/chat" element={<ChatPage />} />
                <Route path="/login" element={<LoginPage />} />
                <Route
                  path="/admin/*"
                  element={
                    <ProtectedRoute requireAdmin>
                      <AdminPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="*" element={<HomePage />} />
              </Routes>
            </Layout>
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
