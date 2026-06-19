/**
 * DeleteConfirmDialog Component
 * 
 * Confirmation dialog for deleting data sources.
 * Warns users about cascade deletion of associated documents and embeddings.
 */

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Alert,
} from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';

interface DeleteConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  dataSourceName: string;
  isDeleting: boolean;
}

export function DeleteConfirmDialog({
  open,
  onClose,
  onConfirm,
  dataSourceName,
  isDeleting,
}: DeleteConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <WarningIcon color="error" />
        Confirm Delete
      </DialogTitle>
      <DialogContent>
        <Typography variant="body1" gutterBottom>
          Are you sure you want to delete the data source <strong>"{dataSourceName}"</strong>?
        </Typography>
        <Alert severity="warning" sx={{ mt: 2 }}>
          <Typography variant="body2">
            <strong>Warning:</strong> This operation cannot be undone. It will:
          </Typography>
          <Typography variant="body2" component="ul" sx={{ mt: 1, mb: 0 }}>
            <li>Delete the data source permanently</li>
            <li>Remove all associated knowledge documents</li>
            <li>Remove all associated document embeddings</li>
          </Typography>
        </Alert>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isDeleting}>
          Cancel
        </Button>
        <Button onClick={onConfirm} variant="contained" color="error" disabled={isDeleting}>
          {isDeleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
