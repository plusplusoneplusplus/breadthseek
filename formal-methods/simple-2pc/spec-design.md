# TLA+ Spec Design: 2PC Atomic Key Rename

## Overview

This specification models a 2PC-style protocol for atomically renaming a key (`A` → `A'`) across 2 independent KV stores, with coordinator crash recovery and message loss/duplication.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Message duplication** | Messages can be delivered multiple times; all handlers must be idempotent |
| **Message loss** | Messages can be lost; coordinator retransmits on recovery |
| **Value domain** | `{0, 1, 2}` — small finite set for tractable model checking |
| **Lock timeout** | No timeout — locks persist until explicitly released |
| **Lock both keys** | Always lock both `A` and `A'`; fail if `A'` already exists |

---

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `Stores` | `{S1, S2}` | The set of KV stores |
| `Values` | `{0, 1, 2}` | Possible values stored at a key |

---

## State Variables

### Coordinator State

| Variable | Type | Durable | Description |
|----------|------|---------|-------------|
| `coordPhase` | `{idle, preparing, committed, done}` | No | Current phase of the protocol |
| `walCommitted` | `BOOLEAN` | **Yes** | Whether COMMIT is recorded in WAL (survives crash) |
| `locksAcquired` | `SUBSET Stores` | No | Stores that have responded success to `LockReq` |
| `renamesDone` | `SUBSET Stores` | No | Stores that have responded to `RenameReq` |

> **Crash behavior**: On crash, `coordPhase` resets to `idle`, and `locksAcquired`/`renamesDone` reset to `{}`. Only `walCommitted` persists.

### KV Store State (per store `s`)

| Variable | Type | Description |
|----------|------|-------------|
| `storeKey[s]` | `{"A", "A'"}` | Which key currently holds the value |
| `storeValue[s]` | `{0, 1, 2}` | The current value |
| `lockA[s]` | `BOOLEAN` | Whether key `A` is locked |
| `lockAprime[s]` | `BOOLEAN` | Whether key `A'` is locked |

### Messages

| Variable | Type | Description |
|----------|------|-------------|
| `messages` | Set of records | In-flight messages |

> **Duplication model**: Messages remain in the set after processing. Handlers can fire multiple times on the same message, modeling network duplication. `LoseMessage` removes messages to model loss.

---

## Message Types

| Message | Fields | Description |
|---------|--------|-------------|
| `LockReq` | `type, store` | Request to lock `A` and `A'` in store |
| `LockResp` | `type, store, success` | Lock result (`success=FALSE` if `A'` exists or already renamed) |
| `RenameReq` | `type, store` | Request to rename `A` → `A'` |
| `RenameResp` | `type, store` | Confirmation of rename |
| `UnlockReq` | `type, store` | Request to release locks |

---

## Actions

### Coordinator Actions

| Action | Precondition | Effect |
|--------|--------------|--------|
| `SendLockReq(s)` | `coordPhase ∈ {idle, preparing}` | Add `LockReq(s)` to messages; set `coordPhase = preparing` |
| `RecvLockResp(s, success)` | `LockResp(s, success)` in messages, `coordPhase = preparing` | See "Handling `LockResp`" below |
| `DecideCommit` | `coordPhase = preparing`, `locksAcquired = Stores` | Set `walCommitted = TRUE`, `coordPhase = committed` |
| `SendRenameReq(s)` | `coordPhase = committed` | Add `RenameReq(s)` to messages |
| `RecvRenameResp(s)` | `RenameResp(s)` in messages, `coordPhase = committed` | See "Handling `RenameResp`" below |
| `SendUnlockReq(s)` | `coordPhase = done` | Add `UnlockReq(s)` to messages |
| `Abort` | `coordPhase = preparing`, received `LockResp(_, FALSE)` | Set `coordPhase = idle`; send `UnlockReq` to all stores |
| `Crash` | `coordPhase ≠ idle` | Reset volatile state (see crash behavior above) |
| `Recover` | `coordPhase = idle` (after crash) | See "Recovery" section |

#### Handling `LockResp` (with duplicate detection)

```
RecvLockResp(s, success):
    if s ∈ locksAcquired:
        \* Duplicate response — ignore
        skip
    else if success = FALSE:
        \* Lock failed — abort
        Abort
    else:
        \* New successful response
        locksAcquired = locksAcquired ∪ {s}
```

#### Handling `RenameResp` (with duplicate detection)

```
RecvRenameResp(s):
    if s ∈ renamesDone:
        \* Duplicate response — ignore
        skip
    else:
        renamesDone = renamesDone ∪ {s}
        if renamesDone = Stores:
            coordPhase = done
```

### KV Store Actions

All handlers are **idempotent** to handle message duplication:

| Action | Behavior |
|--------|----------|
| `HandleLockReq(s)` | See detailed logic below |
| `HandleRenameReq(s)` | See detailed logic below |
| `HandleUnlockReq(s)` | Release locks if held; no-op otherwise; no response |

#### Handling `LockReq` (idempotent)

```
HandleLockReq(s):
    if storeKey[s] = "A'":
        \* Already renamed — lock fails
        send LockResp(s, FALSE)
    else if lockA[s] = TRUE:
        \* Already locked — idempotent success
        send LockResp(s, TRUE)
    else:
        \* Acquire locks
        lockA[s] = TRUE
        lockAprime[s] = TRUE
        send LockResp(s, TRUE)
```

#### Handling `RenameReq` (idempotent)

```
HandleRenameReq(s):
    if storeKey[s] = "A'":
        \* Already renamed — idempotent success
        send RenameResp(s)
    else if lockA[s] = TRUE:
        \* Perform rename (value preserved)
        storeKey[s] = "A'"
        send RenameResp(s)
    else:
        \* Not locked — should not happen in correct protocol
        \* Ignore or error
```

#### Handling `UnlockReq` (idempotent)

```
HandleUnlockReq(s):
    lockA[s] = FALSE
    lockAprime[s] = FALSE
    \* No response — fire and forget
```

### Environment Actions

| Action | Description |
|--------|-------------|
| `LoseMessage(m)` | Remove message `m` from `messages` |
| `UpdateValue(s, v)` | If `lockA[s] = FALSE`: set `storeValue[s] = v` |

---

## Protocol Flow (Happy Path)

```
┌─────────────┐                    ┌─────────┐  ┌─────────┐
│ Coordinator │                    │ Store 1 │  │ Store 2 │
└──────┬──────┘                    └────┬────┘  └────┬────┘
       │                                │            │
       │──── LockReq ──────────────────>│            │
       │──── LockReq ───────────────────────────────>│
       │                                │            │
       │<─── LockResp(success) ─────────│            │
       │<─── LockResp(success) ──────────────────────│
       │                                │            │
       │  [Write COMMIT to WAL]         │            │
       │                                │            │
       │──── RenameReq ────────────────>│            │
       │──── RenameReq ─────────────────────────────>│
       │                                │            │
       │<─── RenameResp ────────────────│            │
       │<─── RenameResp ─────────────────────────────│
       │                                │            │
       │──── UnlockReq ────────────────>│            │
       │──── UnlockReq ─────────────────────────────>│
       │                                │            │
       ▼                                ▼            ▼
    [DONE]                          [A' held]    [A' held]
```

---

## Recovery Scenarios

When coordinator recovers (`coordPhase = idle` after crash):

| WAL State | Recovery Action |
|-----------|-----------------|
| `walCommitted = FALSE` | Send `UnlockReq` to all stores (safe cleanup) |
| `walCommitted = TRUE` | Set `coordPhase = committed`; resend `RenameReq` to all stores |

> **Why this works**:
> - If not committed: Some stores may have locks, some may not. Sending `UnlockReq` to all is safe (idempotent).
> - If committed: Some stores may have renamed, some may not. Resending `RenameReq` to all is safe (idempotent). Coordinator rebuilds `renamesDone` from responses.

---

## Idempotency Summary

| Component | Message | Duplicate Handling |
|-----------|---------|-------------------|
| **KV Store** | `LockReq` | Already locked → respond success |
| **KV Store** | `RenameReq` | Already `A'` → respond success |
| **KV Store** | `UnlockReq` | Not locked → no-op |
| **Coordinator** | `LockResp` | `s ∈ locksAcquired` → ignore |
| **Coordinator** | `RenameResp` | `s ∈ renamesDone` → ignore |

---

## Safety Invariants

### 1. Data Always Accessible

```tla
DataAccessible == ∀ s ∈ Stores : storeKey[s] ∈ {"A", "A'"}
```

Each store always has exactly one valid key — data is never in limbo.

### 2. No Rename Without Commit

```tla
NoRenameWithoutCommit == ~walCommitted ⇒ ∀ s ∈ Stores : storeKey[s] = "A"
```

If the coordinator has not committed, no store should have renamed. This holds because:
- `RenameReq` is only sent when `coordPhase = committed`
- `coordPhase = committed` requires `walCommitted = TRUE`
- Therefore: no commit ⇒ no rename ever sent ⇒ all stores have `A`

### 3. Commit Consistency

```tla
CommitConsistency == coordPhase = "done" ⇒ ∀ s ∈ Stores : storeKey[s] = "A'"
```

If coordinator believes rename is complete, all stores have `A'`.

### 4. Rename Implies Commit

```tla
RenameImpliesCommit == ∀ s ∈ Stores : storeKey[s] = "A'" ⇒ walCommitted
```

If any store has renamed to `A'`, then the coordinator must have committed. (Contrapositive of `NoRenameWithoutCommit`.)

### 5. Committed Phase Implies WAL

```tla
CommittedImpliesWal == coordPhase = "committed" ⇒ walCommitted
```

The coordinator can only be in the `committed` phase if the WAL commit was recorded. This ensures the phase is consistent with durable state.

### 6. Lock Protects Updates

```tla
LockProtectsUpdates == ∀ s ∈ Stores : lockA[s] ⇒ storeValue[s] = storeValue[s]
```

While locked, external updates cannot modify the value. (Enforced by `UpdateValue` precondition; this invariant is trivially true but documents the intent.)

---

## Liveness Properties

### Fairness Assumptions

Liveness requires the following fairness assumptions:

| Assumption | Description |
|------------|-------------|
| **Weak fairness on coordinator actions** | If a coordinator action is continuously enabled, it eventually executes |
| **Weak fairness on store handlers** | If a message can be processed, it eventually is |
| **Message eventual delivery** | Messages are not lost forever; retransmission eventually succeeds |
| **Coordinator eventual recovery** | If the coordinator crashes, it eventually recovers |

### 1. Eventually Stable

```tla
EventuallyStable == <>(
    \* Aborted/Not-started: clean initial state
    (coordPhase = "idle" /\ ~walCommitted /\
     \A s \in Stores: storeKey[s] = "A" /\ ~lockA[s] /\ ~lockAprime[s])
  \/
    \* Committed/Done: clean final state
    (coordPhase = "done" /\ walCommitted /\
     \A s \in Stores: storeKey[s] = "A'")
)
```

The system eventually reaches one of two terminal states:
- **Not-started/Aborted:** No commit recorded, all stores at key `A`, no locks held
- **Committed/Done:** Commit recorded, all stores renamed to `A'`, protocol complete

### 2. Committed Implies Eventually Done

```tla
CommittedImpliesEventuallyDone == walCommitted ~> (coordPhase = "done")
```

If the coordinator commits (writes to WAL), the protocol eventually completes. This ensures no permanent partial-commit state.

### 3. No Permanent Locks

```tla
NoPermanentLocks == \A s \in Stores: lockA[s] ~> ~lockA[s]
```

Any lock that is acquired is eventually released. Locks do not persist indefinitely.

---

## Non-Goals (Not Modeled)

- KV store crashes (only coordinator crashes)
- Concurrent `get`/`put` during rename (only `UpdateValue` when unlocked)
- More than 2 stores (easily generalizable)

---

## Next Steps

1. Review this design
2. Implement TLA+ spec
3. Run TLC model checker
4. Verify safety invariants hold
