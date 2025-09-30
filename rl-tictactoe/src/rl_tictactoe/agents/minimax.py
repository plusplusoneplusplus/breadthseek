"""Minimax agent for perfect play."""

from typing import List, Tuple, Dict
import numpy as np
import numpy.typing as npt


class MinimaxAgent:
    """
    Agent that uses minimax algorithm for optimal play.
    
    This agent will never lose and will win whenever possible.
    Useful as an oracle for evaluating other agents.
    
    Uses memoization to cache state evaluations for performance.
    Complexity: O(b^d) where b=branching factor (~5 avg), d=depth (~9 max)
    With memoization: O(unique states) ≈ O(3^9) = 19,683 states max
    """
    
    def __init__(self, player: int = 1) -> None:
        """
        Initialize the minimax agent.
        
        Args:
            player: Which player this agent is (1 for X, -1 for O)
        """
        self.player = player
        self.opponent = -player
        self.memo: Dict[str, float] = {}  # Cache for state evaluations
    
    def select_action(
        self, state: npt.NDArray[np.int_], legal_actions: List[int]
    ) -> int:
        """
        Select optimal action using minimax algorithm.
        
        Args:
            state: Current board state (9-element array)
            legal_actions: List of legal action indices
            
        Returns:
            Optimal action
        """
        if not legal_actions:
            raise ValueError("No legal actions available")
        
        best_action = legal_actions[0]
        best_value = float('-inf')
        
        for action in legal_actions:
            # Simulate the move
            next_state = state.copy()
            next_state[action] = self.player
            
            # Evaluate using minimax
            value = self._minimax(next_state, False)
            
            if value > best_value:
                best_value = value
                best_action = action
        
        return best_action
    
    def _minimax(self, state: npt.NDArray[np.int_], is_maximizing: bool) -> float:
        """
        Minimax algorithm with recursive evaluation and memoization.
        
        Args:
            state: Current board state
            is_maximizing: True if maximizing player's turn, False otherwise
            
        Returns:
            Value of the state from the current player's perspective
        """
        # Create cache key from state
        state_key = "".join(str(x) for x in state) + str(int(is_maximizing))
        if state_key in self.memo:
            return self.memo[state_key]
        
        # Check terminal conditions
        winner = self._check_winner(state)
        if winner is not None:
            if winner == self.player:
                result = 1.0
            elif winner == self.opponent:
                result = -1.0
            else:  # Draw
                result = 0.0
            self.memo[state_key] = result
            return result
        
        # Get legal actions
        legal_actions = [i for i in range(9) if state[i] == 0]
        
        if not legal_actions:
            self.memo[state_key] = 0.0
            return 0.0  # Draw
        
        if is_maximizing:
            max_value = float('-inf')
            for action in legal_actions:
                next_state = state.copy()
                next_state[action] = self.player
                value = self._minimax(next_state, False)
                max_value = max(max_value, value)
            self.memo[state_key] = max_value
            return max_value
        else:
            min_value = float('inf')
            for action in legal_actions:
                next_state = state.copy()
                next_state[action] = self.opponent
                value = self._minimax(next_state, True)
                min_value = min(min_value, value)
            self.memo[state_key] = min_value
            return min_value
    
    def _check_winner(self, state: npt.NDArray[np.int_]) -> int | None:
        """
        Check if there's a winner.
        
        Args:
            state: Board state
            
        Returns:
            Winner (1 or -1), 0 for draw, None if game not finished
        """
        board_2d = state.reshape(3, 3)
        
        # Check rows
        for row in range(3):
            if abs(board_2d[row, :].sum()) == 3:
                return int(board_2d[row, 0])
        
        # Check columns
        for col in range(3):
            if abs(board_2d[:, col].sum()) == 3:
                return int(board_2d[0, col])
        
        # Check diagonals
        if abs(np.diag(board_2d).sum()) == 3:
            return int(board_2d[0, 0])
        if abs(np.diag(np.fliplr(board_2d)).sum()) == 3:
            return int(board_2d[0, 2])
        
        # Check if board is full (draw)
        if not np.any(state == 0):
            return 0
        
        return None
    
    def reset(self) -> None:
        """Reset agent state and clear memoization cache."""
        self.memo.clear()
