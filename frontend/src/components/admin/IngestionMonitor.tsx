/**
 * IngestionMonitor Component
 * 
 * Admin dashboard for monitoring and managing data ingestion jobs.
 * Features:
 * - Job list table with status, progress, and details
 * - Manual ingestion trigger with data source selection
 * - Real-time status updates via polling (5-second intervals)
 * - Color-coded status badges
 * - Progress bars for running jobs
 * - Error message display for failed jobs
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
  Chip,
  Typography,
  LinearProgress,
  Alert,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as PlayArrowIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';

// Types based on backend schema
interface IngestionJob {
  id: number;
  data_source_id: number;
  data_source_name: string | null;
  data_source_type: string | null;
  status: 'pending' | 'running' | 'success' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  documents_processed: number;
  documents_failed: number;
  error_message: string | null;
  metadata: Record<string, unknown> | null;
}

interface IngestionJobListResponse {
  items: IngestionJob[];
  total: number;
  limit: number;
  offset: number;
}

interface DataSource {
  id: number;
  name: string;
  type: 'confluence' | 'jira' | 'onboarding' | 'custom';
  is_active: boolean;
}

interface DataSourceListResponse {
  items: DataSource[];
  total: number;
  limit: number;
  offset: number;
}

interface ToastState {
  open: boolean;
  message: string;
  severity: 'success' | 'error' | 'info' | 'warning';
}

export function IngestionMonitor() {
  const queryClient = useQueryClient();
  const [isTriggerDialogOpen, setIsTriggerDialogOpen] = useState(false);
  const [selectedDataSourceId, setSelectedDataSourceId] = useState<number | ''>('');
  const [toast, setToast] = useState<ToastState>({
    open: false,
    message: '',
    severity: 'info',
  });

  // Fetch ingestion jobs with auto-refresh every 5 seconds
  const { data: jobsData, isLoading: jobsLoading, error: jobsError } = useQuery<IngestionJobListResponse>({
    queryKey: ['ingestionJobs'],
    queryFn: async () => {
      const response = await api.get('/v1/admin/ingestion/jobs');
      return response.data;
    },
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  // Fetch active data sources for trigger dialog
  const { data: dataSourcesData } = useQuery<DataSourceListResponse>({
    queryKey: ['dataSources', { is_active: true }],
    queryFn: async () => {
      const response = await api.get('/v1/admin/data-sources', {
        params: { is_active: true },
      });
      return response.data;
    },
    enabled: isTriggerDialogOpen,
  });

  // Trigger ingestion mutation
  const triggerMutation = useMutation({
    mutationFn: async (dataSourceId: number) => {
      const response = await api.post('/v1/admin/ingestion/trigger', {
        data_source_id: dataSourceId,
        sync_type: 'incremental',
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingestionJobs'] });
      setIsTriggerDialogOpen(false);
      setSelectedDataSourceId('');
      showToast('Ingestion job triggered successfully', 'success');
    },
    onError: (err: any) => {
      showToast(err.response?.data?.detail || 'Failed to trigger ingestion', 'error');
    },
  });

  const showToast = (message: string, severity: ToastState['severity']) => {
    setToast({ open: true, message, severity });
  };

  const handleCloseToast = () => {
    setToast({ ...toast, open: false });
  };

  const handleTriggerClick = () => {
    setIsTriggerDialogOpen(true);
  };

  const handleTriggerConfirm = () => {
    if (selectedDataSourceId) {
      triggerMutation.mutate(selectedDataSourceId as number);
    }
  };

  const handleTriggerCancel = () => {
    setIsTriggerDialogOpen(false);
    setSelectedDataSourceId('');
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['ingestionJobs'] });
  };

  // Status color mapping
  const getStatusColor = (status: string): 'default' | 'info' | 'success' | 'error' => {
    switch (status) {
      case 'pending':
        return 'default';
      case 'running':
        return 'info';
      case 'success':
        return 'success';
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  // Calculate job duration
  const calculateDuration = (startedAt: string | null, completedAt: string | null): string => {
    if (!startedAt) return '-';

    const start = new Date(startedAt).getTime();
    const end = completedAt ? new Date(completedAt).getTime() : Date.now();
    const durationMs = end - start;

    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  // Calculate progress percentage for running jobs
  const calculateProgress = (job: IngestionJob): number => {
    if (job.status !== 'running') return 0;

    const total = job.documents_processed + job.documents_failed;
    // For running jobs without progress data, show indeterminate progress
    if (total === 0) return 0;

    // This is a simplified calculation - in real scenarios, you'd need total expected documents
    return Math.min((total / 100) * 100, 99); // Cap at 99% while running
  };

  // Format timestamp
  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp) return '-';
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Ingestion Monitoring
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and manage data ingestion jobs
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Tooltip title="Refresh jobs">
            <IconButton onClick={handleRefresh} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={handleTriggerClick}
          >
            Trigger Ingestion
          </Button>
        </Box>
      </Box>

      {jobsError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load ingestion jobs. Please try again.
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Job ID</TableCell>
              <TableCell>Data Source</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Progress</TableCell>
              <TableCell>Start Time</TableCell>
              <TableCell>Duration</TableCell>
              <TableCell>Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {jobsLoading ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <LinearProgress />
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Loading jobs...
                  </Typography>
                </TableCell>
              </TableRow>
            ) : jobsData?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography color="text.secondary">
                    No ingestion jobs found. Trigger an ingestion to get started.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              jobsData?.items.map((job) => (
                <TableRow key={job.id}>
                  <TableCell>{job.id}</TableCell>
                  <TableCell>
                    <Box>
                      <Typography variant="body2">{job.data_source_name || 'Unknown'}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {job.data_source_type || '-'}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={job.status.toUpperCase()}
                      color={getStatusColor(job.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell sx={{ minWidth: 200 }}>
                    {job.status === 'running' ? (
                      <Box sx={{ width: '100%' }}>
                        <LinearProgress
                          variant={job.documents_processed > 0 ? 'determinate' : 'indeterminate'}
                          value={calculateProgress(job)}
                        />
                        <Typography variant="caption" color="text.secondary">
                          Processed: {job.documents_processed} | Failed: {job.documents_failed}
                        </Typography>
                      </Box>
                    ) : (
                      <Typography variant="body2">
                        {job.documents_processed} processed / {job.documents_failed} failed
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{formatTimestamp(job.started_at)}</Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {calculateDuration(job.started_at, job.completed_at)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {job.error_message && (
                      <Alert severity="error" sx={{ maxWidth: 300 }}>
                        {job.error_message}
                      </Alert>
                    )}
                    {job.status === 'success' && !job.error_message && (
                      <Chip label="Completed" color="success" size="small" />
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Trigger Ingestion Dialog */}
      <Dialog open={isTriggerDialogOpen} onClose={handleTriggerCancel} maxWidth="sm" fullWidth>
        <DialogTitle>Trigger Data Ingestion</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Select a data source to trigger manual ingestion. The ingestion will run incrementally.
          </Typography>
          <FormControl fullWidth sx={{ mt: 2 }}>
            <InputLabel id="data-source-select-label">Data Source</InputLabel>
            <Select
              labelId="data-source-select-label"
              id="data-source-select"
              value={selectedDataSourceId}
              label="Data Source"
              onChange={(e) => setSelectedDataSourceId(e.target.value as number)}
            >
              {dataSourcesData?.items.map((source) => (
                <MenuItem key={source.id} value={source.id}>
                  {source.name} ({source.type})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleTriggerCancel} disabled={triggerMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleTriggerConfirm}
            variant="contained"
            disabled={!selectedDataSourceId || triggerMutation.isPending}
          >
            {triggerMutation.isPending ? 'Triggering...' : 'Trigger'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Toast Notification */}
      <Snackbar
        open={toast.open}
        autoHideDuration={6000}
        onClose={handleCloseToast}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleCloseToast} severity={toast.severity} sx={{ width: '100%' }}>
          {toast.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
