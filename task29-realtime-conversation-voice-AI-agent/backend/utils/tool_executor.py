import json
import logging
import requests
import importlib.util
import sys
from typing import Dict, Any, List, Callable, Optional
import os
import inspect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TOOLS_FILE_PATH = "tools.json"
TOOL_FUNCTIONS_DIR = "tool_functions"

class ToolExecutor:
    """Handles execution of registered tools."""
    
    def __init__(self):
        """Initialize the tool executor."""
        # Ensure the tool functions directory exists
        os.makedirs(TOOL_FUNCTIONS_DIR, exist_ok=True)
        self._load_tools()
    
    def _load_tools(self) -> None:
        """Load tool definitions from the JSON file."""
        try:
            if os.path.exists(TOOLS_FILE_PATH):
                with open(TOOLS_FILE_PATH, "r") as f:
                    self.tools = json.load(f)
            else:
                logger.warning(f"Tools file {TOOLS_FILE_PATH} does not exist. Creating empty file.")
                self.tools = []
                with open(TOOLS_FILE_PATH, "w") as f:
                    json.dump(self.tools, f)
        except Exception as e:
            logger.error(f"Error loading tools: {e}")
            self.tools = []
    
    def get_tools_for_gemini(self) -> List[Dict[str, Any]]:
        """Return tools in the format expected by Gemini."""
        from google.genai import types
        
        gemini_tools = []
        
        for tool in self.tools:
            function_declaration = types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=types.Schema(**tool["parameters"])
            )
            
            gemini_tools.append(
                types.Tool(
                    function_declarations=[function_declaration]
                )
            )
        
        return gemini_tools
    
    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with the provided arguments."""
        logger.info(f"Executing tool '{name}' with args: {args}")
        
        # Find the tool definition
        tool_def = None
        for t in self.tools:
            if t["name"] == name:
                tool_def = t
                break
        
        if not tool_def:
            logger.error(f"Tool '{name}' not found")
            return {"error": f"Tool '{name}' not found"}
        
        try:
            # Check if we have a Python function implementation
            function_path = os.path.join(TOOL_FUNCTIONS_DIR, f"{name}.py")
            if os.path.exists(function_path):
                return self._execute_python_function(name, function_path, args)
            
            # If no Python function, try to call an API
            return self._execute_api_call(name, args)
            
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}")
            return {"error": f"Failed to execute tool: {str(e)}"}
    
    def _execute_python_function(self, name: str, function_path: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool implemented as a Python function."""
        try:
            # Load the module
            spec = importlib.util.spec_from_file_location(name, function_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module from {function_path}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            
            # Find the function
            function = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if callable(attr) and not attr_name.startswith("_"):
                    function = attr
                    break
            
            if not function:
                raise ValueError(f"No callable function found in {function_path}")
            
            # Execute the function
            result = function(**args)
            
            # Convert result to dict if it's a string (like JSON)
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # If not JSON, wrap it in a dict
                    result = {"result": result}
            elif not isinstance(result, dict):
                # Wrap non-dict results
                result = {"result": result}
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing Python function '{name}': {e}")
            raise
    
    def _execute_api_call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by making an API call."""
        # This is a simplified implementation. In a real system, you would:
        # 1. Retrieve API details (URL, method, auth) from a database or config
        # 2. Format the request properly based on the OpenAPI spec
        # 3. Handle various HTTP methods, auth, etc.
        
        # For now, we'll just return an error indicating API calls are not implemented
        logger.warning(f"API call execution not implemented for tool '{name}'")
        return {"error": "API call execution not implemented"}
    
    def save_python_function(self, name: str, function_code: str) -> bool:
        """Save a Python function implementation for a tool."""
        try:
            function_path = os.path.join(TOOL_FUNCTIONS_DIR, f"{name}.py")
            with open(function_path, "w") as f:
                f.write(function_code)
            return True
        except Exception as e:
            logger.error(f"Error saving Python function for tool '{name}': {e}")
            return False
    
    def register_openapi_tool(self, name: str, api_config: Dict[str, Any]) -> bool:
        """Register configuration for an OpenAPI tool."""
        # This would store the OpenAPI configuration for the tool
        # For simplicity, we'll just log that this would happen
        logger.info(f"Would register OpenAPI config for tool '{name}': {api_config}")
        return True