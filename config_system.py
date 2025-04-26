import importlib

def construct_object(config):
    """
    Constructs an object based on a configuration dictionary.

    Args:
        config: The configuration data. Can be any type. If it's a dictionary
                with a 'class' key (full Python path), it attempts to load and
                instantiate/call the specified Python object.

    Returns:
        The constructed object or the original config if it's not a
        valid construction dictionary.
    """
    if isinstance(config, list):
        return [construct_object(arg) for arg in config]
    elif isinstance(config, dict):
        config = {k: construct_object(v) for k, v in config.items()}
    
        if "class" in config and isinstance(config["class"], str):
            try:
                # Split path into module and attribute components
                path_parts = config["class"].split('.')
                if len(path_parts) < 2:
                    raise ValueError(f"Path must contain at least module and attribute: {config['class']}")
                
                module_name, *attr_path = path_parts
                module = importlib.import_module(module_name)
                
                # Traverse nested attributes if needed
                target = module
                for attr in attr_path:
                    target = getattr(target, attr)
                
                # Handle parameters if provided
                parameters = config.get("parameters", {})
                if isinstance(parameters, list):
                    return target(*parameters)
                elif isinstance(parameters, dict):
                    return target(**parameters)
                else:
                    return target(parameters)
            except ImportError:
                raise ImportError(f"Error: could not import module: {module_name}")
            except Exception as e:
                raise RuntimeError(f"Error constructing object from config {config}: {e}")
    else: 
        return config
