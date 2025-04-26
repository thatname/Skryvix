import importlib
import os
import yaml

_loaded_objects = {}

def load_from_yaml(path, name=None):
    """
    Load configuration from a YAML file.
    
    Args:
        path: Path to the YAML file
        name: Optional name to use as key in cache. If None, uses filename.
    
    Returns:
        The loaded and constructed object
    """
    if name is None:
        name = os.path.basename(path)
    
    if name in _loaded_objects:
        return _loaded_objects[name]
        
    with open(path) as f:
        config = yaml.safe_load(f)
    
    obj = load_object(config)
    _loaded_objects[name] = obj
    return obj

def load_object(config):
    """
    Constructs an object based on a configuration dictionary.

    Args:
        config: The configuration data. Can be any type. If it's a dictionary
                with a 'path' key (full Python path), it attempts to load and
                instantiate/call the specified Python object.

    Returns:
        The constructed object or the original config if it's not a
        valid construction dictionary.
    """
    if isinstance(config, list):
        return [load_object(arg) for arg in config]
    elif isinstance(config, dict):
        config = {k: load_object(v) for k, v in config.items()}
    
        if "path" in config and "args" in config and isinstance(config["path"], str):
            try:
                # Split path into module and attribute components
                path_parts = config["path"].split('.')
                if len(path_parts) < 2:
                    raise ValueError(f"Path must contain at least module and attribute: {config['path']}")
                
                module_name, *attr_path = path_parts
                module = importlib.import_module(module_name)
                
                # Traverse nested attribute if needed
                target = module
                for attr in attr_path:
                    target = getattr(target, attr)
                
                # Handle parameter if provided
                parameter = config.get("args", {})
                if isinstance(parameter, list):
                    return target(*parameter)
                elif isinstance(parameter, dict):
                    return target(**parameter)
                else:
                    return target(parameter)
            except ImportError:
                raise ImportError(f"Error: could not import module: {module_name}")
            except Exception as e:
                raise RuntimeError(f"Error constructing object from config {config}: {e}")
    else:
        return config
