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
    def stop(self):
        """
        Stop the worker.
        """
        pass