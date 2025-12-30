# Problem Statement: Atomic Key Rename Across Multiple KV Stores

## Setup

There are multiple independent KV stores (e.g., Store X, Store Y, Store Z). A coordinator service (WAL-backed state machine) depends on these stores and reads/updates a single key in each store.

- **Old key:** `A`
- **New key:** `A'`

Each store contains one entry for this coordinator under key `A` (value can change over time due to updates).

---

## KV Store API

Each KV store provides:

| Operation | Description |
|-----------|-------------|
| `lock(key)` / `unlock(key)` | Provides mutual exclusion for operations involving that key |
| `rename(old_key, new_key)` | Atomically renames the key within that store (moves the value and metadata from `old_key` to `new_key` in one atomic step) |

> Stores also support normal `get`/`put` for reads and updates.

---

## Goal

Upgrade the coordinator to use `A'` instead of `A` across all KV stores, such that:

1. **No data is missed:** During the transition, the coordinator must never be unable to find the value because it is "between" `A` and `A'`.
2. **No updates are lost:** Updates happening around the rename must not disappear or get overwritten incorrectly.
3. **No mixed steady state:** The system should not end up permanently with some stores using `A` while others use `A'`.

---

## Failure Model

The protocol must tolerate:

- Coordinator crash/restart
- KV store crash/restart
- Network loss/duplication/delay

> **Note:** No cross-store transactions exist; each store's `rename()` is atomic only within that store.

---

## 2PC-Style Rename

The coordinator implements a 2PC-like protocol using the available API:

### Phase 1: Prepare (Lock)

1. For every store `S`: call `S.lock("A")` (optionally also `S.lock("A'")` to reserve the target)
2. If any lock fails, abort and unlock what was acquired

### Phase 2: Commit (Rename)

1. Record `COMMIT` durably in the coordinator WAL
2. For every store `S`: call `S.rename("A", "A'")`
3. Unlock keys

### Abort

- Unlock any acquired locks and keep using `A`

---

## Recovery Requirement

After a crash, the coordinator uses its WAL to decide:

| WAL State | Recovery Action |
|-----------|-----------------|
| Commit **not** recorded | Ensure locks are released and continue with `A` |
| Commit recorded | Retry remaining `rename(A, A')` until all stores complete, then use `A'` |
