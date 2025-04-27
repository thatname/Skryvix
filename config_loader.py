import os
import yaml
from jinja2 import Environment, FileSystemLoader, Template
import json
from typing import Any, Dict, Optional, Union

class ConfigLoadError(Exception):
    """Base exception for configuration loading errors."""
    pass

class UnsupportedFormatError(ConfigLoadError):
    """Exception raised when file format is not supported."""
    pass

class TemplateRenderError(ConfigLoadError):
    """Exception raised when template rendering fails."""
    pass

# Global cache for loaded objects
_loaded_objects = {}

def do_load_yaml(path: str) -> Any:
    """
    Load and parse a YAML file.
    
    Args:
        path: Path to the YAML file
        
    Returns:
        Dict containing the parsed YAML content
        
    Raises:
        ConfigLoadError: If YAML parsing fails
    """
    try:
        with open(path) as f:
            return yaml.unsafe_load(f)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"Failed to parse YAML file {path}: {str(e)}")
    except IOError as e:
        raise ConfigLoadError(f"Failed to read file {path}: {str(e)}")

def do_load_json(path: str) -> Any:
    """
    Load and parse a JSON file.
    
    Args:
        path: Path to the JSON file
        
    Returns:
        Dict containing the parsed JSON content
        
    Raises:
        ConfigLoadError: If JSON parsing fails
    """
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigLoadError(f"Failed to parse JSON file {path}: {str(e)}")
    except IOError as e:
        raise ConfigLoadError(f"Failed to read file {path}: {str(e)}")

def do_load_j2(path: str) -> Template:
    """
    Load a Jinja2 template file.
    
    Args:
        path: Path to the Jinja2 template file
        
    Returns:
        Jinja2 Template object
        
    Raises:
        TemplateRenderError: If template loading fails
    """
    try:
        # Setup Jinja2 environment with the template's directory as root
        template_dir = os.path.dirname(path)
        env = Environment(loader=FileSystemLoader(template_dir))
        
        # Load template
        template_name = os.path.basename(path)
        return env.get_template(template_name)
            
    except Exception as e:
        raise TemplateRenderError(f"Failed to load template {path}: {str(e)}")

def load_from_file(
    path: str, 
    name: Optional[str] = None, 
    force_reload: bool = False
):
    """
    Load configuration from a file, supporting multiple formats.
    
    Args:
        path: Path to the configuration file
        name: Optional name to use as key in cache. If None, uses filename.
        force_reload: If True, ignore cached version and reload from file
        **kwargs: Additional arguments (unused)
        
    Returns:
        For YAML/JSON files: Dict containing the loaded configuration
        For Jinja2 templates: Jinja2 Template object
        
    Raises:
        UnsupportedFormatError: If file format is not supported
        ConfigLoadError: If loading or parsing fails
    """
    if name is None:
        name = os.path.basename(path)
    
    # Return cached version if available and force_reload is False
    if not force_reload and name in _loaded_objects:
        return _loaded_objects[name]
    
    # Determine file format and load accordingly
    _, ext = os.path.splitext(path.lower())
    
    try:
        if ext == '.json':
            obj = do_load_json(path)
        elif ext == '.j2':
            obj = do_load_j2(path)
        else:
            obj = do_load_yaml(path)
        
        # Cache the loaded object
        _loaded_objects[name] = obj
        return obj
        
    except (ConfigLoadError, UnsupportedFormatError) as e:
        # Re-raise these exceptions as they're already properly formatted
        raise
    except Exception as e:
        # Wrap any other exceptions in ConfigLoadError
        raise ConfigLoadError(f"Unexpected error loading {path}: {str(e)}")
