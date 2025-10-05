"""Visualization utilities for training metrics."""

from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np


def plot_learning_curves(
    metrics: Dict[str, List],
    title: str = "Q-Learning Training Progress",
    save_path: str | None = None,
) -> None:
    """
    Plot learning curves from training metrics.
    
    Args:
        metrics: Dictionary of metrics from TrainingMetrics.to_dict()
        title: Plot title
        save_path: Path to save figure (if None, display only)
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(title, fontsize=16, fontweight="bold")
    
    # Plot 1: Win/Loss/Draw rates
    ax = axes[0, 0]
    ax.plot(metrics["episodes"], metrics["win_rates"], label="Win Rate", linewidth=2)
    ax.plot(metrics["episodes"], metrics["loss_rates"], label="Loss Rate", linewidth=2)
    ax.plot(metrics["episodes"], metrics["draw_rates"], label="Draw Rate", linewidth=2)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Rate")
    ax.set_title("Win/Loss/Draw Rates")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.05, 1.05])
    
    # Plot 2: Epsilon decay
    ax = axes[0, 1]
    ax.plot(metrics["episodes"], metrics["epsilons"], color="orange", linewidth=2)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Epsilon")
    ax.set_title("Exploration Rate (ε) Decay")
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.05, max(metrics["epsilons"]) * 1.1])
    
    # Plot 3: Q-table growth
    ax = axes[1, 0]
    ax.plot(metrics["episodes"], metrics["q_table_sizes"], color="green", linewidth=2)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Number of States")
    ax.set_title("Q-Table Size Growth")
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Cumulative wins/losses/draws
    ax = axes[1, 1]
    cumulative_wins = np.cumsum(metrics["wins"])
    cumulative_losses = np.cumsum(metrics["losses"])
    cumulative_draws = np.cumsum(metrics["draws"])
    
    ax.plot(metrics["episodes"], cumulative_wins, label="Wins", linewidth=2)
    ax.plot(metrics["episodes"], cumulative_losses, label="Losses", linewidth=2)
    ax.plot(metrics["episodes"], cumulative_draws, label="Draws", linewidth=2)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Cumulative Count")
    ax.set_title("Cumulative Game Outcomes")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to {save_path}")
    else:
        plt.show()


def plot_comparison(
    metrics_list: List[Dict[str, List]],
    labels: List[str],
    title: str = "Training Comparison",
    save_path: str | None = None,
) -> None:
    """
    Compare multiple training runs.
    
    Args:
        metrics_list: List of metric dictionaries
        labels: Labels for each training run
        title: Plot title
        save_path: Path to save figure (if None, display only)
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(title, fontsize=16, fontweight="bold")
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(metrics_list)))
    
    # Plot 1: Win rates comparison
    ax = axes[0]
    for metrics, label, color in zip(metrics_list, labels, colors):
        ax.plot(
            metrics["episodes"], metrics["win_rates"],
            label=label, linewidth=2, color=color
        )
    ax.set_xlabel("Episode")
    ax.set_ylabel("Win Rate")
    ax.set_title("Win Rate Comparison")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim([-0.05, 1.05])
    
    # Plot 2: Q-table size comparison
    ax = axes[1]
    for metrics, label, color in zip(metrics_list, labels, colors):
        ax.plot(
            metrics["episodes"], metrics["q_table_sizes"],
            label=label, linewidth=2, color=color
        )
    ax.set_xlabel("Episode")
    ax.set_ylabel("Number of States")
    ax.set_title("Q-Table Size Comparison")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved comparison plot to {save_path}")
    else:
        plt.show()


def print_training_summary(metrics: Dict[str, List]) -> None:
    """Print summary statistics from training."""
    if not metrics["episodes"]:
        print("No training data available.")
        return
    
    print("\n" + "=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    
    # Final episode stats
    final_win_rate = metrics["win_rates"][-1]
    final_loss_rate = metrics["loss_rates"][-1]
    final_draw_rate = metrics["draw_rates"][-1]
    final_epsilon = metrics["epsilons"][-1]
    final_q_size = metrics["q_table_sizes"][-1]
    
    print(f"\nFinal Episode: {metrics['episodes'][-1]}")
    print(f"  Win Rate:    {final_win_rate:.1%}")
    print(f"  Loss Rate:   {final_loss_rate:.1%}")
    print(f"  Draw Rate:   {final_draw_rate:.1%}")
    print(f"  Epsilon:     {final_epsilon:.4f}")
    print(f"  Q-Table Size: {final_q_size} states")
    
    # Average performance over last 20% of training
    split_idx = int(len(metrics["win_rates"]) * 0.8)
    if split_idx < len(metrics["win_rates"]):
        avg_win_rate = np.mean(metrics["win_rates"][split_idx:])
        avg_loss_rate = np.mean(metrics["loss_rates"][split_idx:])
        avg_draw_rate = np.mean(metrics["draw_rates"][split_idx:])
        
        print(f"\nLast 20% Average:")
        print(f"  Win Rate:  {avg_win_rate:.1%}")
        print(f"  Loss Rate: {avg_loss_rate:.1%}")
        print(f"  Draw Rate: {avg_draw_rate:.1%}")
    
    # Best performance
    best_win_idx = np.argmax(metrics["win_rates"])
    best_win_rate = metrics["win_rates"][best_win_idx]
    best_win_episode = metrics["episodes"][best_win_idx]
    
    print(f"\nBest Win Rate: {best_win_rate:.1%} at episode {best_win_episode}")
    
    print("=" * 60 + "\n")





