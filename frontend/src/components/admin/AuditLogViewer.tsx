/**
 * AuditLogViewer Component
 *
 * Admin interface for viewing and filtering audit logs.
 * Features:
 * - Audit log table with columns: timestamp, user, action, resource, details
 * - Filter controls: date range, user, action type
 * - Pagination controls: previous, next, page size
 * - Expandable row details for viewing before/after changes
 */

import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Collapse,
  Chip,
  TextField,
  Grid,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Button,
  CircularProgress,
  Alert,
  Pagination,
  SelectChangeEvent,
} from '@mui/material';
import {
  KeyboardArrowDown as KeyboardArrowDownIcon,
  KeyboardArrowUp as KeyboardArrowUpIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';

// Audit log interface based on backend schema
interface AuditLog {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  resource_type: string | null;
  resource_id: number | null;
  changes: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditLogListResponse {
  items: AuditLog[];
  total: number;
  limit: number;
  offset: number;
}

interface AuditLogRowProps {
  log: AuditLog;
}

function AuditLogRow({ log }: AuditLogRowProps) {
  const [open, setOpen] = useState(false);

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // Get action chip color
  const getActionColor = (
    action: string
  ): 'success' | 'info' | 'error' | 'default' => {
    switch (action.toLowerCase()) {
      case 'create':
        return 'success';
      case 'update':
        return 'info';
      case 'delete':
        return 'error';
      default:
        return 'default';
    }
  };

  return (
    <>
      <TableRow sx={{ '& > *': { borderBottom: 'unset' } }}>
        <TableCell>
          <IconButton size="small" onClick={() => setOpen(!open)}>
            {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
          </IconButton>
        </TableCell>
        <TableCell>{formatTimestamp(log.created_at)}</TableCell>
        <TableCell>{log.user_email || 'System'}</TableCell>
        <TableCell>
          <Chip
            label={log.action}
            color={getActionColor(log.action)}
            size="small"
          />
        </TableCell>
        <TableCell>{log.resource_type || 'N/A'}</TableCell>
        <TableCell>{log.resource_id || 'N/A'}</TableCell>
      </TableRow>
      <TableRow>
        <TableCell style={{ paddingBottom: 0, paddingTop: 0 }} colSpan={6}>
          <Collapse in={open} timeout="auto" unmountOnExit>
            <Box sx={{ margin: 2 }}>
              <Typography variant="h6" gutterBottom component="div">
                Details
              </Typography>
              <Grid container spacing={2}>
                {log.ip_address && (
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">
                      IP Address
                    </Typography>
                    <Typography variant="body1">{log.ip_address}</Typography>
                  </Grid>
                )}
                {log.changes && (
                  <Grid item xs={12}>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      gutterBottom
                    >
                      Changes
                    </Typography>
                    <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                      <pre
                        style={{
                          margin: 0,
                          whiteSpace: 'pre-wrap',
                          fontSize: '0.875rem',
                        }}
                      >
                        {JSON.stringify(log.changes, null, 2)}
                      </pre>
                    </Paper>
                  </Grid>
                )}
              </Grid>
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
}

export function AuditLogViewer() {
  // Filter state
  const [userId, setUserId] = useState<string>('');
  const [action, setAction] = useState<string>('');
  const [resourceType, setResourceType] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  // Pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  // Build query parameters
  const buildQueryParams = () => {
    const params = new URLSearchParams();
    if (userId) params.append('user_id', userId);
    if (action) params.append('action', action);
    if (resourceType) params.append('resource_type', resourceType);
    if (startDate)
      params.append('start_date', new Date(startDate).toISOString());
    if (endDate) params.append('end_date', new Date(endDate).toISOString());
    params.append('limit', pageSize.toString());
    params.append('offset', ((page - 1) * pageSize).toString());
    return params.toString();
  };

  // Fetch audit logs
  const { data, isLoading, error } = useQuery<AuditLogListResponse>({
    queryKey: [
      'auditLogs',
      userId,
      action,
      resourceType,
      startDate,
      endDate,
      page,
      pageSize,
    ],
    queryFn: async () => {
      const queryString = buildQueryParams();
      const response = await api.get(`/v1/admin/audit-logs?${queryString}`);
      return response.data;
    },
  });

  // Handle filter changes
  const handleActionChange = (event: SelectChangeEvent) => {
    setAction(event.target.value);
    setPage(1); // Reset to first page on filter change
  };

  const handleResourceTypeChange = (event: SelectChangeEvent) => {
    setResourceType(event.target.value);
    setPage(1);
  };

  const handlePageSizeChange = (event: SelectChangeEvent) => {
    setPageSize(Number(event.target.value));
    setPage(1);
  };

  const handlePageChange = (
    _event: React.ChangeEvent<unknown>,
    value: number
  ) => {
    setPage(value);
  };

  const handleClearFilters = () => {
    setUserId('');
    setAction('');
    setResourceType('');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        Audit Logs
      </Typography>

      {/* Filters Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <FilterListIcon sx={{ mr: 1 }} />
            <Typography variant="h6">Filters</Typography>
          </Box>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                label="User ID"
                value={userId}
                onChange={(e) => {
                  setUserId(e.target.value);
                  setPage(1);
                }}
                fullWidth
                size="small"
                type="number"
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Action</InputLabel>
                <Select
                  value={action}
                  onChange={handleActionChange}
                  label="Action"
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="create">Create</MenuItem>
                  <MenuItem value="update">Update</MenuItem>
                  <MenuItem value="delete">Delete</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Resource Type</InputLabel>
                <Select
                  value={resourceType}
                  onChange={handleResourceTypeChange}
                  label="Resource Type"
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="data_source">Data Source</MenuItem>
                  <MenuItem value="user">User</MenuItem>
                  <MenuItem value="config">Config</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Button variant="outlined" onClick={handleClearFilters} fullWidth>
                Clear Filters
              </Button>
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                label="Start Date"
                type="datetime-local"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setPage(1);
                }}
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={4}>
              <TextField
                label="End Date"
                type="datetime-local"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setPage(1);
                }}
                fullWidth
                size="small"
                InputLabelProps={{ shrink: true }}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Table Section */}
      {(() => {
        if (isLoading) {
          return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          );
        }
        if (error) {
          return (
            <Alert severity="error">
              Failed to load audit logs:{' '}
              {error instanceof Error ? error.message : 'Unknown error'}
            </Alert>
          );
        }
        if (!data || data.items.length === 0) {
          return <Alert severity="info">No audit logs found</Alert>;
        }
        return (
          <>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell width={50} />
                  <TableCell>Timestamp</TableCell>
                  <TableCell>User</TableCell>
                  <TableCell>Action</TableCell>
                  <TableCell>Resource Type</TableCell>
                  <TableCell>Resource ID</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.items.map((log) => (
                  <AuditLogRow key={log.id} log={log} />
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination Controls */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mt: 3,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Showing {data.offset + 1} -{' '}
                {Math.min(data.offset + data.limit, data.total)} of {data.total}{' '}
                logs
              </Typography>
              <FormControl size="small">
                <InputLabel>Page Size</InputLabel>
                <Select
                  value={pageSize.toString()}
                  onChange={handlePageSizeChange}
                  label="Page Size"
                  sx={{ minWidth: 100 }}
                >
                  <MenuItem value="10">10</MenuItem>
                  <MenuItem value="20">20</MenuItem>
                  <MenuItem value="50">50</MenuItem>
                  <MenuItem value="100">100</MenuItem>
                </Select>
              </FormControl>
            </Box>
            <Pagination
              count={totalPages}
              page={page}
              onChange={handlePageChange}
              color="primary"
              showFirstButton
              showLastButton
            />
          </Box>
          </>
        );
      })()}
    </Box>
  );
}
