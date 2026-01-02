// coordinator_v.rs - Verified executable implementation of Coordinator
//
// This file contains:
// - Coordinator: executable struct
// - View implementation connecting exec to spec
// - Verified exec functions with postconditions
//
// Note: We use CoordPhase directly from coordinator_s.rs - no duplication needed
// since CoordPhase is a regular (non-ghost) enum that works in both spec and exec.
//
// Note: We use a custom SimpleSet instead of vstd::hash_set::HashSetWithView because:
// 1. HashSetWithView requires obeys_key_model::<Key>() which is only proven for primitive types
// 2. Using u64 directly doesn't give us the right View type (Set<u64> vs Set<nat>)
// 3. SimpleSet provides a fully verified set implementation using Vec

use vstd::prelude::*;

use crate::coordinator_s::*;
use crate::network_s::*;

verus! {

// ============================================================
// SIMPLE SET IMPLEMENTATION USING VEC
// ============================================================

/// A simple set implementation using Vec for exec mode
/// This is used because vstd::hash_set::HashSetWithView requires obeys_key_model
/// which is only proven for primitive types, not custom wrappers.
pub struct SimpleSet {
    elements: Vec<u64>,
}

impl View for SimpleSet {
    type V = Set<u64>;

    closed spec fn view(&self) -> Set<u64> {
        Set::new(|x: u64| self.elements@.contains(x))
    }
}

impl SimpleSet {
    pub open spec fn spec_contains(&self, x: u64) -> bool {
        self@.contains(x)
    }

    pub closed spec fn spec_len(&self) -> nat {
        self.elements.len() as nat
    }

    pub fn new() -> (result: Self)
        ensures
            result@ == Set::<u64>::empty()
    {
        SimpleSet { elements: Vec::new() }
    }

    pub fn contains(&self, x: &u64) -> (result: bool)
        ensures
            result == self@.contains(*x)
    {
        let mut i: usize = 0;
        while i < self.elements.len()
            invariant
                0 <= i <= self.elements.len(),
                forall|j: int| 0 <= j < i ==> self.elements@[j] != *x,
            decreases
                self.elements.len() - i,
        {
            if self.elements[i] == *x {
                return true;
            }
            i = i + 1;
        }
        false
    }

    pub fn insert(&mut self, x: u64)
        ensures
            self@.contains(x),
            forall|y: u64| old(self)@.contains(y) ==> self@.contains(y),
    {
        if !self.contains(&x) {
            let ghost old_elements = self.elements@;
            self.elements.push(x);
            proof {
                // After push, x is in the list
                assert(self.elements@.last() == x);
                assert(self.elements@.contains(x));
                // Old elements are preserved
                assert forall|y: u64| old_elements.contains(y) implies self.elements@.contains(y) by {
                    if old_elements.contains(y) {
                        // y was in old list, so it's in new list (push preserves existing elements)
                        let idx = choose|i: int| 0 <= i < old_elements.len() && old_elements[i] == y;
                        assert(self.elements@[idx] == y);
                    }
                }
            }
        }
    }

    pub fn len(&self) -> (result: usize)
        ensures
            result as nat == self.spec_len(),
    {
        self.elements.len()
    }

    pub fn clear(&mut self)
        ensures
            self@ == Set::<u64>::empty()
    {
        self.elements = Vec::new();
    }
}

// ============================================================
// COORDINATOR STRUCT
// ============================================================

/// Executable coordinator state
/// Uses CoordPhase directly from coordinator_s.rs - no duplication needed!
pub struct Coordinator {
    // ===== Durable state (survives crash) =====
    /// Transaction ID for current protocol attempt
    pub current_txn_id: u64,
    /// Whether COMMIT is recorded in WAL
    pub wal_committed: bool,

    // ===== Volatile state (lost on crash) =====
    /// Current phase of the protocol (uses CoordPhase directly)
    pub phase: CoordPhase,
    /// Stores that have responded success to LockReq (using u64 store IDs)
    pub locks_acquired: SimpleSet,
    /// Stores that have responded to RenameReq
    pub renames_done: SimpleSet,
    /// Stores that have responded to UnlockReq
    pub unlocks_acked: SimpleSet,
}

impl View for Coordinator {
    type V = CoordinatorSpec;

    closed spec fn view(&self) -> CoordinatorSpec {
        CoordinatorSpec {
            current_txn_id: self.current_txn_id as nat,
            wal_committed: self.wal_committed,
            phase: self.phase,
            locks_acquired: Set::new(|s: nat| self.locks_acquired@.contains(s as u64)),
            renames_done: Set::new(|s: nat| self.renames_done@.contains(s as u64)),
            unlocks_acked: Set::new(|s: nat| self.unlocks_acked@.contains(s as u64)),
        }
    }
}

impl Coordinator {
    // ============================================================
    // SPEC HELPERS
    // ============================================================

    pub open spec fn spec_txn_id(&self) -> nat {
        self.current_txn_id as nat
    }

    pub open spec fn spec_is_committed(&self) -> bool {
        self.wal_committed
    }

    pub open spec fn spec_phase(&self) -> CoordPhase {
        self.phase
    }

    pub open spec fn spec_has_lock(&self, store: u64) -> bool {
        self.locks_acquired@.contains(store)
    }

    pub open spec fn spec_has_renamed(&self, store: u64) -> bool {
        self.renames_done@.contains(store)
    }

    pub open spec fn spec_has_unlocked(&self, store: u64) -> bool {
        self.unlocks_acked@.contains(store)
    }

    // ============================================================
    // EXEC FUNCTIONS
    // ============================================================

    /// Create new coordinator in initial state
    pub fn new() -> (result: Self)
        ensures
            result.current_txn_id == 1,
            result.wal_committed == false,
            result.phase == CoordPhase::Idle,
            result.locks_acquired@ == Set::<u64>::empty(),
            result.renames_done@ == Set::<u64>::empty(),
            result.unlocks_acked@ == Set::<u64>::empty(),
    {
        Coordinator {
            current_txn_id: 1,
            wal_committed: false,
            phase: CoordPhase::Idle,
            locks_acquired: SimpleSet::new(),
            renames_done: SimpleSet::new(),
            unlocks_acked: SimpleSet::new(),
        }
    }

    /// Get current transaction ID
    pub fn get_txn_id(&self) -> (result: u64)
        ensures
            result as nat == self.spec_txn_id()
    {
        self.current_txn_id
    }

    /// Check if WAL is committed
    pub fn is_committed(&self) -> (result: bool)
        ensures
            result == self.spec_is_committed()
    {
        self.wal_committed
    }

    /// Get current phase
    pub fn get_phase(&self) -> (result: CoordPhase)
        ensures
            result == self.spec_phase()
    {
        self.phase
    }

    /// Check if a store has acquired lock
    pub fn has_lock(&self, store: u64) -> (result: bool)
        ensures
            result == self.locks_acquired@.contains(store)
    {
        self.locks_acquired.contains(&store)
    }

    /// Check if a store has completed rename
    pub fn has_renamed(&self, store: u64) -> (result: bool)
        ensures
            result == self.renames_done@.contains(store)
    {
        self.renames_done.contains(&store)
    }

    /// Check if a store has acknowledged unlock
    pub fn has_unlocked(&self, store: u64) -> (result: bool)
        ensures
            result == self.unlocks_acked@.contains(store)
    {
        self.unlocks_acked.contains(&store)
    }

    /// Start preparing - transition from Idle to Preparing
    pub fn start_preparing(&mut self)
        requires
            old(self).phase == CoordPhase::Idle || old(self).phase == CoordPhase::Preparing
        ensures
            self.phase == CoordPhase::Preparing,
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            self.locks_acquired@ == old(self).locks_acquired@,
            self.renames_done@ == old(self).renames_done@,
            self.unlocks_acked@ == old(self).unlocks_acked@,
    {
        self.phase = CoordPhase::Preparing;
    }

    /// Record successful lock response from a store
    pub fn record_lock_success(&mut self, store: u64)
        requires
            old(self).phase == CoordPhase::Preparing,
            !old(self).locks_acquired@.contains(store),
        ensures
            self.locks_acquired@.contains(store),
            self.phase == old(self).phase,
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            forall|s: u64| old(self).renames_done@.contains(s) ==> self.renames_done@.contains(s),
            forall|s: u64| old(self).unlocks_acked@.contains(s) ==> self.unlocks_acked@.contains(s),
    {
        self.locks_acquired.insert(store);
    }

    /// Handle lock failure - transition to cleanup
    pub fn handle_lock_failure(&mut self)
        requires
            old(self).phase == CoordPhase::Preparing
        ensures
            self.phase == CoordPhase::Cleanup,
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            self.locks_acquired@ == Set::<u64>::empty(),
            self.renames_done@ == Set::<u64>::empty(),
            self.unlocks_acked@ == Set::<u64>::empty(),
    {
        self.phase = CoordPhase::Cleanup;
        self.locks_acquired.clear();
        self.renames_done.clear();
        self.unlocks_acked.clear();
    }

    /// Decide to commit - write to WAL and transition to Committed
    pub fn decide_commit(&mut self)
        requires
            old(self).phase == CoordPhase::Preparing
        ensures
            self.wal_committed == true,
            self.phase == CoordPhase::Committed,
            self.current_txn_id == old(self).current_txn_id,
            forall|s: u64| old(self).locks_acquired@.contains(s) ==> self.locks_acquired@.contains(s),
            forall|s: u64| old(self).renames_done@.contains(s) ==> self.renames_done@.contains(s),
            forall|s: u64| old(self).unlocks_acked@.contains(s) ==> self.unlocks_acked@.contains(s),
    {
        self.wal_committed = true;
        self.phase = CoordPhase::Committed;
    }

    /// Record rename response from a store
    /// Returns true if all stores have completed rename (transition to cleanup)
    pub fn record_rename_done(&mut self, store: u64, num_stores: usize) -> (all_done: bool)
        requires
            old(self).phase == CoordPhase::Committed,
            !old(self).renames_done@.contains(store),
        ensures
            self.renames_done@.contains(store),
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            forall|s: u64| old(self).locks_acquired@.contains(s) ==> self.locks_acquired@.contains(s),
            forall|s: u64| old(self).unlocks_acked@.contains(s) ==> self.unlocks_acked@.contains(s),
            // Phase transition logic
            all_done ==> self.phase == CoordPhase::Cleanup,
            !all_done ==> self.phase == CoordPhase::Committed,
    {
        self.renames_done.insert(store);
        let len = self.renames_done.len();
        if len == num_stores {
            self.phase = CoordPhase::Cleanup;
            true
        } else {
            false
        }
    }

    /// Record unlock acknowledgment from a store
    /// Returns true if all stores have acknowledged (transition to done)
    pub fn record_unlock_acked(&mut self, store: u64, num_stores: usize) -> (all_done: bool)
        requires
            old(self).phase == CoordPhase::Cleanup,
            !old(self).unlocks_acked@.contains(store),
        ensures
            self.unlocks_acked@.contains(store),
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            forall|s: u64| old(self).locks_acquired@.contains(s) ==> self.locks_acquired@.contains(s),
            forall|s: u64| old(self).renames_done@.contains(s) ==> self.renames_done@.contains(s),
            // Phase transition logic
            all_done ==> self.phase == CoordPhase::Done,
            !all_done ==> self.phase == CoordPhase::Cleanup,
    {
        self.unlocks_acked.insert(store);
        let len = self.unlocks_acked.len();
        if len == num_stores {
            self.phase = CoordPhase::Done;
            true
        } else {
            false
        }
    }

    /// Coordinator crash - reset volatile state
    pub fn crash(&mut self)
        requires
            old(self).phase.spec_can_crash()
        ensures
            // Durable state preserved
            self.current_txn_id == old(self).current_txn_id,
            self.wal_committed == old(self).wal_committed,
            // Volatile state reset
            self.phase == CoordPhase::Crashed,
            self.locks_acquired@ == Set::<u64>::empty(),
            self.renames_done@ == Set::<u64>::empty(),
            self.unlocks_acked@ == Set::<u64>::empty(),
    {
        self.phase = CoordPhase::Crashed;
        self.locks_acquired.clear();
        self.renames_done.clear();
        self.unlocks_acked.clear();
    }

    /// Coordinator recover - increment txn_id, resume based on WAL
    pub fn recover(&mut self)
        requires
            old(self).phase == CoordPhase::Crashed,
            old(self).current_txn_id < u64::MAX,
        ensures
            // Txn ID incremented
            self.current_txn_id == old(self).current_txn_id + 1,
            // WAL preserved
            self.wal_committed == old(self).wal_committed,
            // Phase based on WAL
            old(self).wal_committed ==> self.phase == CoordPhase::Committed,
            !old(self).wal_committed ==> self.phase == CoordPhase::Cleanup,
            // Volatile state reset
            self.locks_acquired@ == Set::<u64>::empty(),
            self.renames_done@ == Set::<u64>::empty(),
            self.unlocks_acked@ == Set::<u64>::empty(),
    {
        self.current_txn_id = self.current_txn_id + 1;
        if self.wal_committed {
            self.phase = CoordPhase::Committed;
        } else {
            self.phase = CoordPhase::Cleanup;
        }
        self.locks_acquired.clear();
        self.renames_done.clear();
        self.unlocks_acked.clear();
    }
}

// ============================================================
// UNIT TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test: Create new coordinator
    fn test_new() {
        let coord = Coordinator::new();
        assert(coord.get_txn_id() == 1);
        assert(!coord.is_committed());
        assert(coord.get_phase() == CoordPhase::Idle);
    }

    /// Test: Start preparing
    fn test_start_preparing() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        assert(coord.get_phase() == CoordPhase::Preparing);
        assert(coord.get_txn_id() == 1);
    }

    /// Test: Record lock success
    fn test_record_lock_success() {
        let mut coord = Coordinator::new();
        coord.start_preparing();

        coord.record_lock_success(0);
        assert(coord.has_lock(0));
        assert(!coord.has_lock(1));

        coord.record_lock_success(1);
        assert(coord.has_lock(0));
        assert(coord.has_lock(1));
    }

    /// Test: Handle lock failure
    fn test_handle_lock_failure() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.record_lock_success(0);

        coord.handle_lock_failure();
        assert(coord.get_phase() == CoordPhase::Cleanup);
        assert(!coord.has_lock(0));  // Locks cleared
    }

    /// Test: Decide commit
    fn test_decide_commit() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.record_lock_success(0);
        coord.record_lock_success(1);

        coord.decide_commit();
        assert(coord.is_committed());
        assert(coord.get_phase() == CoordPhase::Committed);
    }

    /// Test: Record rename done
    fn test_record_rename_done() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.decide_commit();

        let all_done = coord.record_rename_done(0, 2);
        assert(!all_done);
        assert(coord.has_renamed(0));
        assert(coord.get_phase() == CoordPhase::Committed);

        let all_done = coord.record_rename_done(1, 2);
        assert(all_done);
        assert(coord.has_renamed(1));
        assert(coord.get_phase() == CoordPhase::Cleanup);
    }

    /// Test: Record unlock acked
    fn test_record_unlock_acked() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.decide_commit();
        coord.record_rename_done(0, 2);
        coord.record_rename_done(1, 2);

        let all_done = coord.record_unlock_acked(0, 2);
        assert(!all_done);
        assert(coord.has_unlocked(0));
        assert(coord.get_phase() == CoordPhase::Cleanup);

        let all_done = coord.record_unlock_acked(1, 2);
        assert(all_done);
        assert(coord.has_unlocked(1));
        assert(coord.get_phase() == CoordPhase::Done);
    }

    /// Test: Crash and recover (committed)
    fn test_crash_recover_committed() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.decide_commit();
        coord.record_rename_done(0, 2);

        // Crash
        coord.crash();
        assert(coord.get_phase() == CoordPhase::Crashed);
        assert(coord.is_committed());  // Durable state preserved
        assert(coord.get_txn_id() == 1);  // Txn ID preserved

        // Recover
        coord.recover();
        assert(coord.get_txn_id() == 2);  // Txn ID incremented
        assert(coord.is_committed());  // WAL preserved
        assert(coord.get_phase() == CoordPhase::Committed);  // Resume commit
        assert(!coord.has_renamed(0));  // Volatile state cleared
    }

    /// Test: Crash and recover (not committed)
    fn test_crash_recover_not_committed() {
        let mut coord = Coordinator::new();
        coord.start_preparing();
        coord.record_lock_success(0);

        // Crash before commit
        coord.crash();
        assert(coord.get_phase() == CoordPhase::Crashed);
        assert(!coord.is_committed());

        // Recover
        coord.recover();
        assert(coord.get_txn_id() == 2);
        assert(!coord.is_committed());
        assert(coord.get_phase() == CoordPhase::Cleanup);  // Go to cleanup
    }
}

} // verus!
