/**
 * DataSourceManager Component
 *
 * Admin UI for managing data sources (Confluence, JIRA, Onboarding, Custom).
 * Features:
 * - Data source list table with columns: name, type, status, last sync, actions
 * - Create/Edit modals with form validation
 * - Delete confirmation dialog
 * - API integration using React Query
 * - Toast notifications for success/error states
 */

import { useState } from 'react';
import {
  Box,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  Typography,
  Snackbar,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { DataSourceFormModal } from './DataSourceFormModal';
import { DeleteConfirmDialog } from './DeleteConfirmDialog';

// Types based on backend schema
interface DataSource {
  id: number;
  name: string;
  type: 'confluence' | 'jira' | 'onboarding' | 'custom';
  config: Record<string, unknown> | null;
  is_active: boolean;
  sync_schedule: string | null;
  last_sync_at: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

interface DataSourceListResponse {
  items: DataSource[];
  total: number;
  limit: number;
  offset: number;
}

interface DataSourceFormData {
  name: string;
  type: 'confluence' | 'jira' | 'onboarding' | 'custom';
  config: Record<string, unknown>;
  sync_schedule: string;
  is_active: boolean;
}

interface ToastState {
  open: boolean;
  message: string;
  severity: 'success' | 'error' | 'info' | 'warning';
}

export function DataSourceManager() {
  const queryClient = useQueryClient();
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingDataSource, setEditingDataSource] = useState<DataSource | null>(
    null
  );
  const [deletingDataSource, setDeletingDataSource] =
    useState<DataSource | null>(null);
  const [toast, setToast] = useState<ToastState>({
    open: false,
    message: '',
    severity: 'info',
  });

  // Fetch data sources
  const { data, isLoading, error, refetch } = useQuery<DataSourceListResponse>({
    queryKey: ['dataSources'],
    queryFn: async () => {
      const response = await api.get('/v1/admin/data-sources');
      return response.data;
    },
  });

  // Create data source mutation
  const createMutation = useMutation({
    mutationFn: async (formData: DataSourceFormData) => {
      const response = await api.post('/v1/admin/data-sources', formData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
      setIsCreateModalOpen(false);
      showToast('Data source created successfully', 'success');
    },
    onError: (err: any) => {
      showToast(
        err.response?.data?.detail || 'Failed to create data source',
        'error'
      );
    },
  });

  // Update data source mutation
  const updateMutation = useMutation({
    mutationFn: async ({
      id,
      formData,
    }: {
      id: number;
      formData: Partial<DataSourceFormData>;
    }) => {
      const response = await api.put(`/v1/admin/data-sources/${id}`, formData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
      setEditingDataSource(null);
      showToast('Data source updated successfully', 'success');
    },
    onError: (err: any) => {
      showToast(
        err.response?.data?.detail || 'Failed to update data source',
        'error'
      );
    },
  });

  // Delete data source mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/v1/admin/data-sources/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
      setDeletingDataSource(null);
      showToast('Data source deleted successfully', 'success');
    },
    onError: (err: any) => {
      showToast(
        err.response?.data?.detail || 'Failed to delete data source',
        'error'
      );
    },
  });

  const showToast = (message: string, severity: ToastState['severity']) => {
    setToast({ open: true, message, severity });
  };

  const handleCloseToast = () => {
    setToast({ ...toast, open: false });
  };

  const handleCreate = (
    formData: DataSourceFormData | Partial<DataSourceFormData>
  ) => {
    createMutation.mutate(formData as DataSourceFormData);
  };

  const handleEdit = (
    formData: DataSourceFormData | Partial<DataSourceFormData>
  ) => {
    if (editingDataSource) {
      updateMutation.mutate({ id: editingDataSource.id, formData });
    }
  };

  const handleDelete = () => {
    if (deletingDataSource) {
      deleteMutation.mutate(deletingDataSource.id);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const getStatusChip = (dataSource: DataSource) => {
    if (!dataSource.is_active) {
      return <Chip label="Inactive" color="default" size="small" />;
    }
    if (dataSource.last_sync_at) {
      return <Chip label="Active" color="success" size="small" />;
    }
    return <Chip label="Pending" color="warning" size="small" />;
  };

  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 3,
        }}
      >
        <Box>
          <Typography variant="h4" component="h1">
            Data Sources
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure and manage data sources
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetch()}
            disabled={isLoading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Add Data Source
          </Button>
        </Box>
      </Box>

      {/* Error State */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load data sources:{' '}
          {(error as any)?.message || 'Unknown error'}
        </Alert>
      )}

      {/* Data Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Last Sync</TableCell>
              <TableCell>Sync Schedule</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  Loading...
                </TableCell>
              </TableRow>
            )}
            {!isLoading && data?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No data sources found. Create one to get started.
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((dataSource) => (
              <TableRow key={dataSource.id}>
                <TableCell>
                  <Typography variant="body2" fontWeight="medium">
                    {dataSource.name}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={dataSource.type}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>{getStatusChip(dataSource)}</TableCell>
                <TableCell>{formatDate(dataSource.last_sync_at)}</TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                  >
                    {dataSource.sync_schedule || 'Not scheduled'}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    color="primary"
                    onClick={() => setEditingDataSource(dataSource)}
                    title="Edit"
                  >
                    <EditIcon />
                  </IconButton>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => setDeletingDataSource(dataSource)}
                    title="Delete"
                  >
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination Info */}
      {data && data.total > 0 && (
        <Box sx={{ mt: 2, textAlign: 'right' }}>
          <Typography variant="body2" color="text.secondary">
            Showing {data.items.length} of {data.total} data sources
          </Typography>
        </Box>
      )}

      {/* Create Modal */}
      <DataSourceFormModal
        open={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onSubmit={handleCreate}
        isSubmitting={createMutation.isPending}
      />

      {/* Edit Modal */}
      {editingDataSource && (
        <DataSourceFormModal
          open
          onClose={() => setEditingDataSource(null)}
          onSubmit={handleEdit}
          initialData={{
            id: editingDataSource.id,
            name: editingDataSource.name,
            type: editingDataSource.type,
            config: editingDataSource.config || {},
            sync_schedule: editingDataSource.sync_schedule || '',
            is_active: editingDataSource.is_active,
          }}
          isSubmitting={updateMutation.isPending}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deletingDataSource && (
        <DeleteConfirmDialog
          open
          onClose={() => setDeletingDataSource(null)}
          onConfirm={handleDelete}
          dataSourceName={deletingDataSource.name}
          isDeleting={deleteMutation.isPending}
        />
      )}

      {/* Toast Notifications */}
      <Snackbar
        open={toast.open}
        autoHideDuration={6000}
        onClose={handleCloseToast}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleCloseToast}
          severity={toast.severity}
          sx={{ width: '100%' }}
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
