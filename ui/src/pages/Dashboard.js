import React, { useState, useEffect } from 'react';
import {
  Typography,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Box
} from '@mui/material';
import KeyMasterAdminClient from '../api/keymaster';

function Dashboard({ baseURL, adminToken }) {
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkHealth = async () => {
      setLoading(true);
      const client = new KeyMasterAdminClient(baseURL, adminToken);
      const result = await client.healthCheck();
      setHealthStatus(result);
      setLoading(false);
    };

    // Only check health if we have a baseURL
    if (baseURL) {
      checkHealth();
    } else {
      setLoading(false);
    }
  }, [baseURL, adminToken]);

  return (
    <div>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>
              
              {loading ? (
                <Box display="flex" justifyContent="center" alignItems="center" minHeight={100}>
                  <CircularProgress />
                </Box>
              ) : healthStatus ? (
                <div>
                  {healthStatus.success ? (
                    <Alert severity="success">
                      Service is running healthy
                    </Alert>
                  ) : (
                    <Alert severity="error">
                      Service is unavailable: {healthStatus.error?.error?.message || healthStatus.error?.message || 'Unknown error'}
                    </Alert>
                  )}
                </div>
              ) : baseURL ? (
                <Alert severity="info">
                  Checking service status...
                </Alert>
              ) : (
                <Alert severity="warning">
                  Please configure your API settings in the Settings menu
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
        
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Getting Started
              </Typography>
              <Typography variant="body1">
                Welcome to the KeyMaster Workbench! This interface allows you to manage your API projects and keys.
              </Typography>
              <ul>
                <li>
                  <Typography variant="body1">
                    Navigate to <b>Projects</b> to create and manage your projects
                  </Typography>
                </li>
                <li>
                  <Typography variant="body1">
                    Go to <b>API Keys</b> to generate, view, and revoke API keys
                  </Typography>
                </li>
                <li>
                  <Typography variant="body1">
                    Use the <b>Settings</b> menu to configure your API connection
                  </Typography>
                </li>
              </ul>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </div>
  );
}

export default Dashboard;