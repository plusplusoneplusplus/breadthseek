"""Tic-Tac-Toe environment following Gymnasium-style API."""

from typing import Tuple, List, Optional, Dict, Any
import numpy as np
import numpy.typing as npt


class TicTacToeEnv:
    """
    Tic-Tac-Toe environment for Reinforcement Learning.
    
    State representation:
        - 3x3 board (or flattened 9-element array)
        - 0 = empty, 1 = player 1 (X), -1 = player 2 (O)
    
    Action space:
        - Integer 0-8 representing board position (row-major order)
        - 0 1 2
          3 4 5
          6 7 8
    
    Rewards:
        - +1 for win
        - -1 for loss
        - 0 for draw
        - -10 for invalid move (and episode terminates)
    """
    
    def __init__(self) -> None:
        """Initialize the Tic-Tac-Toe environment."""
        self.board: npt.NDArray[np.int_] = np.zeros(9, dtype=np.int_)
        self.current_player: int = 1  # 1 for X, -1 for O
        self.done: bool = False
        self.winner: Optional[int] = None
        
    def reset(self) -> npt.NDArray[np.int_]:
        """
        Reset the environment to initial state.
        
        Returns:
            Initial board state (9-element array of zeros)
        """
        self.board = np.zeros(9, dtype=np.int_)
        self.current_player = 1
        self.done = False
        self.winner = None
        return self.board.copy()
    
    def step(
        self, action: int
    ) -> Tuple[npt.NDArray[np.int_], float, bool, Dict[str, Any]]:
        """
        Execute one step in the environment.
        
        Args:
            action: Board position (0-8) to place current player's mark
            
        Returns:
            Tuple of (next_state, reward, done, info)
            - next_state: Updated board state
            - reward: Reward for the action (+1 win, -1 loss, 0 draw, -10 invalid)
            - done: Whether episode has terminated
            - info: Additional information dict
        """
        if self.done:
            raise ValueError("Episode has already terminated. Call reset() first.")
        
        # Check for invalid move
        if action < 0 or action > 8:
            self.done = True
            return self.board.copy(), -10.0, True, {"invalid_move": True, "reason": "out_of_bounds"}
        
        if self.board[action] != 0:
            self.done = True
            return self.board.copy(), -10.0, True, {"invalid_move": True, "reason": "occupied"}
        
        # Make the move
        self.board[action] = self.current_player
        
        # Check if current player won
        if self._check_win(self.current_player):
            self.done = True
            self.winner = self.current_player
            reward = 1.0 if self.current_player == 1 else -1.0
            return self.board.copy(), reward, True, {"winner": self.current_player}
        
        # Check for draw
        if self.is_terminal(self.board):
            self.done = True
            return self.board.copy(), 0.0, True, {"draw": True}
        
        # Game continues, switch player
        self.current_player *= -1
        return self.board.copy(), 0.0, False, {}
    
    def legal_actions(self, state: Optional[npt.NDArray[np.int_]] = None) -> List[int]:
        """
        Get list of legal actions for a given state.
        
        Args:
            state: Board state (if None, uses current board)
            
        Returns:
            List of legal action indices (empty positions)
        """
        if state is None:
            state = self.board
        return [i for i in range(9) if state[i] == 0]
    
    def is_terminal(self, state: Optional[npt.NDArray[np.int_]] = None) -> bool:
        """
        Check if a state is terminal (game over).
        
        Args:
            state: Board state (if None, uses current board)
            
        Returns:
            True if game is over (win or draw), False otherwise
        """
        if state is None:
            state = self.board
            
        # Check for wins
        if self._check_win(1, state) or self._check_win(-1, state):
            return True
        
        # Check for draw (no empty spaces)
        return not np.any(state == 0)
    
    def _check_win(self, player: int, state: Optional[npt.NDArray[np.int_]] = None) -> bool:
        """
        Check if a player has won.
        
        Args:
            player: Player to check (1 or -1)
            state: Board state (if None, uses current board)
            
        Returns:
            True if player has won, False otherwise
        """
        if state is None:
            state = self.board
            
        board_2d = state.reshape(3, 3)
        
        # Check rows
        for row in range(3):
            if np.all(board_2d[row, :] == player):
                return True
        
        # Check columns
        for col in range(3):
            if np.all(board_2d[:, col] == player):
                return True
        
        # Check diagonals
        if np.all(np.diag(board_2d) == player):
            return True
        if np.all(np.diag(np.fliplr(board_2d)) == player):
            return True
        
        return False
    
    def render(self) -> str:
        """
        Render the current board state as a string.
        
        Returns:
            String representation of the board
        """
        symbols = {0: ".", 1: "X", -1: "O"}
        board_2d = self.board.reshape(3, 3)
        
        lines = []
        lines.append("  0 1 2")
        for i, row in enumerate(board_2d):
            line = f"{i} " + " ".join(symbols[cell] for cell in row)
            lines.append(line)
        
        return "\n".join(lines)
    
    def get_state_key(self, state: Optional[npt.NDArray[np.int_]] = None) -> str:
        """
        Convert state to a hashable key for Q-table.
        
        Args:
            state: Board state (if None, uses current board)
            
        Returns:
            String representation of the state
        """
        if state is None:
            state = self.board
        return "".join(str(x) for x in state)
