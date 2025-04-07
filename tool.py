
from abc import ABC, abstractmethod

class Tool(ABC):
    
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def use(self, args: str) -> str:
        pass