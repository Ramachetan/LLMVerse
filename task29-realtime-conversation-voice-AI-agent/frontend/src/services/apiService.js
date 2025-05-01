import axios from 'axios';

const API_URL = 'http://localhost:5000'; // Update this to your API URL

const apiService = {
  // Get all tools
  getTools: async () => {
    try {
      const response = await axios.get(`${API_URL}/tools/`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },
  
  // Add Python tool
  addPythonTool: async (functionCode, functionName) => {
    try {
      const response = await axios.post(`${API_URL}/tools/python-function`, {
        function_code: functionCode,
        function_name: functionName
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
  
  // Add OpenAPI tool
  addOpenAPITool: async (spec, operationId) => {
    try {
      const response = await axios.post(`${API_URL}/tools/openapi-spec`, {
        spec: typeof spec === 'string' ? JSON.parse(spec) : spec,
        operation_id: operationId || undefined
      });
      return response.data;
    } catch (error) {
      throw error;
    }
  },
  
  // Delete tool
  deleteTool: async (toolName) => {
    try {
      const response = await axios.delete(`${API_URL}/tools/${toolName}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  }
};

export default apiService;