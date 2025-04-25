
from abc import ABC, abstractmethod

class Tool(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    async def __call__(self, args: str):
        """
        Execute the tool asynchronously
        
        Args:
            args (str): Arguments for the tool
            
        Yields:
            str: Output from the tool execution
        """
        pass