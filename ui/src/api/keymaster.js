import axios from 'axios';

class KeyMasterAdminClient {
  constructor(baseURL, adminToken) {
    this.baseURL = baseURL;
    this.adminToken = adminToken;
    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.adminToken}`
      },
      timeout: 10000 // 10 second timeout
    });
  }

  // Health check
  async healthCheck() {
    try {
      const response = await this.client.get('/health');
      return { success: true, data: response.data };
    } catch (error) {
      if (error.code === 'ECONNABORTED') {
        return { success: false, error: { message: 'Request timeout - server not responding' } };
      }
      if (error.response) {
        // Server responded with error status
        return { success: false, error: error.response.data || { message: `Server error: ${error.response.status}` } };
      } else if (error.request) {
        // Request was made but no response received
        return { success: false, error: { message: 'No response from server - check if service is running' } };
      } else {
        // Something else happened
        return { success: false, error: { message: `Request failed: ${error.message}` } };
      }
    }
  }

  // Project management
  async createProject(projectId, label, owner) {
    try {
      const response = await this.client.post('/v1/admin/create-project', null, {
        params: {
          project_id: projectId,
          label,
          owner
        }
      });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async getProject(projectId) {
    try {
      const response = await this.client.get(`/v1/admin/project/${projectId}`);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  // API key management
  async mintKey(projectId, owner, metadata, expiresInDays = null) {
    try {
      const requestData = {
        project_id: projectId,
        owner,
        metadata
      };

      if (expiresInDays !== null) {
        const expiresAt = new Date();
        expiresAt.setDate(expiresAt.getDate() + expiresInDays);
        requestData.expires_at = expiresAt.getTime() / 1000;
      }

      const response = await this.client.post('/v1/mint-key', requestData);
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async revokeKey(projectId, keyId) {
    try {
      const response = await this.client.post('/v1/revoke-key', {
        project_id: projectId,
        key_id: keyId
      });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async listKeys(projectId, offset = 0, limit = 50) {
    try {
      const response = await this.client.get('/v1/list-keys', {
        params: {
          project_id: projectId,
          offset,
          limit
        }
      });
      return { success: true, data: response.data };
    } catch (error) {
      return this.handleError(error);
    }
  }

  async listAllKeys(projectId) {
    try {
      let allKeys = [];
      let offset = 0;
      const limit = 50;

      while (true) {
        const result = await this.listKeys(projectId, offset, limit);
        
        if (!result.success) {
          return result;
        }

        allKeys = [...allKeys, ...result.data.items];

        if (!result.data.next || result.data.items.length < limit) {
          break;
        }

        offset += limit;
      }

      return { success: true, data: allKeys };
    } catch (error) {
      return this.handleError(error);
    }
  }

  // Helper method to handle errors consistently
  handleError(error) {
    if (error.code === 'ECONNABORTED') {
      return { success: false, error: { error: { message: 'Request timeout - server not responding' } } };
    }
    if (error.response) {
      // Server responded with error status
      return { success: false, error: error.response.data || { error: { message: `Server error: ${error.response.status}` } } };
    } else if (error.request) {
      // Request was made but no response received
      return { success: false, error: { error: { message: 'No response from server - check if service is running' } } };
    } else {
      // Something else happened
      return { success: false, error: { error: { message: `Request failed: ${error.message}` } } };
    }
  }
}

export default KeyMasterAdminClient;