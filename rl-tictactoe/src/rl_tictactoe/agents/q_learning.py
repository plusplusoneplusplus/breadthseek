"""Q-learning agent for Tic-Tac-Toe."""

from typing import List, Dict, Tuple
import numpy as np
import numpy.typing as npt


class QLearningAgent:
    """
    Tabular Q-learning agent.
    
    Uses epsilon-greedy exploration and Q-learning update rule:
    Q(s,a) <- Q(s,a) + alpha * [r + gamma * max_a' Q(s',a') - Q(s,a)]
    
    State encoding: String representation of board state
    Q-table: Dict[state_str, np.ndarray(9)] mapping states to action values
    """
    
    def __init__(
        self,
        player: int = 1,
        alpha: float = 0.1,
        gamma: float = 0.95,
        epsilon: float = 0.1,
        seed: int | None = None,
    ) -> None:
        """
        Initialize Q-learning agent.
        
        Args:
            player: Which player this agent is (1 for X, -1 for O)
            alpha: Learning rate
            gamma: Discount factor
            epsilon: Exploration rate (probability of random action)
            seed: Random seed for reproducibility
        """
        self.player = player
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = np.random.default_rng(seed)
        
        # Q-table: maps state_str -> action values (9-element array)
        self.q_table: Dict[str, npt.NDArray[np.float64]] = {}
        
        # Episode tracking
        self.last_state: str | None = None
        self.last_action: int | None = None
        
        # Training statistics
        self.training_mode = True
    
    def _get_state_key(self, state: npt.NDArray[np.int_]) -> str:
        """Convert state to string key for Q-table."""
        return "".join(str(x) for x in state)
    
    def _get_q_values(self, state_key: str) -> npt.NDArray[np.float64]:
        """Get Q-values for a state, initializing if new."""
        if state_key not in self.q_table:
            self.q_table[state_key] = np.zeros(9, dtype=np.float64)
        return self.q_table[state_key]
    
    def select_action(
        self, state: npt.NDArray[np.int_], legal_actions: List[int]
    ) -> int:
        """
        Select action using epsilon-greedy policy.
        
        Args:
            state: Current board state
            legal_actions: List of legal action indices
            
        Returns:
            Selected action
        """
        if not legal_actions:
            raise ValueError("No legal actions available")
        
        state_key = self._get_state_key(state)
        q_values = self._get_q_values(state_key)
        
        # Epsilon-greedy: explore with probability epsilon
        if self.training_mode and self.rng.random() < self.epsilon:
            action = int(self.rng.choice(legal_actions))
        else:
            # Exploit: choose best legal action
            legal_q_values = [(a, q_values[a]) for a in legal_actions]
            action = max(legal_q_values, key=lambda x: x[1])[0]
        
        # Store for learning
        self.last_state = state_key
        self.last_action = action
        
        return action
    
    def learn(
        self,
        reward: float,
        next_state: npt.NDArray[np.int_] | None,
        legal_actions: List[int],
        done: bool,
    ) -> None:
        """
        Update Q-values using Q-learning rule.
        
        Args:
            reward: Reward received
            next_state: Next state (None if terminal)
            legal_actions: Legal actions in next state
            done: Whether episode terminated
        """
        if not self.training_mode or self.last_state is None:
            return
        
        q_values = self._get_q_values(self.last_state)
        old_q = q_values[self.last_action]
        
        # Calculate TD target
        if done or next_state is None:
            # Terminal state: no future value
            td_target = reward
        else:
            # Non-terminal: bootstrap from next state
            next_state_key = self._get_state_key(next_state)
            next_q_values = self._get_q_values(next_state_key)
            
            # Max Q-value over legal actions in next state
            if legal_actions:
                max_next_q = max(next_q_values[a] for a in legal_actions)
            else:
                max_next_q = 0.0
            
            td_target = reward + self.gamma * max_next_q
        
        # Q-learning update
        td_error = td_target - old_q
        q_values[self.last_action] = old_q + self.alpha * td_error
    
    def reset(self) -> None:
        """Reset episode tracking."""
        self.last_state = None
        self.last_action = None
    
    def set_training_mode(self, mode: bool) -> None:
        """Set training mode (enables/disables exploration and learning)."""
        self.training_mode = mode
    
    def set_epsilon(self, epsilon: float) -> None:
        """Update exploration rate."""
        self.epsilon = epsilon
    
    def set_alpha(self, alpha: float) -> None:
        """Update learning rate."""
        self.alpha = alpha
    
    def save(self, filepath: str) -> None:
        """Save Q-table to file."""
        np.savez_compressed(
            filepath,
            q_table_keys=list(self.q_table.keys()),
            q_table_values=np.array(list(self.q_table.values())),
            player=self.player,
            alpha=self.alpha,
            gamma=self.gamma,
            epsilon=self.epsilon,
        )
    
    def load(self, filepath: str) -> None:
        """Load Q-table from file."""
        data = np.load(filepath, allow_pickle=True)
        keys = data["q_table_keys"]
        values = data["q_table_values"]
        
        self.q_table = {k: v for k, v in zip(keys, values)}
        self.player = int(data["player"])
        self.alpha = float(data["alpha"])
        self.gamma = float(data["gamma"])
        self.epsilon = float(data["epsilon"])
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the Q-table."""
        return {
            "num_states": len(self.q_table),
            "total_updates": sum(1 for q in self.q_table.values() if np.any(q != 0)),
        }
