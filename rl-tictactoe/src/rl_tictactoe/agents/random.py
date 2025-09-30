"""Random agent that plays uniformly at random among legal actions."""

from typing import List
import numpy as np
import numpy.typing as npt


class RandomAgent:
    """Agent that selects actions uniformly at random from legal actions."""
    
    def __init__(self, seed: int | None = None) -> None:
        """
        Initialize the random agent.
        
        Args:
            seed: Random seed for reproducibility (optional)
        """
        self.rng = np.random.default_rng(seed)
    
    def select_action(
        self, state: npt.NDArray[np.int_], legal_actions: List[int]
    ) -> int:
        """
        Select a random legal action.
        
        Args:
            state: Current board state (not used by random agent)
            legal_actions: List of legal action indices
            
        Returns:
            Randomly selected action from legal_actions
        """
        if not legal_actions:
            raise ValueError("No legal actions available")
        return int(self.rng.choice(legal_actions))
    
    def reset(self) -> None:
        """Reset agent state (no-op for stateless agent)."""
        pass
