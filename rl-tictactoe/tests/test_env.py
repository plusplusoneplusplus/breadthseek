"""Comprehensive tests for TicTacToeEnv."""

import numpy as np
import pytest
from rl_tictactoe.env import TicTacToeEnv


class TestTicTacToeEnvBasics:
    """Test basic environment functionality."""
    
    def test_initialization(self) -> None:
        """Test that environment initializes correctly."""
        env = TicTacToeEnv()
        assert env.board.shape == (9,)
        assert np.all(env.board == 0)
        assert env.current_player == 1
        assert not env.done
        assert env.winner is None
    
    def test_reset(self) -> None:
        """Test that reset returns environment to initial state."""
        env = TicTacToeEnv()
        
        # Make some moves
        env.step(0)
        env.step(1)
        
        # Reset
        state = env.reset()
        
        assert np.all(state == 0)
        assert env.current_player == 1
        assert not env.done
        assert env.winner is None
    
    def test_reset_returns_copy(self) -> None:
        """Test that reset returns a copy of the state."""
        env = TicTacToeEnv()
        state = env.reset()
        state[0] = 1  # Modify returned state
        assert env.board[0] == 0  # Internal state unchanged


class TestWinDetection:
    """Test win detection for all possible winning configurations."""
    
    def test_row_wins(self) -> None:
        """Test detection of row wins."""
        env = TicTacToeEnv()
        
        # Row 0: X X X
        env.reset()
        env.step(0)  # X
        env.step(3)  # O
        env.step(1)  # X
        env.step(4)  # O
        _, reward, done, info = env.step(2)  # X wins
        
        assert done
        assert reward == 1.0
        assert info["winner"] == 1
        
    def test_column_wins(self) -> None:
        """Test detection of column wins."""
        env = TicTacToeEnv()
        
        # Column 0: X
        #           X
        #           X
        env.reset()
        env.step(0)  # X
        env.step(1)  # O
        env.step(3)  # X
        env.step(2)  # O
        _, reward, done, info = env.step(6)  # X wins
        
        assert done
        assert reward == 1.0
        assert info["winner"] == 1
    
    def test_diagonal_wins(self) -> None:
        """Test detection of diagonal wins."""
        env = TicTacToeEnv()
        
        # Main diagonal: X . .
        #                . X .
        #                . . X
        env.reset()
        env.step(0)  # X
        env.step(1)  # O
        env.step(4)  # X
        env.step(2)  # O
        _, reward, done, info = env.step(8)  # X wins
        
        assert done
        assert reward == 1.0
        assert info["winner"] == 1
    
    def test_anti_diagonal_wins(self) -> None:
        """Test detection of anti-diagonal wins."""
        env = TicTacToeEnv()
        
        # Anti-diagonal: . . X
        #                . X .
        #                X . .
        env.reset()
        env.step(2)  # X
        env.step(0)  # O
        env.step(4)  # X
        env.step(1)  # O
        _, reward, done, info = env.step(6)  # X wins
        
        assert done
        assert reward == 1.0
        assert info["winner"] == 1
    
    def test_player_2_wins(self) -> None:
        """Test that player 2 (O) can win and receives correct reward."""
        env = TicTacToeEnv()
        
        # O wins in row 0
        env.step(3)  # X
        env.step(0)  # O
        env.step(4)  # X
        env.step(1)  # O
        env.step(7)  # X
        _, reward, done, info = env.step(2)  # O wins
        
        assert done
        assert reward == -1.0  # From player 1's perspective
        assert info["winner"] == -1
    
    def test_all_winning_lines(self) -> None:
        """Test all 8 possible winning lines."""
        winning_positions = [
            [0, 1, 2],  # Row 0
            [3, 4, 5],  # Row 1
            [6, 7, 8],  # Row 2
            [0, 3, 6],  # Col 0
            [1, 4, 7],  # Col 1
            [2, 5, 8],  # Col 2
            [0, 4, 8],  # Main diagonal
            [2, 4, 6],  # Anti-diagonal
        ]
        
        for positions in winning_positions:
            env = TicTacToeEnv()
            # Player 1 occupies winning positions, Player 2 plays elsewhere
            blocking_positions = [p for p in range(9) if p not in positions]
            
            for i, pos in enumerate(positions[:-1]):
                env.step(pos)  # X
                # Player 2 plays in blocking positions
                if i < len(blocking_positions):
                    env.step(blocking_positions[i])  # O
            
            # Final winning move
            _, reward, done, info = env.step(positions[-1])
            assert done, f"Failed to detect win for positions {positions}"
            assert reward == 1.0
            assert info["winner"] == 1


class TestDrawDetection:
    """Test draw detection."""
    
    def test_draw_game(self) -> None:
        """Test that draw is correctly detected."""
        env = TicTacToeEnv()
        
        # Create a draw:
        # X X O
        # O O X
        # X O X
        moves = [0, 2, 1, 3, 5, 4, 6, 7, 8]
        
        for i, move in enumerate(moves[:-1]):
            _, reward, done, _ = env.step(move)
            assert not done, f"Game ended prematurely at move {i}"
            assert reward == 0.0
        
        # Last move creates draw
        _, reward, done, info = env.step(moves[-1])
        assert done
        assert reward == 0.0
        assert info.get("draw", False)
    
    def test_is_terminal_on_draw(self) -> None:
        """Test is_terminal returns True for draw."""
        env = TicTacToeEnv()
        
        # Full board with no winner
        draw_board = np.array([1, -1, 1, -1, 1, -1, -1, 1, -1])
        assert env.is_terminal(draw_board)


class TestLegalActions:
    """Test legal action detection."""
    
    def test_legal_actions_initial_state(self) -> None:
        """Test that all actions are legal initially."""
        env = TicTacToeEnv()
        legal = env.legal_actions()
        assert legal == list(range(9))
    
    def test_legal_actions_after_moves(self) -> None:
        """Test that legal actions update correctly after moves."""
        env = TicTacToeEnv()
        
        env.step(0)  # X at position 0
        legal = env.legal_actions()
        assert 0 not in legal
        assert len(legal) == 8
        
        env.step(4)  # O at position 4
        legal = env.legal_actions()
        assert 0 not in legal
        assert 4 not in legal
        assert len(legal) == 7
    
    def test_legal_actions_with_custom_state(self) -> None:
        """Test legal_actions with a provided state."""
        env = TicTacToeEnv()
        custom_state = np.array([1, 0, -1, 0, 1, 0, 0, 0, -1])
        legal = env.legal_actions(custom_state)
        expected = [1, 3, 5, 6, 7]
        assert legal == expected
    
    def test_no_legal_actions_on_full_board(self) -> None:
        """Test that no actions are legal on a full board."""
        env = TicTacToeEnv()
        full_board = np.array([1, -1, 1, -1, 1, -1, -1, 1, -1])
        legal = env.legal_actions(full_board)
        assert legal == []


class TestInvalidMoves:
    """Test handling of invalid moves."""
    
    def test_invalid_move_occupied_square(self) -> None:
        """Test that playing on occupied square is invalid."""
        env = TicTacToeEnv()
        
        env.step(0)  # X at position 0
        _, reward, done, info = env.step(0)  # Try to play at 0 again
        
        assert done
        assert reward == -10.0
        assert info["invalid_move"]
        assert info["reason"] == "occupied"
    
    def test_invalid_move_out_of_bounds(self) -> None:
        """Test that out of bounds actions are invalid."""
        env = TicTacToeEnv()
        
        _, reward, done, info = env.step(9)  # Invalid position
        assert done
        assert reward == -10.0
        assert info["invalid_move"]
        assert info["reason"] == "out_of_bounds"
        
        env.reset()
        _, reward, done, info = env.step(-1)  # Invalid position
        assert done
        assert reward == -10.0
        assert info["invalid_move"]
    
    def test_step_after_done_raises_error(self) -> None:
        """Test that stepping after game is done raises an error."""
        env = TicTacToeEnv()
        
        # Create a quick win
        env.step(0)
        env.step(3)
        env.step(1)
        env.step(4)
        env.step(2)  # X wins
        
        # Try to step again
        with pytest.raises(ValueError, match="Episode has already terminated"):
            env.step(5)


class TestIsTerminal:
    """Test is_terminal method."""
    
    def test_is_terminal_initial_state(self) -> None:
        """Test that initial state is not terminal."""
        env = TicTacToeEnv()
        assert not env.is_terminal()
    
    def test_is_terminal_mid_game(self) -> None:
        """Test that mid-game state is not terminal."""
        env = TicTacToeEnv()
        env.step(0)
        env.step(1)
        assert not env.is_terminal()
    
    def test_is_terminal_on_win(self) -> None:
        """Test that winning state is terminal."""
        env = TicTacToeEnv()
        win_state = np.array([1, 1, 1, 0, 0, 0, 0, 0, 0])
        assert env.is_terminal(win_state)
    
    def test_is_terminal_on_draw(self) -> None:
        """Test that draw state is terminal."""
        env = TicTacToeEnv()
        draw_state = np.array([1, -1, 1, -1, 1, -1, -1, 1, -1])
        assert env.is_terminal(draw_state)


class TestUtilityMethods:
    """Test utility methods like render and get_state_key."""
    
    def test_render_initial_state(self) -> None:
        """Test rendering of initial state."""
        env = TicTacToeEnv()
        output = env.render()
        assert "." in output
        assert "X" not in output
        assert "O" not in output
    
    def test_render_with_pieces(self) -> None:
        """Test rendering with X and O on board."""
        env = TicTacToeEnv()
        env.step(0)  # X
        env.step(4)  # O
        output = env.render()
        assert "X" in output
        assert "O" in output
    
    def test_get_state_key(self) -> None:
        """Test state key generation."""
        env = TicTacToeEnv()
        key1 = env.get_state_key()
        assert key1 == "000000000"
        
        env.step(0)
        key2 = env.get_state_key()
        assert key2 == "100000000"
        
        env.step(4)
        key3 = env.get_state_key()
        assert "1" in key3 and "-1" in key3
    
    def test_get_state_key_with_custom_state(self) -> None:
        """Test state key with custom state."""
        env = TicTacToeEnv()
        custom_state = np.array([1, 0, -1, 0, 1, 0, 0, 0, -1])
        key = env.get_state_key(custom_state)
        assert key == "10-101000-1"  # Note: -1 appears as -1


class TestPlayerAlternation:
    """Test that players alternate correctly."""
    
    def test_player_alternation(self) -> None:
        """Test that current_player alternates between moves."""
        env = TicTacToeEnv()
        
        assert env.current_player == 1
        env.step(0)
        assert env.current_player == -1
        env.step(1)
        assert env.current_player == 1
        env.step(2)
        assert env.current_player == -1
    
    def test_player_alternation_stops_on_win(self) -> None:
        """Test that player doesn't change after game ends."""
        env = TicTacToeEnv()
        
        # Quick win for player 1
        env.step(0)  # X
        env.step(3)  # O
        env.step(1)  # X
        env.step(4)  # O
        env.step(2)  # X wins
        
        # Player should still be 1 (the winner)
        assert env.current_player == 1


class TestStepReturnValues:
    """Test that step returns correct values."""
    
    def test_step_returns_copy_of_state(self) -> None:
        """Test that step returns a copy, not reference to internal state."""
        env = TicTacToeEnv()
        state, _, _, _ = env.step(0)
        
        # Modify returned state
        state[1] = 999
        
        # Internal state should be unchanged
        assert env.board[1] == 0
    
    def test_step_return_types(self) -> None:
        """Test that step returns correct types."""
        env = TicTacToeEnv()
        state, reward, done, info = env.step(0)
        
        assert isinstance(state, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(info, dict)
