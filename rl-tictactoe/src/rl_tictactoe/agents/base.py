"""Base class and protocol for Tic-Tac-Toe agents."""

from typing import Protocol, List
import numpy.typing as npt
import numpy as np


class Agent(Protocol):
    """Protocol for Tic-Tac-Toe agents."""
    
    def select_action(
        self, state: npt.NDArray[np.int_], legal_actions: List[int]
    ) -> int:
        """
        Select an action given the current state and legal actions.
        
        Args:
            state: Current board state (9-element array)
            legal_actions: List of legal action indices
            
        Returns:
            Selected action index (0-8)
        """
        ...
    
    def reset(self) -> None:
        """
        Reset agent state (if any) at the start of a new episode.
        
        Optional for stateless agents.
        """
        ...
