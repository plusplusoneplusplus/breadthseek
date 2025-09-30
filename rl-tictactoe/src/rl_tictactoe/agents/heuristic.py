"""Heuristic agent using simple rule-based strategy."""

from typing import List
import numpy as np
import numpy.typing as npt


class HeuristicAgent:
    """
    Agent that uses simple heuristics for action selection.
    
    Priority order:
    1. Win if possible (complete three in a row)
    2. Block opponent from winning
    3. Take center if available
    4. Take corner if available
    5. Take side (edge) position
    
    This agent plays defensively and tries to control key positions.
    """
    
    def __init__(self, player: int = 1) -> None:
        """
        Initialize the heuristic agent.
        
        Args:
            player: Which player this agent is (1 for X, -1 for O)
        """
        self.player = player
        self.opponent = -player
    
    def select_action(
        self, state: npt.NDArray[np.int_], legal_actions: List[int]
    ) -> int:
        """
        Select action using heuristic rules.
        
        Args:
            state: Current board state (9-element array)
            legal_actions: List of legal action indices
            
        Returns:
            Selected action based on heuristics
        """
        if not legal_actions:
            raise ValueError("No legal actions available")
        
        # 1. Check if we can win
        winning_move = self._find_winning_move(state, self.player, legal_actions)
        if winning_move is not None:
            return winning_move
        
        # 2. Block opponent from winning
        blocking_move = self._find_winning_move(state, self.opponent, legal_actions)
        if blocking_move is not None:
            return blocking_move
        
        # 3. Take center (position 4)
        if 4 in legal_actions:
            return 4
        
        # 4. Take corners (positions 0, 2, 6, 8)
        corners = [pos for pos in [0, 2, 6, 8] if pos in legal_actions]
        if corners:
            return corners[0]
        
        # 5. Take any remaining side position
        return legal_actions[0]
    
    def _find_winning_move(
        self, state: npt.NDArray[np.int_], player: int, legal_actions: List[int]
    ) -> int | None:
        """
        Find a move that would complete three in a row for the player.
        
        Args:
            state: Current board state
            player: Player to check (1 or -1)
            legal_actions: List of legal actions
            
        Returns:
            Action that wins, or None if no winning move exists
        """
        # All possible winning lines: rows, columns, diagonals
        winning_lines = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6],              # Diagonals
        ]
        
        for line in winning_lines:
            line_values = [state[pos] for pos in line]
            
            # Check if player has 2 in this line and the third is empty
            if line_values.count(player) == 2 and line_values.count(0) == 1:
                # Find the empty position
                for pos in line:
                    if state[pos] == 0 and pos in legal_actions:
                        return pos
        
        return None
    
    def reset(self) -> None:
        """Reset agent state (no-op for stateless agent)."""
        pass
