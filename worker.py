from abc import ABC, abstractmethod
import importlib
import yaml

class Worker(ABC):
    """
    Abstract base class for workers that defines the basic worker interface.
    """
    
    @abstractmethod
    def start(self, task, workspace):
        """
        Start the worker to process a task.
        
        Args:
            task: The task to be processed
            workspace: The workspace for processing
        """
        pass
    
    @abstractmethod
    async def stop(self):
        """
        Stop the worker.
        """
        pass
        
    @classmethod
    def create(cls, yaml_config):
        """
        Create a Worker instance from YAML configuration.
        
        Args:
            yaml_config: YAML configuration string or dict containing:
                - class: Full path to the class (e.g., "mypackage.mymodule.MyWorker")
                - params: List of constructor parameters
                
        Returns:
            Worker: Created Worker instance
        
        Example:
            yaml_config = '''
            class: mypackage.workers.CustomWorker
            params:
              - param1_value
              - param2_value
            '''
            worker = Worker.create(yaml_config)
        """
        # Parse YAML if input is string
        if isinstance(yaml_config, str):
            config = yaml.safe_load(yaml_config)
        else:
            config = yaml_config
            
        # Get class path and parameters
        class_path = config['class']
        params = config.get('params', [])
        
        # Parse module and class name
        module_path, class_name = class_path.rsplit('.', 1)
        
        try:
            # Dynamically import module
            module = importlib.import_module(module_path)
            # Get class object
            worker_class = getattr(module, class_name)
            
            # Ensure class is a Worker subclass
            if not issubclass(worker_class, Worker):
                raise ValueError(f"{class_path} is not a subclass of Worker")
            
            # Create instance
            return worker_class(*params)
            
        except ImportError:
            raise ImportError(f"Could not import module {module_path}")
        except AttributeError:
            raise AttributeError(f"Class {class_name} does not exist in module {module_path}")