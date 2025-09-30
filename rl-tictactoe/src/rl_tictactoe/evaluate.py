"""Evaluation utilities for comparing agents."""

from typing import Dict, Tuple, Any
import numpy as np
from rl_tictactoe.env import TicTacToeEnv


def play_game(
    env: TicTacToeEnv,
    agent1: Any,
    agent2: Any,
    verbose: bool = False,
) -> Tuple[int | None, int]:
    """
    Play a single game between two agents.
    
    Args:
        env: TicTacToeEnv instance
        agent1: Agent playing as X (player 1)
        agent2: Agent playing as O (player -1)
        verbose: If True, print game progress
        
    Returns:
        Tuple of (winner, num_moves)
        - winner: 1 if agent1 wins, -1 if agent2 wins, 0 for draw
        - num_moves: Total number of moves played
    """
    env.reset()
    agent1.reset()
    agent2.reset()
    
    done = False
    num_moves = 0
    
    while not done:
        # Agent 1 (X) plays
        legal = env.legal_actions()
        action = agent1.select_action(env.board.copy(), legal)
        _, _, done, info = env.step(action)
        num_moves += 1
        
        if verbose:
            print(f"Move {num_moves}: X plays {action}")
            print(env.render())
            print()
        
        if done:
            if "winner" in info:
                return info["winner"], num_moves
            else:
                return 0, num_moves
        
        # Agent 2 (O) plays
        legal = env.legal_actions()
        action = agent2.select_action(env.board.copy(), legal)
        _, _, done, info = env.step(action)
        num_moves += 1
        
        if verbose:
            print(f"Move {num_moves}: O plays {action}")
            print(env.render())
            print()
        
        if done:
            if "winner" in info:
                return info["winner"], num_moves
            else:
                return 0, num_moves
    
    return 0, num_moves


def evaluate_agents(
    agent1: Any,
    agent2: Any,
    agent1_name: str,
    agent2_name: str,
    num_games: int = 100,
    seed: int | None = None,
) -> Dict[str, Any]:
    """
    Evaluate two agents against each other.
    
    Args:
        agent1: First agent (plays as X)
        agent2: Second agent (plays as O)
        agent1_name: Name of first agent for display
        agent2_name: Name of second agent for display
        num_games: Number of games to play
        seed: Random seed for environment
        
    Returns:
        Dictionary with evaluation results
    """
    if seed is not None:
        np.random.seed(seed)
    
    env = TicTacToeEnv()
    
    agent1_wins = 0
    agent2_wins = 0
    draws = 0
    total_moves = 0
    
    for _ in range(num_games):
        winner, moves = play_game(env, agent1, agent2)
        total_moves += moves
        
        if winner == 1:
            agent1_wins += 1
        elif winner == -1:
            agent2_wins += 1
        else:
            draws += 1
    
    results = {
        "agent1_name": agent1_name,
        "agent2_name": agent2_name,
        "num_games": num_games,
        "agent1_wins": agent1_wins,
        "agent2_wins": agent2_wins,
        "draws": draws,
        "agent1_win_rate": agent1_wins / num_games,
        "agent2_win_rate": agent2_wins / num_games,
        "draw_rate": draws / num_games,
        "avg_moves_per_game": total_moves / num_games,
    }
    
    return results


def print_evaluation_results(results: Dict[str, Any]) -> None:
    """
    Pretty print evaluation results.
    
    Args:
        results: Results dictionary from evaluate_agents
    """
    print("=" * 60)
    print(f"{results['agent1_name']} vs {results['agent2_name']}")
    print("=" * 60)
    print(f"Games played: {results['num_games']}")
    print()
    print(f"{results['agent1_name']} wins: {results['agent1_wins']} "
          f"({results['agent1_win_rate']:.1%})")
    print(f"{results['agent2_name']} wins: {results['agent2_wins']} "
          f"({results['agent2_win_rate']:.1%})")
    print(f"Draws: {results['draws']} ({results['draw_rate']:.1%})")
    print()
    print(f"Average moves per game: {results['avg_moves_per_game']:.1f}")
    print("=" * 60)
