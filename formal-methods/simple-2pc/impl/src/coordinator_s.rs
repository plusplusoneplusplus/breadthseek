// coordinator_s.rs - Specification layer for Coordinator
//
// This file contains:
// - CoordPhase: enum for coordinator phases
// - CoordinatorSpec: ghost struct for verification
// - Spec functions for state transitions
// - Proof lemmas for coordinator properties
//
// Matches TLA+ spec: coordPhase, currentTxnId, walCommitted, locksAcquired, renamesDone, unlocksAcked

use vstd::prelude::*;
use crate::network_s::*;

verus! {

// ============================================================
// COORDINATOR PHASE
// ============================================================

/// Coordinator phase enum - matches TLA+ spec
/// {idle, preparing, committed, cleanup, done, crashed}
///
/// This is a regular (non-ghost) enum that can be used in both spec and exec contexts.
/// No need for a separate ExecCoordPhase - this single enum serves both purposes.
#[derive(PartialEq, Eq, Clone, Copy)]
pub enum CoordPhase {
    /// Initial state, not started
    Idle,
    /// Sending lock requests, waiting for responses
    Preparing,
    /// WAL committed, sending rename requests
    Committed,
    /// Sending unlock requests (after abort or after all renames done)
    Cleanup,
    /// Terminal state - protocol complete
    Done,
    /// Coordinator crashed - volatile state lost
    Crashed,
}

impl CoordPhase {
    /// Check if coordinator can crash in this phase (spec function)
    pub open spec fn spec_can_crash(&self) -> bool {
        match *self {
            CoordPhase::Preparing => true,
            CoordPhase::Committed => true,
            CoordPhase::Cleanup => true,
            _ => false,
        }
    }

    /// Check if coordinator can crash in this phase (exec function)
    pub fn can_crash(&self) -> (result: bool)
        ensures
            result == self.spec_can_crash()
    {
        match *self {
            CoordPhase::Preparing => true,
            CoordPhase::Committed => true,
            CoordPhase::Cleanup => true,
            _ => false,
        }
    }

    /// Check if this is a terminal state (spec function)
    pub open spec fn spec_is_terminal(&self) -> bool {
        match *self {
            CoordPhase::Done => true,
            _ => false,
        }
    }

    /// Check if this is a terminal state (exec function)
    pub fn is_terminal(&self) -> (result: bool)
        ensures
            result == self.spec_is_terminal()
    {
        match *self {
            CoordPhase::Done => true,
            _ => false,
        }
    }

    /// Check if coordinator is active (not crashed or done) (spec function)
    pub open spec fn spec_is_active(&self) -> bool {
        match *self {
            CoordPhase::Idle => true,
            CoordPhase::Preparing => true,
            CoordPhase::Committed => true,
            CoordPhase::Cleanup => true,
            _ => false,
        }
    }

    /// Check if coordinator is active (exec function)
    pub fn is_active(&self) -> (result: bool)
        ensures
            result == self.spec_is_active()
    {
        match *self {
            CoordPhase::Idle => true,
            CoordPhase::Preparing => true,
            CoordPhase::Committed => true,
            CoordPhase::Cleanup => true,
            _ => false,
        }
    }
}

// ============================================================
// COORDINATOR SPEC
// ============================================================

/// Spec-level coordinator state (ghost/proof only)
/// Matches TLA+ coordinator variables
pub ghost struct CoordinatorSpec {
    // ===== Durable state (survives crash) =====
    /// Transaction ID for current protocol attempt (incremented on recovery)
    pub current_txn_id: TxnId,
    /// Whether COMMIT is recorded in WAL
    pub wal_committed: bool,

    // ===== Volatile state (lost on crash) =====
    /// Current phase of the protocol
    pub phase: CoordPhase,
    /// Stores that have responded success to LockReq
    pub locks_acquired: Set<StoreId>,
    /// Stores that have responded to RenameReq
    pub renames_done: Set<StoreId>,
    /// Stores that have responded to UnlockReq
    pub unlocks_acked: Set<StoreId>,
}

impl CoordinatorSpec {
    // ============================================================
    // SPEC FUNCTIONS - State observations
    // ============================================================

    /// Get current transaction ID
    pub open spec fn get_txn_id(&self) -> TxnId {
        self.current_txn_id
    }

    /// Check if WAL is committed
    pub open spec fn is_committed(&self) -> bool {
        self.wal_committed
    }

    /// Get current phase
    pub open spec fn get_phase(&self) -> CoordPhase {
        self.phase
    }

    /// Check if a store has acquired lock
    pub open spec fn has_lock(&self, store: StoreId) -> bool {
        self.locks_acquired.contains(store)
    }

    /// Check if a store has completed rename
    pub open spec fn has_renamed(&self, store: StoreId) -> bool {
        self.renames_done.contains(store)
    }

    /// Check if a store has acknowledged unlock
    pub open spec fn has_unlocked(&self, store: StoreId) -> bool {
        self.unlocks_acked.contains(store)
    }

    /// Check if all stores have acquired locks
    pub open spec fn all_locks_acquired(&self, stores: Set<StoreId>) -> bool {
        self.locks_acquired == stores
    }

    /// Check if all stores have completed rename
    pub open spec fn all_renames_done(&self, stores: Set<StoreId>) -> bool {
        self.renames_done == stores
    }

    /// Check if all stores have acknowledged unlock
    pub open spec fn all_unlocks_acked(&self, stores: Set<StoreId>) -> bool {
        self.unlocks_acked == stores
    }

    // ============================================================
    // SPEC FUNCTIONS - State transitions
    // ============================================================

    /// Create initial coordinator state
    pub open spec fn init() -> Self {
        CoordinatorSpec {
            current_txn_id: 1,
            wal_committed: false,
            phase: CoordPhase::Idle,
            locks_acquired: Set::empty(),
            renames_done: Set::empty(),
            unlocks_acked: Set::empty(),
        }
    }

    /// Send lock request - transitions to Preparing phase
    /// Returns (new_state, message_to_send)
    pub open spec fn send_lock_req(self, store: StoreId) -> (Self, Message)
        recommends
            self.phase == CoordPhase::Idle || self.phase == CoordPhase::Preparing
    {
        let new_state = CoordinatorSpec {
            phase: CoordPhase::Preparing,
            ..self
        };
        let msg = lock_req_msg(store, self.current_txn_id);
        (new_state, msg)
    }

    /// Receive successful lock response
    pub open spec fn recv_lock_resp_success(self, store: StoreId) -> Self
        recommends
            self.phase == CoordPhase::Preparing,
            !self.locks_acquired.contains(store),
    {
        CoordinatorSpec {
            locks_acquired: self.locks_acquired.insert(store),
            ..self
        }
    }

    /// Receive failed lock response - transition to cleanup
    pub open spec fn recv_lock_resp_failure(self) -> Self
        recommends
            self.phase == CoordPhase::Preparing
    {
        CoordinatorSpec {
            phase: CoordPhase::Cleanup,
            locks_acquired: Set::empty(),
            renames_done: Set::empty(),
            unlocks_acked: Set::empty(),
            ..self
        }
    }

    /// Decide to commit (all locks acquired)
    pub open spec fn decide_commit(self) -> Self
        recommends
            self.phase == CoordPhase::Preparing
    {
        CoordinatorSpec {
            wal_committed: true,
            phase: CoordPhase::Committed,
            ..self
        }
    }

    /// Send rename request
    /// Returns (new_state, message_to_send)
    pub open spec fn send_rename_req(self, store: StoreId) -> (Self, Message)
        recommends
            self.phase == CoordPhase::Committed
    {
        let msg = rename_req_msg(store, self.current_txn_id);
        (self, msg)
    }

    /// Receive rename response
    pub open spec fn recv_rename_resp(self, store: StoreId, all_stores: Set<StoreId>) -> Self
        recommends
            self.phase == CoordPhase::Committed,
            !self.renames_done.contains(store),
    {
        let new_renames = self.renames_done.insert(store);
        let new_phase = if new_renames == all_stores {
            CoordPhase::Cleanup
        } else {
            self.phase
        };
        CoordinatorSpec {
            phase: new_phase,
            renames_done: new_renames,
            ..self
        }
    }

    /// Send unlock request
    /// Returns (new_state, message_to_send)
    pub open spec fn send_unlock_req(self, store: StoreId) -> (Self, Message)
        recommends
            self.phase == CoordPhase::Cleanup
    {
        let msg = unlock_req_msg(store, self.current_txn_id);
        (self, msg)
    }

    /// Receive unlock response
    pub open spec fn recv_unlock_resp(self, store: StoreId, all_stores: Set<StoreId>) -> Self
        recommends
            self.phase == CoordPhase::Cleanup,
            !self.unlocks_acked.contains(store),
    {
        let new_unlocks = self.unlocks_acked.insert(store);
        let new_phase = if new_unlocks == all_stores {
            CoordPhase::Done
        } else {
            self.phase
        };
        CoordinatorSpec {
            phase: new_phase,
            unlocks_acked: new_unlocks,
            ..self
        }
    }

    /// Coordinator crash - reset volatile state, keep durable state
    pub open spec fn crash(self) -> Self
        recommends
            self.phase.spec_can_crash()
    {
        CoordinatorSpec {
            // Durable state preserved
            current_txn_id: self.current_txn_id,
            wal_committed: self.wal_committed,
            // Volatile state lost
            phase: CoordPhase::Crashed,
            locks_acquired: Set::empty(),
            renames_done: Set::empty(),
            unlocks_acked: Set::empty(),
        }
    }

    /// Coordinator recover - increment txn_id, resume based on WAL
    pub open spec fn recover(self) -> Self
        recommends
            self.phase == CoordPhase::Crashed
    {
        let new_txn_id = self.current_txn_id + 1;
        if self.wal_committed {
            // Committed - resume commit phase
            CoordinatorSpec {
                current_txn_id: new_txn_id,
                wal_committed: self.wal_committed,
                phase: CoordPhase::Committed,
                locks_acquired: Set::empty(),
                renames_done: Set::empty(),
                unlocks_acked: Set::empty(),
            }
        } else {
            // Not committed - go to cleanup
            CoordinatorSpec {
                current_txn_id: new_txn_id,
                wal_committed: self.wal_committed,
                phase: CoordPhase::Cleanup,
                locks_acquired: Set::empty(),
                renames_done: Set::empty(),
                unlocks_acked: Set::empty(),
            }
        }
    }

    // ============================================================
    // PROOF LEMMAS - Properties of coordinator
    // ============================================================

    /// Crash preserves durable state
    pub proof fn lemma_crash_preserves_durable(self)
        requires
            self.phase.spec_can_crash()
        ensures
            self.crash().current_txn_id == self.current_txn_id,
            self.crash().wal_committed == self.wal_committed,
    {
    }

    /// Recovery increments txn_id
    pub proof fn lemma_recover_increments_txn_id(self)
        requires
            self.phase == CoordPhase::Crashed
        ensures
            self.recover().current_txn_id == self.current_txn_id + 1,
    {
    }

    /// Recovery preserves wal_committed
    pub proof fn lemma_recover_preserves_wal(self)
        requires
            self.phase == CoordPhase::Crashed
        ensures
            self.recover().wal_committed == self.wal_committed,
    {
    }

    /// Committed recovery goes to Committed phase
    pub proof fn lemma_recover_committed_phase(self)
        requires
            self.phase == CoordPhase::Crashed,
            self.wal_committed,
        ensures
            self.recover().phase == CoordPhase::Committed,
    {
    }

    /// Non-committed recovery goes to Cleanup phase
    pub proof fn lemma_recover_not_committed_phase(self)
        requires
            self.phase == CoordPhase::Crashed,
            !self.wal_committed,
        ensures
            self.recover().phase == CoordPhase::Cleanup,
    {
    }

    /// Decide commit sets wal_committed
    pub proof fn lemma_decide_commit_sets_wal(self)
        requires
            self.phase == CoordPhase::Preparing
        ensures
            self.decide_commit().wal_committed,
            self.decide_commit().phase == CoordPhase::Committed,
    {
    }

    /// Lock response success adds store to locks_acquired
    pub proof fn lemma_lock_resp_adds_store(self, store: StoreId)
        requires
            self.phase == CoordPhase::Preparing,
            !self.locks_acquired.contains(store),
        ensures
            self.recv_lock_resp_success(store).locks_acquired.contains(store),
    {
    }

    /// Lock response failure transitions to cleanup
    pub proof fn lemma_lock_failure_to_cleanup(self)
        requires
            self.phase == CoordPhase::Preparing
        ensures
            self.recv_lock_resp_failure().phase == CoordPhase::Cleanup,
    {
    }
}

// ============================================================
// PROTOCOL INVARIANTS
// ============================================================

/// Committed phase implies WAL committed
pub open spec fn committed_implies_wal(coord: CoordinatorSpec) -> bool {
    coord.phase == CoordPhase::Committed ==> coord.wal_committed
}

/// Done phase with wal_committed means successful completion
pub open spec fn done_means_success(coord: CoordinatorSpec) -> bool {
    (coord.phase == CoordPhase::Done && coord.wal_committed) ==>
        coord.all_renames_done(coord.renames_done)
}

/// Lemma: decide_commit establishes committed_implies_wal invariant
pub proof fn lemma_decide_commit_invariant(coord: CoordinatorSpec)
    requires
        coord.phase == CoordPhase::Preparing
    ensures
        committed_implies_wal(coord.decide_commit()),
{
}

} // verus!

