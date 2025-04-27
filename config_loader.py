import importlib
import os
import yaml

_loaded_objects = {}
def do_load_from_yaml(path):
    with open(path) as f:
        return yaml.unsafe_load(f)

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
    
    obj = do_load_from_yaml(path)
    _loaded_objects[name] = obj
    return obj