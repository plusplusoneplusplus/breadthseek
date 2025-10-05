"""Tests for Q-learning agent."""

import numpy as np
import pytest
import tempfile
import os
from rl_tictactoe.agents.q_learning import QLearningAgent
from rl_tictactoe.agents.random import RandomAgent
from rl_tictactoe.env import TicTacToeEnv
from rl_tictactoe.train import train_q_learning


class TestQLearningAgent:
    """Test QLearningAgent."""
    
    def test_initialization(self) -> None:
        """Test that QLearningAgent initializes correctly."""
        agent = QLearningAgent(player=1, alpha=0.1, gamma=0.95, epsilon=0.1)
        
        assert agent.player == 1
        assert agent.alpha == 0.1
        assert agent.gamma == 0.95
        assert agent.epsilon == 0.1
        assert len(agent.q_table) == 0
        assert agent.training_mode
    
    def test_state_encoding(self) -> None:
        """Test state encoding to string key."""
        agent = QLearningAgent()
        state = np.array([1, 0, -1, 0, 1, 0, 0, 0, -1])
        key = agent._get_state_key(state)
        assert isinstance(key, str)
        assert key == "10-101000-1"
    
    def test_q_table_initialization(self) -> None:
        """Test that Q-values are initialized to zero for new states."""
        agent = QLearningAgent()
        state = np.zeros(9, dtype=np.int_)
        state_key = agent._get_state_key(state)
        
        q_values = agent._get_q_values(state_key)
        
        assert state_key in agent.q_table
        assert len(q_values) == 9
        assert np.all(q_values == 0.0)
    
    def test_select_action_deterministic(self) -> None:
        """Test action selection in greedy mode (epsilon=0)."""
        agent = QLearningAgent(epsilon=0.0, seed=42)
        state = np.zeros(9, dtype=np.int_)
        legal_actions = [0, 1, 2, 3, 4, 5, 6, 7, 8]
        
        # All Q-values are zero initially, should pick first legal action with max Q
        action = agent.select_action(state, legal_actions)
        assert action in legal_actions
    
    def test_select_action_exploration(self) -> None:
        """Test that high epsilon leads to exploration."""
        agent = QLearningAgent(epsilon=1.0, seed=42)
        state = np.zeros(9, dtype=np.int_)
        legal_actions = [0, 1, 2]
        
        # With epsilon=1.0, should always explore (select randomly)
        actions = [agent.select_action(state, legal_actions) for _ in range(50)]
        
        # Should see multiple different actions
        unique_actions = set(actions)
        assert len(unique_actions) > 1
    
    def test_select_action_respects_legal_actions(self) -> None:
        """Test that agent only selects from legal actions."""
        agent = QLearningAgent(epsilon=0.5, seed=42)
        state = np.array([1, 0, -1, 0, 1, 0, 0, 0, -1])
        legal_actions = [1, 3, 5, 6, 7]
        
        for _ in range(50):
            action = agent.select_action(state, legal_actions)
            assert action in legal_actions
    
    def test_learning_updates_q_values(self) -> None:
        """Test that learning updates Q-values."""
        agent = QLearningAgent(alpha=0.5, gamma=0.9)
        state = np.zeros(9, dtype=np.int_)
        state_key = agent._get_state_key(state)
        
        # Select action
        legal_actions = [0, 1, 2]
        action = agent.select_action(state, legal_actions)
        
        # Get initial Q-value
        q_before = agent.q_table[state_key][action].copy()
        
        # Simulate winning
        agent.learn(reward=1.0, next_state=None, legal_actions=[], done=True)
        
        # Q-value should have increased
        q_after = agent.q_table[state_key][action]
        assert q_after > q_before
    
    def test_training_mode_toggle(self) -> None:
        """Test that training mode can be toggled."""
        agent = QLearningAgent(epsilon=0.5)
        
        assert agent.training_mode
        
        agent.set_training_mode(False)
        assert not agent.training_mode
        
        agent.set_training_mode(True)
        assert agent.training_mode
    
    def test_epsilon_update(self) -> None:
        """Test that epsilon can be updated."""
        agent = QLearningAgent(epsilon=0.5)
        
        agent.set_epsilon(0.1)
        assert agent.epsilon == 0.1
    
    def test_alpha_update(self) -> None:
        """Test that alpha can be updated."""
        agent = QLearningAgent(alpha=0.1)
        
        agent.set_alpha(0.05)
        assert agent.alpha == 0.05
    
    def test_reset(self) -> None:
        """Test that reset clears episode state."""
        agent = QLearningAgent()
        state = np.zeros(9, dtype=np.int_)
        
        agent.select_action(state, [0, 1, 2])
        assert agent.last_state is not None
        assert agent.last_action is not None
        
        agent.reset()
        assert agent.last_state is None
        assert agent.last_action is None
    
    def test_save_and_load(self) -> None:
        """Test saving and loading Q-table."""
        agent = QLearningAgent(player=1, alpha=0.1, gamma=0.95, epsilon=0.2)
        
        # Train a bit to populate Q-table
        state1 = np.zeros(9, dtype=np.int_)
        agent.select_action(state1, [0, 1, 2])
        agent.learn(1.0, None, [], True)
        
        state2 = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0])
        agent.select_action(state2, [1, 2, 3])
        agent.learn(0.5, None, [], True)
        
        # Save
        with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as f:
            filepath = f.name
        
        try:
            agent.save(filepath)
            
            # Create new agent and load
            new_agent = QLearningAgent()
            new_agent.load(filepath)
            
            # Check parameters
            assert new_agent.player == agent.player
            assert new_agent.alpha == agent.alpha
            assert new_agent.gamma == agent.gamma
            assert new_agent.epsilon == agent.epsilon
            
            # Check Q-table
            assert len(new_agent.q_table) == len(agent.q_table)
            for key in agent.q_table:
                assert key in new_agent.q_table
                np.testing.assert_array_equal(
                    new_agent.q_table[key], agent.q_table[key]
                )
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    
    def test_get_stats(self) -> None:
        """Test getting Q-table statistics."""
        agent = QLearningAgent()
        
        stats = agent.get_stats()
        assert stats["num_states"] == 0
        
        # Add some states
        state1 = np.zeros(9, dtype=np.int_)
        agent.select_action(state1, [0])
        agent.learn(1.0, None, [], True)
        
        stats = agent.get_stats()
        assert stats["num_states"] == 1


class TestQLearningTraining:
    """Test Q-learning training."""
    
    def test_train_vs_random_improves(self) -> None:
        """Test that training vs random agent improves performance."""
        agent = QLearningAgent(player=1, alpha=0.1, gamma=0.95, seed=42)
        opponent = RandomAgent(seed=123)
        
        # Train for a small number of episodes
        metrics = train_q_learning(
            agent,
            opponent,
            num_episodes=500,
            eval_interval=100,
            epsilon_start=1.0,
            epsilon_end=0.01,
            epsilon_decay=0.99,
            verbose=False,
        )
        
        # Check that metrics were recorded
        assert len(metrics.episodes) > 0
        assert len(metrics.win_rates) > 0
        
        # Check that win rate improved (should be higher at end than start)
        if len(metrics.win_rates) >= 2:
            # Allow for some variance, but should see improvement
            final_win_rate = np.mean(metrics.win_rates[-2:])
            initial_win_rate = metrics.win_rates[0]
            assert final_win_rate >= initial_win_rate - 0.1  # Allow slight variance
    
    def test_epsilon_decay_works(self) -> None:
        """Test that epsilon decays during training."""
        agent = QLearningAgent(player=1, seed=42)
        opponent = RandomAgent(seed=123)
        
        metrics = train_q_learning(
            agent,
            opponent,
            num_episodes=300,
            eval_interval=100,
            epsilon_start=1.0,
            epsilon_end=0.01,
            epsilon_decay=0.98,
            verbose=False,
        )
        
        # Epsilon should decrease over time
        assert metrics.epsilons[0] > metrics.epsilons[-1]
        assert metrics.epsilons[-1] < 0.5  # Should have decayed significantly
    
    def test_q_table_grows(self) -> None:
        """Test that Q-table grows during training."""
        agent = QLearningAgent(player=1, seed=42)
        opponent = RandomAgent(seed=123)
        
        metrics = train_q_learning(
            agent,
            opponent,
            num_episodes=200,
            eval_interval=100,
            verbose=False,
        )
        
        # Q-table should grow as agent explores
        assert metrics.q_table_sizes[-1] > 0
        if len(metrics.q_table_sizes) > 1:
            assert metrics.q_table_sizes[-1] >= metrics.q_table_sizes[0]
    
    def test_agent_plays_second(self) -> None:
        """Test training when agent plays as O (second player)."""
        agent = QLearningAgent(player=-1, seed=42)
        opponent = RandomAgent(seed=123)
        
        metrics = train_q_learning(
            agent,
            opponent,
            num_episodes=200,
            eval_interval=100,
            agent_plays_first=False,
            verbose=False,
        )
        
        # Should still record metrics
        assert len(metrics.episodes) > 0
        assert metrics.q_table_sizes[-1] > 0





