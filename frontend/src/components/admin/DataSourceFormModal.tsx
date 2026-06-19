/**
 * DataSourceFormModal Component
 * 
 * Modal dialog for creating/editing data sources with form validation.
 * Features:
 * - Required field validation (name, type, config)
 * - Cron expression validation for sync schedule
 * - JSON validation for config field
 * - Type-specific config field hints
 */

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Box,
  Typography,
  Alert,
} from '@mui/material';

interface DataSourceFormData {
  name: string;
  type: 'confluence' | 'jira' | 'onboarding' | 'custom';
  config: Record<string, unknown>;
  sync_schedule: string;
  is_active: boolean;
}

interface DataSourceFormModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: DataSourceFormData | Partial<DataSourceFormData>) => void;
  initialData?: Partial<DataSourceFormData & { id: number }>;
  isSubmitting: boolean;
}

interface FormErrors {
  name?: string;
  type?: string;
  config?: string;
  sync_schedule?: string;
}

export function DataSourceFormModal({
  open,
  onClose,
  onSubmit,
  initialData,
  isSubmitting,
}: DataSourceFormModalProps) {
  const isEditMode = !!initialData?.id;

  const [formData, setFormData] = useState<DataSourceFormData>({
    name: '',
    type: 'confluence',
    config: {},
    sync_schedule: '',
    is_active: true,
  });

  const [configText, setConfigText] = useState('{}');
  const [errors, setErrors] = useState<FormErrors>({});

  // Initialize form with initial data
  useEffect(() => {
    if (initialData) {
      setFormData({
        name: initialData.name || '',
        type: initialData.type || 'confluence',
        config: initialData.config || {},
        sync_schedule: initialData.sync_schedule || '',
        is_active: initialData.is_active ?? true,
      });
      setConfigText(JSON.stringify(initialData.config || {}, null, 2));
    } else {
      // Reset form for create mode
      setFormData({
        name: '',
        type: 'confluence',
        config: {},
        sync_schedule: '',
        is_active: true,
      });
      setConfigText('{}');
    }
    setErrors({});
  }, [initialData, open]);

  // Validate cron expression
  const validateCronExpression = (cron: string): boolean => {
    if (!cron.trim()) return true; // Empty is valid (optional field)
    
    // Basic cron validation: 5 or 6 fields separated by spaces
    const parts = cron.trim().split(/\s+/);
    if (parts.length < 5 || parts.length > 6) {
      return false;
    }
    
    // Each part should be a valid cron field (number, *, /, -, or ,)
    const cronFieldRegex = /^(\*|([0-9]|[1-5][0-9])([-,\/]([0-9]|[1-5][0-9]))*)$/;
    return parts.every((part) => cronFieldRegex.test(part) || part === '*');
  };

  // Validate form
  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.type) {
      newErrors.type = 'Type is required';
    }

    // Validate config JSON
    try {
      const parsedConfig = JSON.parse(configText);
      if (typeof parsedConfig !== 'object' || parsedConfig === null || Array.isArray(parsedConfig)) {
        newErrors.config = 'Config must be a valid JSON object';
      }
    } catch (err) {
      newErrors.config = 'Invalid JSON format';
    }

    // Validate cron expression
    if (formData.sync_schedule && !validateCronExpression(formData.sync_schedule)) {
      newErrors.sync_schedule = 'Invalid cron expression (e.g., "0 2 * * *" for daily at 2 AM)';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validateForm()) {
      return;
    }

    try {
      const parsedConfig = JSON.parse(configText);
      const submitData = {
        ...formData,
        config: parsedConfig,
      };
      onSubmit(submitData);
    } catch (err) {
      setErrors({ ...errors, config: 'Failed to parse config JSON' });
    }
  };

  const handleConfigTextChange = (text: string) => {
    setConfigText(text);
    // Clear config error when user types
    if (errors.config) {
      const { config, ...rest } = errors;
      setErrors(rest);
    }
  };

  const getConfigPlaceholder = () => {
    switch (formData.type) {
      case 'confluence':
        return JSON.stringify({
          url: 'https://wiki.example.com',
          username: 'admin',
          api_token: 'your_token',
          space_key: 'DOCS',
        }, null, 2);
      case 'jira':
        return JSON.stringify({
          url: 'https://jira.example.com',
          username: 'admin',
          api_token: 'your_token',
          project_key: 'PROJ',
        }, null, 2);
      case 'onboarding':
        return JSON.stringify({
          storage_path: '/path/to/onboarding/docs',
        }, null, 2);
      case 'custom':
        return JSON.stringify({
          url: 'https://api.example.com',
          api_key: 'your_key',
        }, null, 2);
      default:
        return '{}';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{isEditMode ? 'Edit Data Source' : 'Create Data Source'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {/* Name Field */}
          <TextField
            label="Name"
            value={formData.name}
            onChange={(e) => {
              setFormData({ ...formData, name: e.target.value });
              if (errors.name) {
                const { name, ...rest } = errors;
                setErrors(rest);
              }
            }}
            error={!!errors.name}
            helperText={errors.name}
            required
            fullWidth
            autoFocus={!isEditMode}
          />

          {/* Type Field */}
          <FormControl fullWidth required error={!!errors.type}>
            <InputLabel>Type</InputLabel>
            <Select
              value={formData.type}
              label="Type"
              onChange={(e) => {
                const newType = e.target.value as DataSourceFormData['type'];
                setFormData({ ...formData, type: newType });
                if (errors.type) {
                  const { type, ...rest } = errors;
                  setErrors(rest);
                }
              }}
              disabled={isEditMode} // Don't allow changing type in edit mode
            >
              <MenuItem value="confluence">Confluence</MenuItem>
              <MenuItem value="jira">JIRA</MenuItem>
              <MenuItem value="onboarding">Onboarding</MenuItem>
              <MenuItem value="custom">Custom</MenuItem>
            </Select>
          </FormControl>

          {/* Config Field */}
          <Box>
            <TextField
              label="Configuration (JSON)"
              value={configText}
              onChange={(e) => handleConfigTextChange(e.target.value)}
              error={!!errors.config}
              helperText={errors.config}
              required
              fullWidth
              multiline
              rows={8}
              placeholder={getConfigPlaceholder()}
              sx={{ fontFamily: 'monospace' }}
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Enter configuration as JSON. Example for {formData.type} shown in placeholder.
            </Typography>
          </Box>

          {/* Sync Schedule Field */}
          <TextField
            label="Sync Schedule (Cron Expression)"
            value={formData.sync_schedule}
            onChange={(e) => {
              setFormData({ ...formData, sync_schedule: e.target.value });
              if (errors.sync_schedule) {
                const { sync_schedule, ...rest } = errors;
                setErrors(rest);
              }
            }}
            error={!!errors.sync_schedule}
            helperText={errors.sync_schedule || 'Optional. E.g., "0 2 * * *" for daily at 2 AM'}
            fullWidth
            placeholder="0 2 * * *"
          />

          {/* Active Switch */}
          <FormControlLabel
            control={
              <Switch
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
            }
            label="Active"
          />

          {/* Information Alert */}
          <Alert severity="info">
            <Typography variant="body2">
              <strong>Required fields by type:</strong>
            </Typography>
            <Typography variant="body2" component="div">
              • <strong>Confluence:</strong> url, username, api_token, space_key<br />
              • <strong>JIRA:</strong> url, username, api_token, project_key<br />
              • <strong>Onboarding:</strong> storage_path<br />
              • <strong>Custom:</strong> url
            </Typography>
          </Alert>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={isSubmitting}>
          {isSubmitting ? 'Saving...' : (isEditMode ? 'Update' : 'Create')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
