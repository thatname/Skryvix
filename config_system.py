import importlib

def construct_object(config):
    """
    Constructs an object based on a configuration dictionary.

    Args:
        config: The configuration data. Can be any type. If it's a dictionary
                with specific keys ('module', 'class'/'func', 'parameters'),
                it attempts to dynamically load and instantiate/call the
                specified Python object.

    Returns:
        The constructed object or the original config if it's not a
        valid construction dictionary.
    """
    if not isinstance(config, dict):
        return config

    if "module" in config and isinstance(config["module"], str):
        try:
            module_name = config["module"]
            module = importlib.import_module(module_name)

            target = None
            if "func" in config and isinstance(config["func"], str):
                func_name = config["func"]
                target = getattr(module, func_name)
            elif "class" in config and isinstance(config["class"], str):
                class_name = config["class"]
                target = getattr(module, class_name)
            else:
                raise ValueError(f"Config with module '{module_name}' must specify 'class' or 'func'")

            parameters = config.get("parameters", {})
            processed_args = []
            processed_kwargs = {}

            if isinstance(parameters, list):
                processed_args = [construct_object(arg) for arg in parameters]
                return target(*processed_args)
            elif isinstance(parameters, dict):
                processed_kwargs = {k: construct_object(v) for k, v in parameters.items()}
                return target(**processed_kwargs)
            elif not parameters:
                return target()
            else:
                raise TypeError(f"Parameters for {module_name}.{config.get('func') or config.get('class')} must be a list or dict, got {type(parameters)}")

        except ImportError:
            raise ImportError(f"Could not import module: {config['module']}")
        except AttributeError:
            target_name = config.get("func") or config.get("class")
            raise AttributeError(f"Could not find '{target_name}' in module '{config['module']}'")
        except Exception as e:
            raise RuntimeError(f"Error constructing object from config {config}: {e}")

    return config
