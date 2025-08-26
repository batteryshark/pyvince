import React, { useState, useEffect, useCallback } from 'react';
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
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Chip,
  InputAdornment,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Block as RevokeIcon,
  ContentCopy as CopyIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon
} from '@mui/icons-material';
import KeyMasterAdminClient from '../api/keymaster';

function ApiKeys({ baseURL, adminToken }) {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [openMintDialog, setOpenMintDialog] = useState(false);
  const [openRevokeDialog, setOpenRevokeDialog] = useState(false);
  const [openApiKeyDialog, setOpenApiKeyDialog] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');
  const [selectedKey, setSelectedKey] = useState(null);
  const [keys, setKeys] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [newKey, setNewKey] = useState({
    projectId: '',
    owner: '',
    metadata: '',
    expiresInDays: ''
  });
  const [showApiKey, setShowApiKey] = useState(false);

  const loadKeys = useCallback(async (projectId) => {
    setRefreshing(true);
    setError('');
    
    const client = new KeyMasterAdminClient(baseURL, adminToken);
    const result = await client.listAllKeys(projectId);

    if (result.success) {
      setKeys(result.data || []);
      setSuccess('Keys loaded successfully');
    } else {
      setError(result.error?.error?.message || result.error?.message || 'Failed to load keys');
      setKeys([]);
    }
    
    setRefreshing(false);
  }, [baseURL, adminToken]);

  // Load keys when component mounts or when selectedProject changes
  useEffect(() => {
    if (selectedProject && baseURL && adminToken) {
      loadKeys(selectedProject);
    }
  }, [selectedProject, baseURL, adminToken, loadKeys]);

  const handleMintKey = async () => {
    // Use the project ID from the form or the selected project
    const projectId = newKey.projectId || selectedProject;
    
    if (!projectId || !newKey.owner || !newKey.metadata) {
      setError('Project ID, owner, and metadata are required');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    const client = new KeyMasterAdminClient(baseURL, adminToken);
    const result = await client.mintKey(
      projectId,
      newKey.owner,
      newKey.metadata,
      newKey.expiresInDays ? parseInt(newKey.expiresInDays) : null
    );

    if (result.success) {
      // Show the newly created API key
      setNewApiKey(result.data.api_key);
      setOpenApiKeyDialog(true);
      setOpenMintDialog(false);
      setNewKey({ projectId: '', owner: '', metadata: '', expiresInDays: '' });
      // Refresh keys list if we're viewing the same project
      if (selectedProject === projectId) {
        loadKeys(projectId);
      }
    } else {
      setError(result.error?.error?.message || result.error?.message || 'Failed to create API key');
    }

    setLoading(false);
  };

  const handleRevokeKey = async () => {
    if (!selectedKey) return;

    setLoading(true);
    setError('');
    setSuccess('');

    const client = new KeyMasterAdminClient(baseURL, adminToken);
    const result = await client.revokeKey(selectedKey.project_id, selectedKey.key_id);

    if (result.success) {
      setSuccess('API key revoked successfully');
      setOpenRevokeDialog(false);
      setSelectedKey(null);
      // Refresh keys list
      loadKeys(selectedProject);
    } else {
      setError(result.error?.error?.message || result.error?.message || 'Failed to revoke API key');
    }

    setLoading(false);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess('Copied to clipboard');
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp * 1000).toLocaleString();
  };

  const isExpired = (expiresAt) => {
    if (!expiresAt) return false;
    return new Date().getTime() > expiresAt * 1000;
  };

  const getStatus = (key) => {
    if (key.disabled) return 'Revoked';
    if (isExpired(key.expires_at)) return 'Expired';
    return 'Active';
  };

  const getStatusColor = (key) => {
    if (key.disabled) return 'error';
    if (isExpired(key.expires_at)) return 'warning';
    return 'success';
  };

  const handleRefresh = async () => {
    if (selectedProject) {
      await loadKeys(selectedProject);
    }
  };

  const handleProjectChange = (event) => {
    const projectId = event.target.value;
    setSelectedProject(projectId);
    setKeys([]);
  };

  return (
    <div>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">
          API Keys
        </Typography>
        <Box>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={handleRefresh}
            disabled={refreshing || !selectedProject}
            sx={{ mr: 1 }}
          >
            {refreshing ? <CircularProgress size={20} /> : 'Refresh'}
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setOpenMintDialog(true)}
            disabled={!selectedProject}
          >
            Mint Key
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
                API Key Management
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Create, view, and manage your API keys. Select a project to view its keys.
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <TextField
                  label="Project ID"
                  fullWidth
                  value={selectedProject}
                  onChange={handleProjectChange}
                  helperText="Enter a project ID to view its API keys"
                />
              </Box>
              
              {selectedProject && (
                <>
                  <TableContainer component={Paper}>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Key ID</TableCell>
                          <TableCell>Owner</TableCell>
                          <TableCell>Created</TableCell>
                          <TableCell>Expires</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell>Actions</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {keys.length > 0 ? (
                          keys.map((key) => (
                            <TableRow key={key.key_id}>
                              <TableCell>
                                <Tooltip title={key.key_id}>
                                  <span>{key.key_id.substring(0, 10)}...</span>
                                </Tooltip>
                              </TableCell>
                              <TableCell>{key.owner}</TableCell>
                              <TableCell>{formatDate(key.created_at)}</TableCell>
                              <TableCell>
                                {key.expires_at ? formatDate(key.expires_at) : 'Never'}
                              </TableCell>
                              <TableCell>
                                <Chip 
                                  label={getStatus(key)} 
                                  color={getStatusColor(key)} 
                                  size="small" 
                                />
                              </TableCell>
                              <TableCell>
                                <Tooltip title="Revoke Key">
                                  <IconButton 
                                    size="small" 
                                    onClick={() => {
                                      setSelectedKey(key);
                                      setOpenRevokeDialog(true);
                                    }}
                                    disabled={key.disabled || isExpired(key.expires_at)}
                                  >
                                    <RevokeIcon />
                                  </IconButton>
                                </Tooltip>
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={6} align="center">
                              <Typography variant="body2" color="text.secondary">
                                No keys found for this project.
                              </Typography>
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Mint Key Dialog */}
      <Dialog open={openMintDialog} onClose={() => setOpenMintDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Mint New API Key</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              label="Project ID"
              fullWidth
              value={newKey.projectId || selectedProject}
              onChange={(e) => setNewKey({...newKey, projectId: e.target.value})}
              margin="normal"
              helperText="The project this key belongs to"
            />
            <TextField
              label="Owner"
              fullWidth
              value={newKey.owner}
              onChange={(e) => setNewKey({...newKey, owner: e.target.value})}
              margin="normal"
              helperText="Name or email of the key owner"
            />
            <TextField
              label="Metadata"
              fullWidth
              multiline
              rows={3}
              value={newKey.metadata}
              onChange={(e) => setNewKey({...newKey, metadata: e.target.value})}
              margin="normal"
              helperText="Additional information about this key (can be JSON)"
            />
            <TextField
              label="Expires in Days (optional)"
              fullWidth
              type="number"
              value={newKey.expiresInDays}
              onChange={(e) => setNewKey({...newKey, expiresInDays: e.target.value})}
              margin="normal"
              helperText="Number of days until key expires"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenMintDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleMintKey} 
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : null}
          >
            Mint Key
          </Button>
        </DialogActions>
      </Dialog>

      {/* API Key Display Dialog */}
      <Dialog open={openApiKeyDialog} onClose={() => setOpenApiKeyDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Your New API Key</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Please copy this key now. For security reasons, it will not be shown again.
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={3}
            value={newApiKey}
            type={showApiKey ? "text" : "password"}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowApiKey(!showApiKey)}>
                    {showApiKey ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                  <IconButton onClick={() => copyToClipboard(newApiKey)}>
                    <CopyIcon />
                  </IconButton>
                </InputAdornment>
              ),
            }}
            sx={{ mb: 2 }}
          />
          <FormControlLabel
            control={<Checkbox checked={showApiKey} onChange={(e) => setShowApiKey(e.target.checked)} />}
            label="Show API Key"
          />
        </DialogContent>
        <DialogActions>
          <Button 
            onClick={() => copyToClipboard(newApiKey)} 
            variant="contained"
            startIcon={<CopyIcon />}
          >
            Copy to Clipboard
          </Button>
          <Button onClick={() => setOpenApiKeyDialog(false)}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Revoke Key Dialog */}
      <Dialog open={openRevokeDialog} onClose={() => setOpenRevokeDialog(false)}>
        <DialogTitle>Revoke API Key</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to revoke this API key? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenRevokeDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleRevokeKey} 
            variant="contained" 
            color="error"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} /> : <RevokeIcon />}
          >
            Revoke
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

export default ApiKeys;