#!/usr/bin/env python3
"""Train Q-learning agent and evaluate performance."""

import sys
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rl_tictactoe.agents import QLearningAgent, RandomAgent, HeuristicAgent
from rl_tictactoe.train import train_q_learning
from rl_tictactoe.visualize import plot_learning_curves, print_training_summary
from rl_tictactoe.evaluate import evaluate_agents, print_evaluation_results


def main() -> None:
    """Train and evaluate Q-learning agent."""
    parser = argparse.ArgumentParser(description="Train Q-learning agent for Tic-Tac-Toe")
    parser.add_argument(
        "--opponent",
        type=str,
        default="random",
        choices=["random", "heuristic"],
        help="Opponent to train against",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=10000,
        help="Number of training episodes",
    )
    parser.add_argument(
        "--eval-interval",
        type=int,
        default=500,
        help="Episodes between evaluations",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.1,
        help="Learning rate",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.95,
        help="Discount factor",
    )
    parser.add_argument(
        "--epsilon-start",
        type=float,
        default=1.0,
        help="Initial exploration rate",
    )
    parser.add_argument(
        "--epsilon-end",
        type=float,
        default=0.01,
        help="Final exploration rate",
    )
    parser.add_argument(
        "--epsilon-decay",
        type=float,
        default=0.9995,
        help="Epsilon decay factor",
    )
    parser.add_argument(
        "--save-model",
        type=str,
        default=None,
        help="Path to save trained model",
    )
    parser.add_argument(
        "--save-plot",
        type=str,
        default=None,
        help="Path to save learning curve plot",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("Q-LEARNING TRAINING")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Opponent:       {args.opponent}")
    print(f"  Episodes:       {args.episodes}")
    print(f"  Alpha:          {args.alpha}")
    print(f"  Gamma:          {args.gamma}")
    print(f"  Epsilon:        {args.epsilon_start} → {args.epsilon_end} (decay: {args.epsilon_decay})")
    print(f"  Seed:           {args.seed}")
    print()
    
    # Create agent
    agent = QLearningAgent(
        player=1,
        alpha=args.alpha,
        gamma=args.gamma,
        epsilon=args.epsilon_start,
        seed=args.seed,
    )
    
    # Create opponent
    if args.opponent == "random":
        opponent = RandomAgent(seed=args.seed + 1)
        opponent_name = "Random"
    else:
        opponent = HeuristicAgent(player=-1)
        opponent_name = "Heuristic"
    
    print(f"Training agent (X) vs {opponent_name} (O)...")
    print()
    
    # Train
    metrics = train_q_learning(
        agent,
        opponent,
        num_episodes=args.episodes,
        eval_interval=args.eval_interval,
        epsilon_start=args.epsilon_start,
        epsilon_end=args.epsilon_end,
        epsilon_decay=args.epsilon_decay,
        verbose=True,
    )
    
    # Print summary
    print_training_summary(metrics.to_dict())
    
    # Save model if requested
    if args.save_model:
        save_path = Path(args.save_model)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        agent.save(str(save_path))
        print(f"Saved model to {save_path}")
    
    # Plot learning curves if requested
    if args.save_plot:
        plot_path = Path(args.save_plot)
        plot_path.parent.mkdir(parents=True, exist_ok=True)
        plot_learning_curves(
            metrics.to_dict(),
            title=f"Q-Learning vs {opponent_name}",
            save_path=str(plot_path),
        )
    
    # Final evaluation
    print("\n" + "=" * 80)
    print("FINAL EVALUATION (greedy policy, ε=0)")
    print("=" * 80)
    
    agent.set_training_mode(False)
    agent.set_epsilon(0.0)
    
    # Evaluate vs training opponent
    print(f"\n1. vs {opponent_name} (training opponent)")
    if args.opponent == "random":
        eval_opponent = RandomAgent(seed=999)
    else:
        eval_opponent = HeuristicAgent(player=-1)
    
    results = evaluate_agents(
        agent, eval_opponent,
        "Q-Learning", opponent_name,
        num_games=100,
    )
    print_evaluation_results(results)
    
    # Evaluate vs other opponents
    print("\n2. vs Random (if not training opponent)")
    if args.opponent != "random":
        random_opponent = RandomAgent(seed=999)
        results = evaluate_agents(
            agent, random_opponent,
            "Q-Learning", "Random",
            num_games=100,
        )
        print_evaluation_results(results)
    
    print("\n3. vs Heuristic (if not training opponent)")
    if args.opponent != "heuristic":
        heuristic_opponent = HeuristicAgent(player=-1)
        results = evaluate_agents(
            agent, heuristic_opponent,
            "Q-Learning", "Heuristic",
            num_games=100,
        )
        print_evaluation_results(results)
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()





