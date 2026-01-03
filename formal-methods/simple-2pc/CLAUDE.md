# Simple 2PC: Atomic Key Rename Protocol

A formally verified implementation of a Two-Phase Commit (2PC) protocol for atomically renaming a key across multiple independent KV stores.

## Problem

A coordinator service needs to rename a key (`A` → `A'`) across multiple KV stores atomically, ensuring:
- No data loss during transition
- No updates lost around the rename
- No mixed steady state (some stores at `A`, others at `A'`)
- Tolerance for coordinator crashes, KV store crashes, and network issues

See [statement.md](statement.md) for the full problem specification.

## Project Structure

```
simple-2pc/
├── statement.md          # Problem statement and requirements
├── spec-design.md        # TLA+ specification design document
├── AtomicRename.tla      # TLA+ formal specification
├── AtomicRename.cfg      # TLC model checker configuration
└── impl/                 # Verus verified Rust implementation
    └── src/
        ├── kv_store_s.rs     # KV store spec layer (ghost)
        ├── kv_store_v.rs     # KV store verified executable
        ├── network_s.rs      # Network spec layer (ghost)
        ├── network_v.rs      # Network verified executable
        ├── coordinator_s.rs  # Coordinator spec layer (ghost)
        ├── coordinator_v.rs  # Coordinator verified executable
        ├── system_s.rs       # System composition spec
        └── system_v.rs       # System driver executable
```

## Protocol Overview

### Phase 1: Prepare (Lock)
1. Coordinator sends `LockReq` to all stores
2. Each store locks keys `A` and `A'`, responds with success/failure
3. If any lock fails → abort and cleanup

### Phase 2: Commit (Rename)
1. Write `COMMIT` to coordinator WAL (durable)
2. Send `RenameReq` to all stores
3. After all renames complete → cleanup (unlock all)

Key mechanisms:
- **Transaction IDs**: Prevent stale messages from old attempts after crash recovery
- **Idempotent handlers**: All operations are safe to retry
- **WAL-based recovery**: Resume correctly after coordinator crash

See [spec-design.md](spec-design.md) for detailed design and invariants.

## Verification

### TLA+ Model Checking
```bash
# Run TLC model checker (from project root)
tlc AtomicRename.tla -config AtomicRename.cfg
```

### Verus Proof Verification
```bash
# From the impl/ directory
cd impl
../../verus/cargo-verus verify
```

The Verus implementation uses a layered architecture:
- `*_s.rs` modules: Specification layer with ghost types and lemmas
- `*_v.rs` modules: Verified executable implementations

## Safety Invariants

1. **Data Always Accessible**: Each store always has exactly one valid key
2. **No Rename Without Commit**: If not committed, all stores have key `A`
3. **Commit Consistency**: If done with commit, all stores have key `A'`
4. **No Permanent Locks**: All acquired locks are eventually released

## Liveness Properties

- **Eventually Done**: The protocol always terminates
- **Committed Implies Done**: If WAL commit is recorded, rename completes
