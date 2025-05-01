import json
import os
import inspect
import logging
import yaml
import re
from typing import Dict, List, Any, Optional, Union, Callable
from fastapi import APIRouter, HTTPException, Body, Query, Path
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TOOLS_FILE_PATH = "tools.json"
TOOLS_DIR = "tool_functions"

# Models for API requests and responses
class ToolParameter(BaseModel):
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    default: Optional[Any] = None

class ToolParameterProperties(BaseModel):
    type: str = "object"
    properties: Dict[str, ToolParameter] = {}
    required: Optional[List[str]] = None

class Tool(BaseModel):
    name: str
    description: str
    parameters: ToolParameterProperties = Field(default_factory=ToolParameterProperties)

class ToolList(BaseModel):
    tools: List[Tool] = []

class PythonFunctionInput(BaseModel):
    function_code: str
    function_name: Optional[str] = None

class OpenAPISpecInput(BaseModel):
    spec: Union[Dict[str, Any], str]
    operation_id: Optional[str] = None

class DeleteToolResponse(BaseModel):
    message: str
    deleted_tool: str

# Router definition
router = APIRouter(prefix="/tools", tags=["tools"])

# Helper functions
def load_tools() -> List[Dict[str, Any]]:
    """Load tools from the JSON file."""
    try:
        if os.path.exists(TOOLS_FILE_PATH):
            with open(TOOLS_FILE_PATH, "r") as f:
                return json.load(f)
        else:
            # If file doesn't exist, return empty list and create file
            with open(TOOLS_FILE_PATH, "w") as f:
                json.dump([], f)
            return []
    except Exception as e:
        logger.error(f"Error loading tools: {e}")
        # Return empty list in case of error, but don't overwrite existing file
        return []

def save_tools(tools: List[Dict[str, Any]]) -> bool:
    """Save tools to the JSON file."""
    try:
        with open(TOOLS_FILE_PATH, "w") as f:
            json.dump(tools, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving tools: {e}")
        return False

def parse_python_function(function_code: str) -> Tool:
    """Parse a Python function string to extract tool metadata."""
    # Create a namespace to execute the function code
    namespace = {}
    
    try:
        # Execute the function code to get it into namespace
        exec(function_code, namespace)
        
        # Find the function in namespace
        function_obj = None
        function_name = None
        
        for name, obj in namespace.items():
            if callable(obj) and name != "__builtins__":
                function_obj = obj
                function_name = name
                break
        
        if not function_obj:
            raise ValueError("No function found in the provided code")
        
        # Extract function signature and docstring
        signature = inspect.signature(function_obj)
        docstring = inspect.getdoc(function_obj) or ""
        
        # Process docstring to extract description
        description_lines = []
        param_docs = {}
        current_param = None
        parsing_args = False
        
        for line in docstring.split("\n"):
            line = line.strip()
            if line.lower().startswith("args:") or line.lower().startswith("parameters:"):
                parsing_args = True
                continue
            elif line.lower().startswith("returns:") or line.lower().startswith("return:"):
                parsing_args = False
                continue
            elif parsing_args and line and re.match(r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\(', line):
                # This looks like a parameter line
                param_match = re.match(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*:(.*)', line)
                if param_match:
                    current_param = param_match.group(1)
                    param_type = param_match.group(2).strip()
                    param_desc = param_match.group(3).strip()
                    param_docs[current_param] = {"type": param_type, "description": param_desc}
                continue
            elif not parsing_args and not current_param:
                if line:
                    description_lines.append(line)
        
        # Create tool description from function name and docstring
        tool_description = " ".join(description_lines) if description_lines else f"Function: {function_name}"
        
        # Create parameters from function signature
        parameters = {"type": "object", "properties": {}, "required": []}
        
        for param_name, param in signature.parameters.items():
            if param_name == "self":  # Skip 'self' for class methods
                continue
                
            param_info = {"type": "string"}  # Default type
            
            # Extract parameter type from annotations if available
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation.__name__ if hasattr(param.annotation, "__name__") else str(param.annotation)
                if annotation.lower() in ["str", "string"]:
                    param_info["type"] = "string"
                elif annotation.lower() in ["int", "integer", "float", "number"]:
                    param_info["type"] = "number"
                elif annotation.lower() in ["bool", "boolean"]:
                    param_info["type"] = "boolean"
                elif annotation.lower() in ["list", "array"]:
                    param_info["type"] = "array"
                elif annotation.lower() in ["dict", "object"]:
                    param_info["type"] = "object"
            
            # Extract description and other metadata from docstring
            if param_name in param_docs:
                param_info["description"] = param_docs[param_name]["description"]
                
                # Check for enumerated values in description
                enum_match = re.search(r'(?:one of|either) \"([^\"]+)\"(?:,| or) \"([^\"]+)\"', param_docs[param_name]["description"])
                if enum_match:
                    param_info["enum"] = [enum_match.group(1), enum_match.group(2)]
                
                # Look for other enum formats
                enum_match = re.search(r'\[(.*?)\]', param_docs[param_name]["description"])
                if enum_match:
                    enum_values = [val.strip(' "\'') for val in enum_match.group(1).split(",")]
                    if len(enum_values) > 1:
                        param_info["enum"] = enum_values
            
            # Set default value if available
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
                
            # Add to parameters
            parameters["properties"][param_name] = param_info
            
            # Add to required list if no default value
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)
        
        # Create tool object
        tool = Tool(
            name=function_name,
            description=tool_description,
            parameters=parameters
        )
        
        return tool
        
    except Exception as e:
        logger.error(f"Error parsing Python function: {e}")
        raise ValueError(f"Failed to parse Python function: {str(e)}")

def parse_openapi_spec(spec_input: Union[Dict[str, Any], str], operation_id: Optional[str] = None) -> Tool:
    """Parse an OpenAPI specification to extract tool metadata."""
    try:
        # Parse the spec if it's a string (YAML or JSON)
        if isinstance(spec_input, str):
            try:
                # Try JSON first
                spec = json.loads(spec_input)
            except json.JSONDecodeError:
                # If not JSON, try YAML
                spec = yaml.safe_load(spec_input)
        else:
            spec = spec_input
        
        # Validate basic OpenAPI structure
        if "openapi" not in spec:
            raise ValueError("Invalid OpenAPI specification: missing 'openapi' field")
        if "paths" not in spec:
            raise ValueError("Invalid OpenAPI specification: missing 'paths' field")
        
        # Find the operation to use
        selected_operation = None
        selected_path = None
        selected_method = None
        selected_operation_id = None
        
        # If operation_id is provided, find the matching operation
        if operation_id:
            for path, path_item in spec["paths"].items():
                for method, operation in path_item.items():
                    if method in ["get", "post", "put", "delete", "patch"] and "operationId" in operation and operation["operationId"] == operation_id:
                        selected_operation = operation
                        selected_path = path
                        selected_method = method
                        selected_operation_id = operation_id
                        break
                if selected_operation:
                    break
        
        # If no operation_id provided or not found, use the first operation
        if not selected_operation:
            for path, path_item in spec["paths"].items():
                for method, operation in path_item.items():
                    if method in ["get", "post", "put", "delete", "patch"]:
                        selected_operation = operation
                        selected_path = path
                        selected_method = method
                        selected_operation_id = operation.get("operationId", f"{method.upper()}_{path.replace('/', '_')}")
                        break
                if selected_operation:
                    break
        
        if not selected_operation:
            raise ValueError("No valid operations found in the OpenAPI specification")
        
        # Extract tool information
        tool_name = selected_operation_id.replace(" ", "")
        # Prefer operation description, fallback to path info description, then info title
        tool_description = (
            selected_operation.get("description") or 
            selected_operation.get("summary") or 
            spec.get("info", {}).get("description") or 
            spec.get("info", {}).get("title") or 
            f"API operation: {selected_method.upper()} {selected_path}"
        )
        
        # Process parameters
        parameters = {"type": "object", "properties": {}, "required": []}
        required_params = []
        
        # Handle path parameters
        if "parameters" in selected_operation:
            for param in selected_operation["parameters"]:
                param_name = param.get("name")
                if not param_name:
                    continue
                
                param_info = {}
                
                # Get parameter type
                if "schema" in param and "type" in param["schema"]:
                    param_info["type"] = param["schema"]["type"]
                else:
                    param_info["type"] = "string"  # Default type
                
                # Get description
                if "description" in param:
                    param_info["description"] = param["description"]
                
                # Get enum values
                if "schema" in param and "enum" in param["schema"]:
                    param_info["enum"] = param["schema"]["enum"]
                
                # Get default value
                if "schema" in param and "default" in param["schema"]:
                    param_info["default"] = param["schema"]["default"]
                
                # Add to properties
                parameters["properties"][param_name] = param_info
                
                # Check if required
                if param.get("required", False):
                    required_params.append(param_name)
        
        # Handle request body parameters for POST/PUT
        if "requestBody" in selected_operation and "content" in selected_operation["requestBody"]:
            content_types = selected_operation["requestBody"]["content"]
            # Try to get JSON schema first
            schema = None
            for content_type in ["application/json", "application/x-www-form-urlencoded"]:
                if content_type in content_types and "schema" in content_types[content_type]:
                    schema = content_types[content_type]["schema"]
                    break
            
            if schema and "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    param_info = {}
                    
                    # Get parameter type
                    if "type" in prop_schema:
                        param_info["type"] = prop_schema["type"]
                    else:
                        param_info["type"] = "string"  # Default type
                    
                    # Get description
                    if "description" in prop_schema:
                        param_info["description"] = prop_schema["description"]
                    
                    # Get enum values
                    if "enum" in prop_schema:
                        param_info["enum"] = prop_schema["enum"]
                    
                    # Get default value
                    if "default" in prop_schema:
                        param_info["default"] = prop_schema["default"]
                    
                    # Add to properties
                    parameters["properties"][prop_name] = param_info
                
                # Add required properties
                if "required" in schema and isinstance(schema["required"], list):
                    required_params.extend(schema["required"])
        
        # Add required parameters to the tool
        if required_params:
            parameters["required"] = required_params
        
        # Create tool object
        tool = Tool(
            name=tool_name,
            description=tool_description,
            parameters=parameters
        )
        
        return tool
        
    except Exception as e:
        logger.error(f"Error parsing OpenAPI spec: {e}")
        raise ValueError(f"Failed to parse OpenAPI specification: {str(e)}")

# API endpoints
@router.get("/", response_model=ToolList)
async def list_tools():
    """List all available tools."""
    tools = load_tools()
    return {"tools": tools}

@router.post("/python-function", response_model=Tool)
async def add_tool_from_python(input_data: PythonFunctionInput = Body(...)):
    """Add a new tool from a Python function."""
    try:
        # Parse the function code to extract tool metadata
        tool = parse_python_function(input_data.function_code)
        
        # Override function name if provided
        if input_data.function_name:
            tool.name = input_data.function_name
        
        # Add to tools list
        tools = load_tools()
        
        # Save the Python function to a file
        os.makedirs(TOOLS_DIR, exist_ok=True)
        function_path = os.path.join(TOOLS_DIR, f"{tool.name}.py")
        try:
            with open(function_path, "w") as f:
                f.write(input_data.function_code)
            logger.info(f"Saved function code to {function_path}")
        except Exception as e:
            logger.error(f"Failed to save function code to file: {e}")
        
        # Check if tool with same name already exists
        for i, existing_tool in enumerate(tools):
            if existing_tool["name"] == tool.name:
                # Replace existing tool
                tools[i] = tool.dict()
                if save_tools(tools):
                    return tool
                else:
                    raise HTTPException(status_code=500, detail="Failed to save updated tool")
        
        # Add new tool
        tools.append(tool.dict())
        if save_tools(tools):
            return tool
        else:
            raise HTTPException(status_code=500, detail="Failed to save new tool")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding tool from Python function: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/openapi-spec", response_model=Tool)
async def add_tool_from_openapi(input_data: OpenAPISpecInput = Body(...)):
    """Add a new tool from an OpenAPI specification."""
    try:
        # Parse the OpenAPI spec to extract tool metadata
        tool = parse_openapi_spec(input_data.spec, input_data.operation_id)
        
        # Add to tools list
        tools = load_tools()
        
        # Check if tool with same name already exists
        for i, existing_tool in enumerate(tools):
            if existing_tool["name"] == tool.name:
                # Replace existing tool
                tools[i] = tool.dict()
                if save_tools(tools):
                    return tool
                else:
                    raise HTTPException(status_code=500, detail="Failed to save updated tool")
        
        # Add new tool
        tools.append(tool.dict())
        if save_tools(tools):
            return tool
        else:
            raise HTTPException(status_code=500, detail="Failed to save new tool")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding tool from OpenAPI spec: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{tool_name}", response_model=DeleteToolResponse)
async def delete_tool(tool_name: str = Path(..., description="The name of the tool to delete")):
    """Delete a tool by name."""
    tools = load_tools()
    
    # Find the tool to delete
    for i, tool in enumerate(tools):
        if tool["name"] == tool_name:
            # Remove the tool
            deleted_tool = tools.pop(i)
            if save_tools(tools):
                return {"message": "Tool deleted successfully", "deleted_tool": tool_name}
            else:
                raise HTTPException(status_code=500, detail="Failed to save tools after deletion")
    
    # Tool not found
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")