/**
 * ProtectedRoute Component
 *
 * A wrapper component that protects routes requiring authentication.
 * Redirects unauthenticated users to the login page.
 * Optionally restricts access to admin users only.
 */

import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: ReactNode;
  requireAdmin?: boolean;
}

/**
 * ProtectedRoute component
 *
 * @param children - Child components to render if authorized
 * @param requireAdmin - If true, only admin users can access (default: false)
 * @returns Protected content or redirect to login
 */
export function ProtectedRoute({
  children,
  requireAdmin = false,
}: ProtectedRouteProps) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();
  const location = useLocation();

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          fontSize: '1.2rem',
          color: '#666',
        }}
      >
        Loading...
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    // Save the attempted location for redirecting after login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check admin requirement
  if (requireAdmin && !isAdmin) {
    // User is authenticated but not an admin
    // Redirect to home page or show unauthorized message
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          fontSize: '1.2rem',
          color: '#d32f2f',
        }}
      >
        <h1>Unauthorized</h1>
        <p>You do not have permission to access this page.</p>
        <p>Admin access required.</p>
      </div>
    );
  }

  // User is authenticated and authorized
  return <>{children}</>;
}

export default ProtectedRoute;
