# RL Tic-Tac-Toe

Train an agent to play Tic-Tac-Toe using Reinforcement Learning (RL). This repo gives you a clean path from zero-to-working agent, including what to learn before each hands-on step.

## Folder structure

- `src/`: Python package with environment, agents, and training loops
- `notebooks/`: Experiment notebooks and visualizations
- `tests/`: Unit tests for environment and agents
- `assets/`: Diagrams, figures, and small saved artifacts
- `scripts/`: CLI tools for training and evaluation

## Quick start

You only need CPU; this is a lightweight project.

Option A (uv):
```bash
cd rl-tictactoe
uv venv && source .venv/bin/activate
uv pip install -e .[dev]
```

Option B (pip):
```bash
cd rl-tictactoe
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```

## Learning path at a glance

- **Python and tooling**: virtualenvs, project structure, running scripts and tests
- **NumPy basics**: arrays, indexing, random sampling
- **Game modeling**: state, actions, transitions, terminal conditions
- **RL foundations**: MDPs, returns, value functions, Bellman equations
- **Tabular methods**: epsilon-greedy, Q-learning, SARSA
- **Training hygiene**: seeding, logging, evaluation, reproducibility

If a term is new, skim the resource listed under the relevant step before coding.

---

## Step-by-step plan (with what to learn before each step)

### 0) Foundations and setup
- Outcome: Ready environment, basic Python tooling, and clear expectations
- Learn before:
  - Python virtualenvs (or `uv`), running modules (`python -m`), basic CLI
  - Git basics (commit, branch)
- Practice:
  - Create and activate a virtual environment
  - Verify Python 3.10+ and install dev extras (`pytest`, `ruff`, `mypy`)
  - Run a trivial test to confirm your setup

Recommended: Real Python venv guide, or the official Python venv docs.

### 1) Model the game as an environment
- Outcome: A minimal Tic-Tac-Toe environment with a clear API
- Learn before:
  - Tic-Tac-Toe rules, terminal states, legal actions
  - State representations (9-cell board), action space (0–8)
  - Optional: Gymnasium-style interfaces (`reset`, `step`, `render`)
- Practice:
  - Implement `TicTacToeEnv` with:
    - `reset() -> state`
    - `step(action) -> next_state, reward, done, info`
    - `legal_actions(state)` and `is_terminal(state)` helpers
  - Decide on rewards: +1 win, -1 loss, 0 draw; penalize invalid moves
  - Add unit tests for win and draw detection and legal action handling

Resources: Gymnasium API overview, simple board game tutorials.

### 2) Baselines: random and heuristic agents
- Outcome: Non-learning opponents to measure progress
- Learn before:
  - Greedy heuristics (center > corners > sides), rule-based play
  - Optional: Minimax for perfect play (useful as an oracle)
- Practice:
  - Implement `RandomAgent` and a simple `HeuristicAgent`
  - (Optional) `MinimaxAgent` for a reference-perfect opponent
  - Evaluate random vs heuristic to confirm expectations

### 3) Tabular Q-learning
- Outcome: A learning agent that improves over time
- Learn before:
  - MDPs, value functions, Bellman optimality
  - Epsilon-greedy exploration, on and off-policy
  - Q-learning update: Q(s,a) <- Q(s,a) + alpha * [r + gamma * max_{a_next} Q(s_next,a_next) - Q(s,a)]
- Practice:
  - Encode states (for example, tuple or string). Consider symmetry reduction (rotations and reflections)
  - Maintain q_values: Dict[state, np.ndarray(9)] initialized to zeros
  - Implement training loop vs `RandomAgent` then vs `HeuristicAgent`
  - Use epsilon decay, learning rate schedule, and fixed gamma (for example, 0.95)
  - Save best policies and plot learning curves (win, draw, loss)

Resources: Sutton and Barto (chapters on tabular methods), David Silver RL lectures.

### 4) Self-play and opponent curriculum
- Outcome: Robust policy not overfit to a single opponent
- Learn before:
  - Self-play concepts, non-stationary opponents, snapshotting
- Practice:
  - Alternate training opponents: random, heuristic, older snapshots of your agent
  - Periodically evaluate vs `MinimaxAgent` (if implemented)
  - Track simple win rates over time

### 5) Variants and improvements (tabular)
- Outcome: Better stability and generalization
- Learn before:
  - SARSA vs Q-learning differences
  - Double Q-learning to reduce overestimation
  - Eligibility traces (SARSA(lambda)) conceptually
- Practice:
  - Try SARSA; compare learning speed and final performance
  - Try Double Q-learning
  - Tune epsilon schedules and reward shaping (for example, small step penalty)

### 6) Function approximation (optional in Tic-Tac-Toe)
- Outcome: Exposure to approximators even if not needed here
- Learn before:
  - Feature engineering for boards (one-hot planes), overfitting risks
  - Basics of DQN: target networks, replay buffers
- Practice:
  - Implement a tiny linear or MLP value approximator
  - (Optional) Minimal DQN; validate it does not regress vs tabular

### 7) Evaluation, logging, and reproducibility
- Outcome: Trustworthy results and repeatable experiments
- Learn before:
  - Random seeding, metric design, plots
- Practice:
  - Deterministic eval runs (fixed seeds, fixed opponents)
  - Log metrics (CSV or JSON) and plot curves in `notebooks/`
  - Save artifacts: Q-tables, hyperparameters, seed values

---

## Suggested timeline

- Day 1 to 2: Steps 0 to 1 (env plus tests)
- Day 3: Step 2 (baselines)
- Day 4 to 5: Step 3 (tabular Q-learning plus curves)
- Day 6: Step 4 (self-play) and Step 5 (variants)
- Day 7+: Step 6 (optional approximators), Step 7 (polish and reproducibility)

## Deliverables checklist

- [ ] `TicTacToeEnv` with tests for win and draw and legality
- [ ] `RandomAgent`, `HeuristicAgent` (and optional `MinimaxAgent`)
- [ ] `QLearningAgent` with training loops
- [ ] Evaluation script: fixed seeds, summary metrics
- [ ] Plots: win, draw, loss vs training steps
- [ ] Saved artifacts: best policy, logs, configs

## Proposed module structure (you will add these as you implement)

- `src/rl_tictactoe/env.py`: TicTacToeEnv
- `src/rl_tictactoe/agents/base.py`: Agent protocol or base class
- `src/rl_tictactoe/agents/random.py`: RandomAgent
- `src/rl_tictactoe/agents/heuristic.py`: HeuristicAgent
- `src/rl_tictactoe/agents/minimax.py`: MinimaxAgent (optional)
- `src/rl_tictactoe/agents/q_learning.py`: QLearningAgent
- `src/rl_tictactoe/train.py`: training loops and experiment entrypoints
- `scripts/train.sh`: convenience wrapper to run training

## Reading list

- Sutton and Barto, Reinforcement Learning: An Introduction (free online)
- David Silver RL course (videos and slides)
- Gymnasium API overview for environment design

## Tips and pitfalls

- Prefer tabular methods first; Tic-Tac-Toe state space is small
- Normalize board symmetries to speed learning and reduce memory
- Always compare vs baselines; do not assume learning is happening
- Seed everything for reproducibility before drawing conclusions

---

Open `notebooks/` and start a simple notebook to visualize learning curves once you log metrics. As you implement each step, check off the deliverables above.
