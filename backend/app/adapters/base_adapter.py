from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the enterprise service."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check connection health."""
        pass

    @abstractmethod
    def execute(self, action: str, **kwargs) -> any:
        """Execute a generic command/action."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the service."""
        pass
