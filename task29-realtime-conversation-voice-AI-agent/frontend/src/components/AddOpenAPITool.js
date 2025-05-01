import React, { useState } from 'react';

const AddOpenAPITool = ({ onToolAdded }) => {
  const [spec, setSpec] = useState('{\n  "openapi": "3.0.0",\n  "info": {\n    "title": "Example API",\n    "version": "1.0.0"\n  },\n  "paths": {\n    "/example": {\n      "get": {\n        "operationId": "getExample",\n        "summary": "Get example data",\n        "responses": {\n          "200": {\n            "description": "Success"\n          }\n        }\n      }\n    }\n  }\n}');
  const [operationId, setOperationId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  
  const handleSubmit = async () => {
    setError('');
    setIsSubmitting(true);
    
    try {
      // Validate JSON
      JSON.parse(spec);
      
      await onToolAdded(spec, operationId);
    } catch (error) {
      setError(error.message || 'Failed to add tool');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  return (
    <div className="form-container">
      <h2>Add OpenAPI Tool</h2>
      
      {error && (
        <div className="error">
          {error}
        </div>
      )}
      
      <div className="form">
        <div className="form-group">
          <label htmlFor="operationId">Operation ID (Optional)</label>
          <input
            id="operationId"
            type="text"
            value={operationId}
            onChange={(e) => setOperationId(e.target.value)}
            placeholder="Enter operation ID (optional)"
          />
          <p className="help-text">
            Leave blank to use the first operation in the spec
          </p>
        </div>
        
        <div className="form-group">
          <label htmlFor="spec">OpenAPI Specification</label>
          <textarea
            id="spec"
            value={spec}
            onChange={(e) => setSpec(e.target.value)}
            rows={15}
            placeholder="Paste your OpenAPI JSON specification here"
          />
        </div>
        
        <div className="form-actions">
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Adding...' : 'Add OpenAPI Tool'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AddOpenAPITool;