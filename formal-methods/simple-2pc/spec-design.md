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
| **Transaction ID** | Each protocol attempt has a unique `txnId`; stores reject old txnIds to prevent stale message interference after crash recovery |

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
| `currentTxnId` | `Nat` | **Yes** | Transaction ID for current protocol attempt (incremented on recovery) |
| `coordPhase` | `{idle, preparing, committed, cleanup, done, crashed}` | No | Current phase of the protocol |
| `walCommitted` | `BOOLEAN` | **Yes** | Whether COMMIT is recorded in WAL (survives crash) |
| `locksAcquired` | `SUBSET Stores` | No | Stores that have responded success to `LockReq` |
| `renamesDone` | `SUBSET Stores` | No | Stores that have responded to `RenameReq` |
| `unlocksAcked` | `SUBSET Stores` | No | Stores that have responded to `UnlockReq` |

> **Crash behavior**: On crash, `coordPhase` transitions to `crashed`, and `locksAcquired`/`renamesDone`/`unlocksAcked` reset to `{}`. Durable state (`currentTxnId`, `walCommitted`) persists.

### KV Store State (per store `s`)

| Variable | Type | Description |
|----------|------|-------------|
| `storeKey[s]` | `{"A", "A'"}` | Which key currently holds the value |
| `storeValue[s]` | `{0, 1, 2}` | The current value |
| `lockA[s]` | `BOOLEAN` | Whether key `A` is locked |
| `lockAprime[s]` | `BOOLEAN` | Whether key `A'` is locked |
| `lastSeenTxnId[s]` | `Nat` | Highest transaction ID seen (rejects lower ones) |

### Messages

| Variable | Type | Description |
|----------|------|-------------|
| `messages` | Set of records | In-flight messages |

> **Duplication model**: Messages remain in the set after processing. Handlers can fire multiple times on the same message, modeling network duplication. `LoseMessage` removes messages to model loss.

---

## Message Types

All messages include a `txnId` field to prevent stale messages from old transactions being processed after recovery.

| Message | Fields | Description |
|---------|--------|-------------|
| `LockReq` | `type, store, txnId` | Request to lock `A` and `A'` in store |
| `LockResp` | `type, store, success, txnId` | Lock result (`success=FALSE` if `A'` exists or already renamed) |
| `RenameReq` | `type, store, txnId` | Request to rename `A` → `A'` |
| `RenameResp` | `type, store, txnId` | Confirmation of rename |
| `UnlockReq` | `type, store, txnId` | Request to release locks |
| `UnlockResp` | `type, store, txnId` | Confirmation of unlock |

> **Transaction ID mechanism**: Stores track the highest `txnId` they've seen in `lastSeenTxnId[s]`. When a message arrives with `txnId < lastSeenTxnId[s]`, it is silently rejected. This prevents old in-flight messages from interfering after coordinator crash/recovery.

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
| `SendUnlockReq(s)` | `coordPhase = cleanup` | Add `UnlockReq(s)` to messages |
| `RecvUnlockResp(s)` | `UnlockResp(s)` in messages, `coordPhase = cleanup` | See "Handling `UnlockResp`" below |
| `Abort` | `coordPhase = preparing`, received `LockResp(_, FALSE)` | Set `coordPhase = cleanup` |
| `Crash` | `coordPhase ∉ {idle, done}` | Reset volatile state (see crash behavior above) |
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
            coordPhase = cleanup  \* Go to cleanup to release locks
```

#### Handling `UnlockResp` (with duplicate detection)

```
RecvUnlockResp(s):
    if s ∈ unlocksAcked:
        \* Duplicate response — ignore
        skip
    else:
        unlocksAcked = unlocksAcked ∪ {s}
        if unlocksAcked = Stores:
            coordPhase = done
```

### KV Store Actions

All handlers are **idempotent** to handle message duplication and **reject stale txnIds**:

| Action | Behavior |
|--------|----------|
| `HandleLockReq(s)` | See detailed logic below |
| `HandleRenameReq(s)` | See detailed logic below |
| `HandleUnlockReq(s)` | Release locks if held; no-op otherwise; always send `UnlockResp` |

> **Stale message rejection**: All handlers first check if `msg.txnId < lastSeenTxnId[s]`. If so, the message is silently discarded. Otherwise, `lastSeenTxnId[s]` is updated to `msg.txnId`.

#### Handling `LockReq` (idempotent, rejects old txnId)

```
HandleLockReq(s, msg):
    if msg.txnId < lastSeenTxnId[s]:
        \* OLD transaction — reject silently
        discard msg
    else:
        lastSeenTxnId[s] = msg.txnId
        if storeKey[s] = "A'":
            \* Already renamed — lock fails
            send LockResp(s, FALSE, msg.txnId)
        else if lockA[s] = TRUE:
            \* Already locked — idempotent success
            send LockResp(s, TRUE, msg.txnId)
        else:
            \* Acquire locks
            lockA[s] = TRUE
            lockAprime[s] = TRUE
            send LockResp(s, TRUE, msg.txnId)
```

#### Handling `RenameReq` (idempotent, rejects old txnId)

```
HandleRenameReq(s, msg):
    if msg.txnId < lastSeenTxnId[s]:
        \* OLD transaction — reject silently
        discard msg
    else:
        lastSeenTxnId[s] = msg.txnId
        if storeKey[s] = "A'":
            \* Already renamed — idempotent success
            send RenameResp(s, msg.txnId)
        else if lockA[s] = TRUE:
            \* Perform rename (value preserved)
            storeKey[s] = "A'"
            send RenameResp(s, msg.txnId)
        else:
            \* Not locked — should not happen in correct protocol
            \* Ignore or error
```

#### Handling `UnlockReq` (idempotent, rejects old txnId)

```
HandleUnlockReq(s, msg):
    if msg.txnId < lastSeenTxnId[s]:
        \* OLD transaction — reject silently
        discard msg
    else:
        lastSeenTxnId[s] = msg.txnId
        lockA[s] = FALSE
        lockAprime[s] = FALSE
        send UnlockResp(s, msg.txnId)
```

### Environment Actions

| Action | Description |
|--------|-------------|
| `LoseMessage(m)` | Remove message `m` from `messages` |
| `UpdateValue(s, v)` | If `lockA[s] = FALSE`: set `storeValue[s] = v` |

---

## Protocol Flow (Success Path)

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
       │  [Enter CLEANUP phase]         │            │
       │                                │            │
       │──── UnlockReq ────────────────>│            │
       │──── UnlockReq ─────────────────────────────>│
       │                                │            │
       │<─── UnlockResp ────────────────│            │
       │<─── UnlockResp ─────────────────────────────│
       │                                │            │
       │  [All unlocks confirmed]       │            │
       │                                │            │
       ▼                                ▼            ▼
    [DONE]                          [A' held]    [A' held]
   (walCommitted)                   (unlocked)   (unlocked)
```

## Protocol Flow (Abort Path)

```
┌─────────────┐                    ┌─────────┐  ┌─────────┐
│ Coordinator │                    │ Store 1 │  │ Store 2 │
└──────┬──────┘                    └────┬────┘  └────┬────┘
       │                                │            │
       │──── LockReq ──────────────────>│            │
       │──── LockReq ───────────────────────────────>│
       │                                │            │
       │<─── LockResp(success) ─────────│            │
       │<─── LockResp(FAIL) ─────────────────────────│
       │                                │            │
       │  [Enter CLEANUP phase]         │            │
       │                                │            │
       │──── UnlockReq ────────────────>│            │
       │──── UnlockReq ─────────────────────────────>│
       │                                │            │
       │<─── UnlockResp ────────────────│            │
       │<─── UnlockResp ─────────────────────────────│
       │                                │            │
       │  [All unlocks confirmed]       │            │
       │                                │            │
       ▼                                ▼            ▼
    [DONE]                          [A held]     [A held]
   (~walCommitted)                  (unlocked)   (unlocked)
```

> **Note:** Both paths use the same `cleanup` → `done` transition. The coordinator waits for all `UnlockResp` before transitioning to `done`, ensuring locks are fully released. The outcome differs based on `walCommitted`: success path has all stores at `A'`, abort path has all stores at `A`.

---

## Recovery Scenarios

When coordinator recovers (`coordPhase = crashed` after crash):

**Key step: Increment `currentTxnId`** — This invalidates all old in-flight messages, preventing stale messages from the aborted attempt from interfering with the new recovery attempt.

| WAL State | Recovery Action |
|-----------|-----------------|
| `walCommitted = FALSE` | Increment `currentTxnId`; set `coordPhase = cleanup`; send `UnlockReq` (with new txnId) to all stores |
| `walCommitted = TRUE` | Increment `currentTxnId`; set `coordPhase = committed`; resend `RenameReq` (with new txnId) to all stores |

> **Why this works**:
> - **Transaction ID prevents stale message interference**: After recovery, old in-flight messages (e.g., delayed `LockReq` from the crashed attempt) have a stale `txnId`. Stores reject these because `oldTxnId < lastSeenTxnId[s]` after processing new messages.
> - If not committed: Some stores may have locks, some may not. Entering `cleanup` phase and sending `UnlockReq` to all is safe (idempotent). Coordinator collects `UnlockResp` and transitions to `done` when all stores acknowledge.
> - If committed: Some stores may have renamed, some may not. Resending `RenameReq` to all is safe (idempotent). Coordinator rebuilds `renamesDone` from responses.

> **Race condition prevented**: Without txnId, an old `LockReq` delayed in the network could arrive AFTER cleanup completed, causing the store to re-acquire locks while the coordinator believes it's done — leading to deadlock. The txnId mechanism ensures such stale messages are silently ignored.

---

## Idempotency Summary

| Component | Message | Duplicate Handling |
|-----------|---------|-------------------|
| **KV Store** | `LockReq` | Stale txnId → reject; Already locked → respond success |
| **KV Store** | `RenameReq` | Stale txnId → reject; Already `A'` → respond success |
| **KV Store** | `UnlockReq` | Stale txnId → reject; Not locked → no-op, always respond |
| **Coordinator** | `LockResp` | `s ∈ locksAcquired` → ignore |
| **Coordinator** | `RenameResp` | `s ∈ renamesDone` → ignore |
| **Coordinator** | `UnlockResp` | `s ∈ unlocksAcked` → ignore |

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

| Assumption | Type | Description |
|------------|------|-------------|
| **Coordinator send actions** | Weak (WF) | If sending (LockReq, RenameReq, UnlockReq) is continuously enabled, it eventually executes |
| **Coordinator receive actions** | Strong (SF) | If receiving (LockResp, RenameResp, UnlockResp) is enabled infinitely often, it eventually executes |
| **Store handlers** | Strong (SF) | If a handler is enabled infinitely often, it eventually executes |
| **Coordinator recovery** | Weak (WF) | If the coordinator is crashed, it eventually recovers |

> **Why Strong Fairness?** With message loss and retransmission, response messages may be repeatedly lost and re-added to the network. This means receive actions are *intermittently* enabled (not continuously). Strong fairness ensures that if an action is enabled infinitely often, it eventually fires — modeling that retransmission eventually succeeds.

### 1. Eventually Done

```tla
EventuallyDone == <>(coordPhase = "done")
```

The system eventually reaches the `done` terminal state. The outcome depends on `walCommitted`:
- **Aborted (`~walCommitted`):** No commit recorded, all stores at key `A`, no locks held
- **Committed (`walCommitted`):** Commit recorded, all stores renamed to `A'`

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
