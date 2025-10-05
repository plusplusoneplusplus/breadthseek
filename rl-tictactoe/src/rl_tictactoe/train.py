"""Training utilities for Q-learning agent."""

from typing import Any, Dict, List, Tuple
import numpy as np
from rl_tictactoe.env import TicTacToeEnv
from rl_tictactoe.agents.q_learning import QLearningAgent


class TrainingMetrics:
    """Track training metrics over episodes."""
    
    def __init__(self) -> None:
        """Initialize metrics tracking."""
        self.episodes: List[int] = []
        self.wins: List[int] = []
        self.losses: List[int] = []
        self.draws: List[int] = []
        self.win_rates: List[float] = []
        self.loss_rates: List[float] = []
        self.draw_rates: List[float] = []
        self.epsilons: List[float] = []
        self.q_table_sizes: List[int] = []
    
    def record(
        self,
        episode: int,
        wins: int,
        losses: int,
        draws: int,
        epsilon: float,
        q_table_size: int,
        window: int,
    ) -> None:
        """Record metrics for current episode."""
        total = wins + losses + draws
        
        self.episodes.append(episode)
        self.wins.append(wins)
        self.losses.append(losses)
        self.draws.append(draws)
        self.win_rates.append(wins / total if total > 0 else 0.0)
        self.loss_rates.append(losses / total if total > 0 else 0.0)
        self.draw_rates.append(draws / total if total > 0 else 0.0)
        self.epsilons.append(epsilon)
        self.q_table_sizes.append(q_table_size)
    
    def to_dict(self) -> Dict[str, List]:
        """Convert metrics to dictionary."""
        return {
            "episodes": self.episodes,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rates": self.win_rates,
            "loss_rates": self.loss_rates,
            "draw_rates": self.draw_rates,
            "epsilons": self.epsilons,
            "q_table_sizes": self.q_table_sizes,
        }


def train_q_learning(
    agent: QLearningAgent,
    opponent: Any,
    num_episodes: int = 10000,
    eval_interval: int = 100,
    epsilon_start: float = 1.0,
    epsilon_end: float = 0.01,
    epsilon_decay: float = 0.995,
    alpha_start: float | None = None,
    alpha_end: float | None = None,
    alpha_decay: float | None = None,
    agent_plays_first: bool = True,
    verbose: bool = True,
) -> TrainingMetrics:
    """
    Train Q-learning agent against an opponent.
    
    Args:
        agent: QLearningAgent to train
        opponent: Opponent agent
        num_episodes: Number of training episodes
        eval_interval: Episodes between metric recordings
        epsilon_start: Initial exploration rate
        epsilon_end: Final exploration rate
        epsilon_decay: Epsilon decay factor per episode
        alpha_start: Initial learning rate (None = use agent's current)
        alpha_end: Final learning rate (None = no decay)
        alpha_decay: Learning rate decay factor
        agent_plays_first: If True, agent plays as X, else as O
        verbose: Print progress
        
    Returns:
        TrainingMetrics object with learning curves
    """
    env = TicTacToeEnv()
    metrics = TrainingMetrics()
    
    # Set initial epsilon
    agent.set_epsilon(epsilon_start)
    if alpha_start is not None:
        agent.set_alpha(alpha_start)
    
    # Track results in evaluation window
    wins = 0
    losses = 0
    draws = 0
    
    for episode in range(1, num_episodes + 1):
        env.reset()
        agent.reset()
        opponent.reset()
        
        done = False
        
        while not done:
            if agent_plays_first:
                # Agent plays as X (player 1)
                state = env.board.copy()
                legal = env.legal_actions()
                action = agent.select_action(state, legal)
                next_state, reward, done, info = env.step(action)
                
                if done:
                    # Episode ended with agent's move
                    agent.learn(reward, None, [], True)
                    
                    if "winner" in info:
                        if info["winner"] == 1:
                            wins += 1
                        else:
                            losses += 1
                    else:
                        draws += 1
                    break
                else:
                    # Continue with opponent's turn
                    agent.learn(0.0, next_state, env.legal_actions(), False)
                
                # Opponent plays as O (player -1)
                state = env.board.copy()
                legal = env.legal_actions()
                action = opponent.select_action(state, legal)
                next_state, reward, done, info = env.step(action)
                
                if done:
                    # Episode ended with opponent's move
                    # Agent gets negative reward from opponent's perspective
                    agent.learn(-reward, None, [], True)
                    
                    if "winner" in info:
                        if info["winner"] == -1:
                            losses += 1
                        else:
                            wins += 1
                    else:
                        draws += 1
            else:
                # Opponent plays first as X
                state = env.board.copy()
                legal = env.legal_actions()
                action = opponent.select_action(state, legal)
                next_state, reward, done, info = env.step(action)
                
                if done:
                    # Opponent won/drew before agent played
                    if "winner" in info:
                        losses += 1
                    else:
                        draws += 1
                    break
                
                # Agent plays as O (player -1)
                state = env.board.copy()
                legal = env.legal_actions()
                action = agent.select_action(state, legal)
                next_state, reward, done, info = env.step(action)
                
                # Agent experiences negative of environment reward
                agent_reward = -reward if "winner" in info else reward
                
                if done:
                    agent.learn(agent_reward, None, [], True)
                    
                    if "winner" in info:
                        if info["winner"] == -1:
                            wins += 1
                        else:
                            losses += 1
                    else:
                        draws += 1
                else:
                    agent.learn(0.0, next_state, env.legal_actions(), False)
        
        # Decay epsilon
        new_epsilon = max(epsilon_end, agent.epsilon * epsilon_decay)
        agent.set_epsilon(new_epsilon)
        
        # Decay alpha if specified
        if alpha_start is not None and alpha_end is not None and alpha_decay is not None:
            new_alpha = max(alpha_end, agent.alpha * alpha_decay)
            agent.set_alpha(new_alpha)
        
        # Record metrics at intervals
        if episode % eval_interval == 0:
            stats = agent.get_stats()
            metrics.record(
                episode, wins, losses, draws,
                agent.epsilon, stats["num_states"], eval_interval
            )
            
            if verbose:
                total = wins + losses + draws
                win_rate = wins / total if total > 0 else 0.0
                print(
                    f"Episode {episode}/{num_episodes} | "
                    f"Win: {win_rate:.1%} | "
                    f"Loss: {losses/total:.1%} | "
                    f"Draw: {draws/total:.1%} | "
                    f"ε: {agent.epsilon:.3f} | "
                    f"Q-states: {stats['num_states']}"
                )
            
            # Reset counters
            wins = losses = draws = 0
    
    return metrics





