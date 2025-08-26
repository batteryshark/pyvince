import React, { useState } from 'react';
import {
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  Button,
  Box,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Snackbar
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import KeyMasterAdminClient from '../api/keymaster';

function Projects({ baseURL, adminToken }) {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [newProject, setNewProject] = useState({
    projectId: '',
    label: '',
    owner: ''
  });

  const handleCreateProject = async () => {
    if (!newProject.projectId || !newProject.label || !newProject.owner) {
      setError('All fields are required');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    const client = new KeyMasterAdminClient(baseURL, adminToken);
    const result = await client.createProject(
      newProject.projectId,
      newProject.label,
      newProject.owner
    );

    if (result.success) {
      setSuccess('Project created successfully');
      setOpenDialog(false);
      setNewProject({ projectId: '', label: '', owner: '' });
    } else {
      setError(result.error?.error?.message || result.error?.message || 'Failed to create project');
    }

    setLoading(false);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    // Simulate refresh
    setTimeout(() => setRefreshing(false), 500);
  };

  return (
    <div>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          Projects
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing}
            sx={{ mr: 1 }}
          >
            {refreshing ? <CircularProgress size={20} /> : 'Refresh'}
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setOpenDialog(true)}
          >
            Create Project
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Projects
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Manage your API projects. Note: Project listing is not available in this version.
              </Typography>
              
              <Alert severity="info" sx={{ mb: 2 }}>
                Project listing functionality is not available in the current API. You can still create new projects 
                and use them for API key management. To verify a project exists, try creating an API key for it.
              </Alert>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create New Project</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              label="Project ID"
              fullWidth
              value={newProject.projectId}
              onChange={(e) => setNewProject({...newProject, projectId: e.target.value})}
              margin="normal"
              helperText="Unique identifier for your project"
            />
            <TextField
              label="Label"
              fullWidth
              value={newProject.label}
              onChange={(e) => setNewProject({...newProject, label: e.target.value})}
              margin="normal"
              helperText="Human-readable name for your project"
            />
            <TextField
              label="Owner"
              fullWidth
              value={newProject.owner}
              onChange={(e) => setNewProject({...newProject, owner: e.target.value})}
              margin="normal"
              helperText="Email or name of the project owner"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleCreateProject} 
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!success}
        autoHideDuration={6000}
        onClose={() => setSuccess('')}
        message={success}
      />
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError('')}
        message={error}
      />
    </div>
  );
}

export default Projects;