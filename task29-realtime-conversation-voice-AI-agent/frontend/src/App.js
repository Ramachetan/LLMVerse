import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import ToolList from './components/ToolList';
import AddPythonTool from './components/AddPythonTool';
import AddOpenAPITool from './components/AddOpenAPITool';
import apiService from './services/apiService';


function App() {
  const [tools, setTools] = useState([]);
  const [activeTab, setActiveTab] = useState('list');
  const [message, setMessage] = useState({ text: '', type: '' });
  
  const fetchTools = useCallback(async () => {
    try {
      const data = await apiService.getTools();
      setTools(data.tools || []);
    } catch (error) {
      showMessage(`Error fetching tools: ${error.message}`, 'error');
    }
  }, []);
  
  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: '', type: '' }), 3000);
  };

  const handleDeleteTool = async (toolName) => {
    try {
      const data = await apiService.deleteTool(toolName);
      showMessage(`${data.deleted_tool} deleted successfully`);
      fetchTools();
    } catch (error) {
      showMessage(`Error deleting tool: ${error.message}`, 'error');
    }
  };

  const handleAddPythonTool = async (functionCode, functionName) => {
    try {
      await apiService.addPythonTool(functionCode, functionName);
      fetchTools();
      showMessage('Python tool added successfully');
      setActiveTab('list');
    } catch (error) {
      showMessage(`Error adding tool: ${error.message}`, 'error');
    }
  };

  const handleAddOpenAPITool = async (spec, operationId) => {
    try {
      await apiService.addOpenAPITool(spec, operationId);
      fetchTools();
      showMessage('OpenAPI tool added successfully');
      setActiveTab('list');
    } catch (error) {
      showMessage(`Error adding tool: ${error.message}`, 'error');
    }
  };

  return (
    <div className="App">
      <div className="container">
        <div className="app-header">
          <h1>AI Assistant Tool Management</h1>
        </div>
        
        {message.text && (
          <div className="message-container">
            <div className={`message ${message.type}`}>
              {message.text}
            </div>
          </div>
        )}
        
        <div className="app-body">
          <div className="sidebar">
            <div className="sidebar-nav">
              <button 
                className={activeTab === 'list' ? 'active' : ''}
                onClick={() => setActiveTab('list')}
              >
                Available Tools
              </button>
              <button 
                className={activeTab === 'addPython' ? 'active' : ''}
                onClick={() => setActiveTab('addPython')}
              >
                Add Python Tool
              </button>
              <button 
                className={activeTab === 'addOpenAPI' ? 'active' : ''}
                onClick={() => setActiveTab('addOpenAPI')}
              >
                Add OpenAPI Tool
              </button>
            </div>
          </div>
          
          <div className="main-content">
            {activeTab === 'list' && (
              <ToolList tools={tools} onDelete={handleDeleteTool} onRefresh={fetchTools} />
            )}
            {activeTab === 'addPython' && (
              <AddPythonTool onToolAdded={handleAddPythonTool} />
            )}
            {activeTab === 'addOpenAPI' && (
              <AddOpenAPITool onToolAdded={handleAddOpenAPITool} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;