/**
 * MetricsDashboard Component
 *
 * Admin dashboard displaying system metrics and statistics.
 * Features:
 * - Metrics cards: total documents, total sessions, queries today, avg response time
 * - Bar/line charts for query trends using recharts library
 * - Real-time data fetching using React Query
 * - Material-UI cards and layout
 */

import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Description as DocumentIcon,
  Chat as ChatIcon,
  Search as SearchIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import api from '../../services/api';

// System metrics interface based on backend schema
interface SystemMetrics {
  total_documents: number;
  active_documents: number;
  sessions: {
    total_all_time: number;
    active_sessions: number;
  };
  queries: {
    total_today: number;
    total_this_week: number;
    total_this_month: number;
    total_all_time: number;
  };
  average_response_time_ms: number | null;
  database: {
    database_size_bytes: number;
    database_size_mb: number;
    total_embeddings: number;
  };
  ingestion: {
    total_jobs: number;
    successful_jobs: number;
    failed_jobs: number;
    success_rate: number;
    last_successful_run: string | null;
    last_failed_run: string | null;
  };
  timestamp: string;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            mb: 2,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: 2,
              bgcolor: `${color}.100`,
              color: `${color}.main`,
            }}
          >
            {icon}
          </Box>
        </Box>
        <Typography variant="h4" component="div" fontWeight="bold">
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          {title}
        </Typography>
      </CardContent>
    </Card>
  );
}

export function MetricsDashboard() {
  // Fetch system metrics
  const {
    data: metrics,
    isLoading,
    error,
  } = useQuery<SystemMetrics>({
    queryKey: ['systemMetrics'],
    queryFn: async () => {
      const response = await api.get('/v1/admin/metrics');
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: 400,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        Failed to load metrics:{' '}
        {error instanceof Error ? error.message : 'Unknown error'}
      </Alert>
    );
  }

  if (!metrics) {
    return <Alert severity="info">No metrics data available</Alert>;
  }

  // Prepare chart data for query trends
  const queryTrendData = [
    { period: 'Today', queries: metrics.queries.total_today },
    { period: 'This Week', queries: metrics.queries.total_this_week },
    { period: 'This Month', queries: metrics.queries.total_this_month },
    { period: 'All Time', queries: metrics.queries.total_all_time },
  ];

  // Format response time
  const formatResponseTime = (ms: number | null) => {
    if (ms === null) return 'N/A';
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        System Metrics
      </Typography>

      {/* Metric Cards Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Documents"
            value={metrics.total_documents.toLocaleString()}
            icon={<DocumentIcon />}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Total Sessions"
            value={metrics.sessions.total_all_time.toLocaleString()}
            icon={<ChatIcon />}
            color="success"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Queries Today"
            value={metrics.queries.total_today.toLocaleString()}
            icon={<SearchIcon />}
            color="info"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="Avg Response Time"
            value={formatResponseTime(metrics.average_response_time_ms)}
            icon={<SpeedIcon />}
            color="warning"
          />
        </Grid>
      </Grid>

      {/* Charts Section */}
      <Grid container spacing={3}>
        {/* Query Trends Bar Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Query Trends
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={queryTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="queries" fill="#1976d2" name="Queries" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Query Trends Line Chart */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Query Growth
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={queryTrendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="period" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="queries"
                    stroke="#2e7d32"
                    strokeWidth={2}
                    name="Queries"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Additional Metrics */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Additional Statistics
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Active Documents
                  </Typography>
                  <Typography variant="h6">
                    {metrics.active_documents.toLocaleString()}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Active Sessions
                  </Typography>
                  <Typography variant="h6">
                    {metrics.sessions.active_sessions.toLocaleString()}
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Database Size
                  </Typography>
                  <Typography variant="h6">
                    {metrics.database.database_size_mb.toFixed(2)} MB
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="body2" color="text.secondary">
                    Total Embeddings
                  </Typography>
                  <Typography variant="h6">
                    {metrics.database.total_embeddings.toLocaleString()}
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
