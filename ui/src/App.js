import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ApiKeys from './pages/ApiKeys';
import Navigation from './components/Navigation';
import { Box, Toolbar } from '@mui/material';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9',
    },
    secondary: {
      main: '#f48fb1',
    },
    background: {
      default: '#121212',
      paper: '#1e1e1e',
    },
  },
});

function App() {
  const [apiBaseURL, setApiBaseURL] = useState('http://localhost:8000');
  const [adminToken, setAdminToken] = useState('');

  useEffect(() => {
    // Load settings from localStorage if available
    const savedBaseURL = localStorage.getItem('keymaster_baseURL');
    const savedToken = localStorage.getItem('keymaster_adminToken');
    
    if (savedBaseURL) setApiBaseURL(savedBaseURL);
    if (savedToken) setAdminToken(savedToken);
  }, []);

  const updateSettings = (baseURL, token) => {
    setApiBaseURL(baseURL);
    setAdminToken(token);
    localStorage.setItem('keymaster_baseURL', baseURL);
    localStorage.setItem('keymaster_adminToken', token);
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Router>
        <Box sx={{ display: 'flex' }}>
          <Navigation 
            apiBaseURL={apiBaseURL} 
            adminToken={adminToken} 
            updateSettings={updateSettings} 
          />
          <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
            <Toolbar />
            <Routes>
              <Route path="/" element={<Dashboard baseURL={apiBaseURL} adminToken={adminToken} />} />
              <Route path="/projects" element={<Projects baseURL={apiBaseURL} adminToken={adminToken} />} />
              <Route path="/api-keys" element={<ApiKeys baseURL={apiBaseURL} adminToken={adminToken} />} />
            </Routes>
          </Box>
        </Box>
      </Router>
    </ThemeProvider>
  );
}

export default App;