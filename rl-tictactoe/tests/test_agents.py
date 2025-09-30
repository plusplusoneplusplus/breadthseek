"""Tests for agent implementations."""

import numpy as np
import pytest
from rl_tictactoe.agents.random import RandomAgent
from rl_tictactoe.agents.heuristic import HeuristicAgent
from rl_tictactoe.agents.minimax import MinimaxAgent
from rl_tictactoe.env import TicTacToeEnv


class TestRandomAgent:
    """Test RandomAgent."""
    
    def test_initialization(self) -> None:
        """Test that RandomAgent initializes correctly."""
        agent = RandomAgent()
        assert agent is not None
    
    def test_seeded_reproducibility(self) -> None:
        """Test that seeded agents produce same actions."""
        state = np.zeros(9, dtype=np.int_)
        legal_actions = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        
        agent1 = RandomAgent(seed=42)
        agent2 = RandomAgent(seed=42)
        
        # Same seed should produce same sequence
        actions1 = [agent1.select_action(state, legal_actions) for _ in range(10)]
        actions2 = [agent2.select_action(state, legal_actions) for _ in range(10)]
        
        assert actions1 == actions2
    
    def test_selects_from_legal_actions(self) -> None:
        """Test that RandomAgent only selects legal actions."""
        state = np.array([1, 0, -1, 0, 1, 0, 0, 0, -1])
        legal_actions = [1, 3, 5, 6, 7]
        
        agent = RandomAgent(seed=42)
        
        for _ in range(50):
            action = agent.select_action(state, legal_actions)
            assert action in legal_actions
    
    def test_raises_on_no_legal_actions(self) -> None:
        """Test that RandomAgent raises error when no legal actions."""
        state = np.zeros(9, dtype=np.int_)
        agent = RandomAgent()
        
        with pytest.raises(ValueError, match="No legal actions"):
            agent.select_action(state, [])
    
    def test_reset(self) -> None:
        """Test that reset doesn't break agent."""
        agent = RandomAgent()
        agent.reset()
        
        state = np.zeros(9, dtype=np.int_)
        action = agent.select_action(state, [0, 1, 2])
        assert action in [0, 1, 2]


class TestHeuristicAgent:
    """Test HeuristicAgent."""
    
    def test_initialization(self) -> None:
        """Test that HeuristicAgent initializes correctly."""
        agent = HeuristicAgent(player=1)
        assert agent.player == 1
        assert agent.opponent == -1
        
        agent2 = HeuristicAgent(player=-1)
        assert agent2.player == -1
        assert agent2.opponent == 1
    
    def test_takes_winning_move(self) -> None:
        """Test that agent takes winning move when available."""
        # X X _ (X can win at position 2)
        # O O .
        # . . .
        state = np.array([1, 1, 0, -1, -1, 0, 0, 0, 0])
        legal_actions = [2, 5, 6, 7, 8]
        
        agent = HeuristicAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 2  # Winning move
    
    def test_blocks_opponent_win(self) -> None:
        """Test that agent blocks opponent from winning."""
        # X . .
        # O O _ (O about to win, X must block at position 5)
        # . . X
        state = np.array([1, 0, 0, -1, -1, 0, 0, 0, 1])
        legal_actions = [1, 2, 5, 6, 7]
        
        agent = HeuristicAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 5  # Block opponent's win
    
    def test_prefers_center(self) -> None:
        """Test that agent prefers center when no immediate threats."""
        state = np.array([1, 0, 0, 0, 0, 0, 0, 0, -1])
        legal_actions = [1, 2, 3, 4, 5, 6, 7]
        
        agent = HeuristicAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 4  # Center
    
    def test_prefers_corners_over_sides(self) -> None:
        """Test that agent prefers corners when center not available."""
        # . . .
        # . X .
        # . . O
        state = np.array([0, 0, 0, 0, 1, 0, 0, 0, -1])
        legal_actions = [0, 1, 2, 3, 5, 6, 7]
        
        agent = HeuristicAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action in [0, 2, 6]  # Corners
    
    def test_wins_over_blocks(self) -> None:
        """Test that winning takes priority over blocking."""
        # X X _ (can win at 2)
        # O O _ (O can win at 5)
        # . . .
        state = np.array([1, 1, 0, -1, -1, 0, 0, 0, 0])
        legal_actions = [2, 5, 6, 7, 8]
        
        agent = HeuristicAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 2  # Win instead of blocking
    
    def test_raises_on_no_legal_actions(self) -> None:
        """Test that HeuristicAgent raises error when no legal actions."""
        state = np.zeros(9, dtype=np.int_)
        agent = HeuristicAgent()
        
        with pytest.raises(ValueError, match="No legal actions"):
            agent.select_action(state, [])
    
    def test_opponent_perspective(self) -> None:
        """Test that agent works correctly as player -1."""
        # O O _ (O can win at position 2)
        # X X .
        # . . .
        state = np.array([-1, -1, 0, 1, 1, 0, 0, 0, 0])
        legal_actions = [2, 5, 6, 7, 8]
        
        agent = HeuristicAgent(player=-1)
        action = agent.select_action(state, legal_actions)
        assert action == 2  # Winning move for O


class TestMinimaxAgent:
    """Test MinimaxAgent."""
    
    def test_initialization(self) -> None:
        """Test that MinimaxAgent initializes correctly."""
        agent = MinimaxAgent(player=1)
        assert agent.player == 1
        assert agent.opponent == -1
    
    def test_takes_winning_move(self) -> None:
        """Test that minimax takes winning move."""
        # X X _ (can win at 2)
        # O . .
        # . O .
        state = np.array([1, 1, 0, -1, 0, 0, 0, -1, 0])
        legal_actions = [2, 4, 5, 6, 8]
        
        agent = MinimaxAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 2
    
    def test_blocks_opponent_win(self) -> None:
        """Test that minimax blocks opponent from winning."""
        # X . .
        # O O _ (must block at 5)
        # . . X
        state = np.array([1, 0, 0, -1, -1, 0, 0, 0, 1])
        legal_actions = [1, 2, 5, 6, 7]
        
        agent = MinimaxAgent(player=1)
        action = agent.select_action(state, legal_actions)
        assert action == 5
    
    def test_perfect_opening_move(self) -> None:
        """Test that minimax makes reasonable opening move."""
        state = np.zeros(9, dtype=np.int_)
        legal_actions = list(range(9))
        
        agent = MinimaxAgent(player=1)
        action = agent.select_action(state, legal_actions)
        
        # Optimal opening is center or corner
        assert action in [0, 2, 4, 6, 8]
    
    def test_never_loses_vs_random(self) -> None:
        """Test that minimax never loses against random play."""
        env = TicTacToeEnv()
        minimax = MinimaxAgent(player=1)
        random = RandomAgent(seed=42)
        
        losses = 0
        
        for _ in range(20):
            env.reset()
            done = False
            
            while not done:
                # Minimax plays as X (player 1)
                legal = env.legal_actions()
                action = minimax.select_action(env.board, legal)
                _, reward, done, info = env.step(action)
                
                if done:
                    if "winner" in info and info["winner"] == -1:
                        losses += 1
                    break
                
                # Random plays as O (player -1)
                legal = env.legal_actions()
                action = random.select_action(env.board, legal)
                _, _, done, _ = env.step(action)
        
        assert losses == 0  # Minimax should never lose
    
    def test_minimax_vs_minimax_always_draws(self) -> None:
        """Test that two minimax agents always draw."""
        env = TicTacToeEnv()
        minimax1 = MinimaxAgent(player=1)
        minimax2 = MinimaxAgent(player=-1)
        
        draws = 0
        
        for _ in range(5):  # Fewer games since minimax is slow
            env.reset()
            done = False
            
            while not done:
                # Minimax 1 plays as X
                legal = env.legal_actions()
                action = minimax1.select_action(env.board, legal)
                _, _, done, info = env.step(action)
                
                if done:
                    if info.get("draw", False):
                        draws += 1
                    break
                
                # Minimax 2 plays as O
                legal = env.legal_actions()
                action = minimax2.select_action(env.board, legal)
                _, _, done, info = env.step(action)
                
                if done:
                    if info.get("draw", False):
                        draws += 1
        
        assert draws == 5  # All games should be draws
    
    def test_raises_on_no_legal_actions(self) -> None:
        """Test that MinimaxAgent raises error when no legal actions."""
        state = np.zeros(9, dtype=np.int_)
        agent = MinimaxAgent()
        
        with pytest.raises(ValueError, match="No legal actions"):
            agent.select_action(state, [])


class TestAgentComparison:
    """Test agents against each other."""
    
    def test_heuristic_beats_random_often(self) -> None:
        """Test that heuristic agent beats random agent most of the time."""
        env = TicTacToeEnv()
        heuristic = HeuristicAgent(player=1)
        random = RandomAgent(seed=42)
        
        heuristic_wins = 0
        random_wins = 0
        draws = 0
        
        for _ in range(50):
            env.reset()
            done = False
            
            while not done:
                # Heuristic plays as X
                legal = env.legal_actions()
                action = heuristic.select_action(env.board, legal)
                _, reward, done, info = env.step(action)
                
                if done:
                    if "winner" in info:
                        if info["winner"] == 1:
                            heuristic_wins += 1
                        else:
                            random_wins += 1
                    else:
                        draws += 1
                    break
                
                # Random plays as O
                legal = env.legal_actions()
                action = random.select_action(env.board, legal)
                _, _, done, info = env.step(action)
                
                if done:
                    if "winner" in info:
                        if info["winner"] == 1:
                            heuristic_wins += 1
                        else:
                            random_wins += 1
                    else:
                        draws += 1
        
        # Heuristic should win significantly more than random
        assert heuristic_wins > random_wins
        assert heuristic_wins + random_wins + draws == 50
    
    def test_random_vs_random_balanced(self) -> None:
        """Test that random vs random has reasonable balance."""
        env = TicTacToeEnv()
        random1 = RandomAgent(seed=42)
        random2 = RandomAgent(seed=123)
        
        player1_wins = 0
        player2_wins = 0
        draws = 0
        
        for _ in range(50):
            env.reset()
            done = False
            
            while not done:
                # Random 1 plays as X
                legal = env.legal_actions()
                action = random1.select_action(env.board, legal)
                _, _, done, info = env.step(action)
                
                if done:
                    if "winner" in info:
                        if info["winner"] == 1:
                            player1_wins += 1
                        else:
                            player2_wins += 1
                    else:
                        draws += 1
                    break
                
                # Random 2 plays as O
                legal = env.legal_actions()
                action = random2.select_action(env.board, legal)
                _, _, done, info = env.step(action)
                
                if done:
                    if "winner" in info:
                        if info["winner"] == 1:
                            player1_wins += 1
                        else:
                            player2_wins += 1
                    else:
                        draws += 1
        
        # Should have some wins for each and some draws
        assert player1_wins > 0
        assert player2_wins > 0
        assert draws > 0
        assert player1_wins + player2_wins + draws == 50
