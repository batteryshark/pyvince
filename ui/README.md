# KeyMaster Workbench

A React-based workbench for managing projects and API keys with the KeyMaster service.

## Features

- Dashboard with system status
- Project management (create/view projects)
- API key management (mint, view, revoke keys)
- Dark theme UI with Material Design
- Responsive layout for desktop and mobile

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm start
   ```

3. Open your browser to http://localhost:3000

## Configuration

The workbench requires connection to a running KeyMaster service:

1. Click the "Settings" icon in the left navigation
2. Enter the base URL of your KeyMaster service (e.g., http://localhost:8000)
3. Enter your admin token (found in your KeyMaster .env file as ADMIN_SECRET)

## Project Structure

```
src/
├── api/          # API client for KeyMaster service
├── components/   # Reusable UI components
├── pages/        # Main page components
├── App.js        # Main application component
└── index.js      # Entry point
```