import React from 'react';

const ToolList = ({ tools, onDelete, onRefresh }) => {
  return (
    <div>
      <div className="header">
        <h2>Available Tools</h2>
        <button onClick={onRefresh}>Refresh Tools</button>
      </div>
      
      {tools.length === 0 ? (
        <div className="empty-message">
          No tools available. Add one to get started!
        </div>
      ) : (
        <div className="tool-list">
          {tools.map((tool) => (
            <div key={tool.name} className="tool-item">
              <div className="tool-header">
                <h3>{tool.name}</h3>
                <button onClick={() => onDelete(tool.name)}>Delete</button>
              </div>
              <p className="tool-description">{tool.description}</p>
              
              {tool.parameters && tool.parameters.properties && (
                <div className="parameters">
                  <h4>Parameters:</h4>
                  <div className="param-list">
                    {Object.entries(tool.parameters.properties).map(([name, param]) => (
                      <div key={name} className="param-item">
                        <div className="param-name">{name}</div>
                        <div className="param-details">
                          <span>Type: {param.type}</span>
                          {param.description && <span>{param.description}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ToolList;