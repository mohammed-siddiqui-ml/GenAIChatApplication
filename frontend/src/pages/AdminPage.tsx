/**
 * AdminPage Component
 *
 * Example admin dashboard page that demonstrates protected route usage.
 * Only accessible to authenticated admin users.
 */

import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

export function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '2rem',
        borderBottom: '2px solid #1976d2',
        paddingBottom: '1rem'
      }}>
        <h1>Admin Dashboard</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span>Welcome, {user?.email}</span>
          <button
            onClick={handleLogout}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#d32f2f',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Logout
          </button>
        </div>
      </div>

      <div style={{
        backgroundColor: '#f5f5f5',
        padding: '1.5rem',
        borderRadius: '8px',
        marginBottom: '1.5rem'
      }}>
        <h2 style={{ marginBottom: '1rem' }}>User Information</h2>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div><strong>ID:</strong> {user?.id}</div>
          <div><strong>Email:</strong> {user?.email}</div>
          <div><strong>Username:</strong> {user?.username}</div>
          <div><strong>Role:</strong> {user?.isAdmin ? 'Admin' : 'User'}</div>
          <div><strong>Created:</strong> {user?.createdAt}</div>
        </div>
      </div>

      <div style={{
        backgroundColor: '#e3f2fd',
        padding: '1.5rem',
        borderRadius: '8px'
      }}>
        <h2 style={{ marginBottom: '1rem' }}>Admin Features</h2>
        <p style={{ marginBottom: '1rem' }}>
          This page is only accessible to authenticated admin users.
        </p>
        <ul style={{ paddingLeft: '1.5rem', lineHeight: '1.8' }}>
          <li>Configure and manage data sources</li>
          <li>Monitor system health and usage</li>
          <li>Trigger data ingestion or refresh</li>
          <li>Manage access control and permissions</li>
        </ul>
      </div>
    </div>
  );
}

export default AdminPage;
