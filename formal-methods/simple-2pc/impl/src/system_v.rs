// system_v.rs - Verified executable system driver
//
// This file contains:
// - ExecSystem: executable system state composing Coordinator, KvStores, and ExecNetwork
// - Verified exec functions for system-level operations
// - Integration of all components for end-to-end protocol execution
//
// This is the executable counterpart to system_s.rs (spec layer).

use vstd::prelude::*;

use crate::coordinator_s::*;
use crate::coordinator_v::*;
use crate::kv_store_v::*;
use crate::network_s::*;
use crate::network_v::*;

verus! {

// ============================================================
// EXECUTABLE SYSTEM STATE
// ============================================================

/// Executable system state that composes all components.
/// 
/// This struct holds:
/// - The coordinator
/// - A collection of KV stores (indexed by store ID)
/// - The network (mocked message queue)
/// - Configuration (key names for the rename operation)
pub struct ExecSystem {
    /// The coordinator managing the 2PC protocol
    pub coord: Coordinator,
    /// KV stores indexed by store ID (using Vec for simplicity)
    pub stores: Vec<KvStore>,
    /// The network (mocked message queue)
    pub net: ExecNetwork,
    /// Source key name for rename operation
    pub key_a: String,
    /// Destination key name for rename operation
    pub key_aprime: String,
}

impl ExecSystem {
    // ============================================================
    // SPEC HELPERS
    // ============================================================

    /// Get the number of stores
    pub open spec fn spec_num_stores(&self) -> nat {
        self.stores@.len() as nat
    }

    /// Check if a store ID is valid
    pub open spec fn spec_valid_store(&self, store_id: u64) -> bool {
        (store_id as int) < self.stores@.len()
    }

    // ============================================================
    // CONSTRUCTORS
    // ============================================================

    /// Create a new system with the specified number of stores.
    /// Each store is initialized with key_a -> initial_value.
    pub fn new(num_stores: usize, key_a: &str, key_aprime: &str, initial_value: u64) -> (result: Self)
        requires
            num_stores > 0,
            key_a@ != key_aprime@,
        ensures
            result.stores@.len() == num_stores,
            result.coord.spec_phase() == CoordPhase::Idle,
            result.net.spec_is_empty(),
    {
        let mut stores: Vec<KvStore> = Vec::new();
        let mut i: usize = 0;
        while i < num_stores
            invariant
                0 <= i <= num_stores,
                stores@.len() == i,
            decreases
                num_stores - i,
        {
            let mut store = KvStore::new();
            store.put(key_a, initial_value);
            stores.push(store);
            i = i + 1;
        }

        ExecSystem {
            coord: Coordinator::new(),
            stores,
            net: ExecNetwork::new(),
            key_a: key_a.to_owned(),
            key_aprime: key_aprime.to_owned(),
        }
    }

    // ============================================================
    // STORE ACCESS HELPERS
    // ============================================================

    /// Get a store by index (immutable)
    #[verifier::truncate]
    pub fn get_store(&self, store_id: u64) -> (result: &KvStore)
        requires
            self.spec_valid_store(store_id),
    {
        &self.stores[store_id as usize]
    }

    // ============================================================
    // COORDINATOR -> NETWORK (SEND) OPERATIONS
    // ============================================================

    /// Coordinator sends lock request to a store
    pub fn coord_send_lock_req(&mut self, store_id: u64)
        requires
            old(self).spec_valid_store(store_id),
            old(self).coord.spec_phase() == CoordPhase::Idle || old(self).coord.spec_phase() == CoordPhase::Preparing,
        ensures
            self.coord.spec_phase() == CoordPhase::Preparing,
            self.net.spec_contains(lock_req_msg(store_id as nat, self.coord.spec_txn_id())),
    {
        self.coord.start_preparing();
        let txn_id = self.coord.get_txn_id();
        let msg = ExecMessage::lock_req(store_id, txn_id);
        self.net.send(msg);
    }

    /// Coordinator sends rename request to a store
    pub fn coord_send_rename_req(&mut self, store_id: u64)
        requires
            old(self).spec_valid_store(store_id),
            old(self).coord.spec_phase() == CoordPhase::Committed,
        ensures
            self.coord.spec_phase() == CoordPhase::Committed,
            self.net.spec_contains(rename_req_msg(store_id as nat, self.coord.spec_txn_id())),
    {
        let txn_id = self.coord.get_txn_id();
        let msg = ExecMessage::rename_req(store_id, txn_id);
        self.net.send(msg);
    }

    /// Coordinator sends unlock request to a store
    pub fn coord_send_unlock_req(&mut self, store_id: u64)
        requires
            old(self).spec_valid_store(store_id),
            old(self).coord.spec_phase() == CoordPhase::Cleanup,
        ensures
            self.coord.spec_phase() == CoordPhase::Cleanup,
            self.net.spec_contains(unlock_req_msg(store_id as nat, self.coord.spec_txn_id())),
    {
        let txn_id = self.coord.get_txn_id();
        let msg = ExecMessage::unlock_req(store_id, txn_id);
        self.net.send(msg);
    }

    // ============================================================
    // NETWORK -> COORDINATOR (RECEIVE) OPERATIONS
    // ============================================================

    /// Coordinator receives lock response (success)
    /// Returns true if message was found and processed
    pub fn coord_recv_lock_resp_success(&mut self, store_id: u64) -> (result: bool)
        requires
            old(self).coord.spec_phase() == CoordPhase::Preparing,
            !old(self).coord.spec_has_lock(store_id),
        ensures
            result ==> self.coord.spec_has_lock(store_id),
            result ==> self.coord.spec_phase() == CoordPhase::Preparing,
    {
        let txn_id = self.coord.get_txn_id();
        let expected_msg = ExecMessage::lock_resp(store_id, true, txn_id);
        
        if self.net.lose(&expected_msg) {
            self.coord.record_lock_success(store_id);
            true
        } else {
            false
        }
    }

    /// Coordinator receives lock response (failure)
    /// Returns true if message was found and processed
    pub fn coord_recv_lock_resp_failure(&mut self, store_id: u64) -> (result: bool)
        requires
            old(self).coord.spec_phase() == CoordPhase::Preparing,
        ensures
            result ==> self.coord.spec_phase() == CoordPhase::Cleanup,
    {
        let txn_id = self.coord.get_txn_id();
        let expected_msg = ExecMessage::lock_resp(store_id, false, txn_id);
        
        if self.net.lose(&expected_msg) {
            self.coord.handle_lock_failure();
            true
        } else {
            false
        }
    }

    /// Coordinator decides to commit
    pub fn coord_decide_commit(&mut self)
        requires
            old(self).coord.spec_phase() == CoordPhase::Preparing,
        ensures
            self.coord.spec_phase() == CoordPhase::Committed,
            self.coord.spec_is_committed(),
    {
        self.coord.decide_commit();
    }

    /// Coordinator receives rename response
    /// Returns true if message was found and processed
    pub fn coord_recv_rename_resp(&mut self, store_id: u64) -> (result: bool)
        requires
            old(self).coord.spec_phase() == CoordPhase::Committed,
            !old(self).coord.spec_has_renamed(store_id),
        ensures
            result ==> self.coord.spec_has_renamed(store_id),
    {
        let txn_id = self.coord.get_txn_id();
        let expected_msg = ExecMessage::rename_resp(store_id, txn_id);
        
        if self.net.lose(&expected_msg) {
            let num_stores = self.stores.len();
            self.coord.record_rename_done(store_id, num_stores);
            true
        } else {
            false
        }
    }

    /// Coordinator receives unlock response
    /// Returns true if message was found and processed
    pub fn coord_recv_unlock_resp(&mut self, store_id: u64) -> (result: bool)
        requires
            old(self).coord.spec_phase() == CoordPhase::Cleanup,
            !old(self).coord.spec_has_unlocked(store_id),
        ensures
            result ==> self.coord.spec_has_unlocked(store_id),
    {
        let txn_id = self.coord.get_txn_id();
        let expected_msg = ExecMessage::unlock_resp(store_id, txn_id);
        
        if self.net.lose(&expected_msg) {
            let num_stores = self.stores.len();
            self.coord.record_unlock_acked(store_id, num_stores);
            true
        } else {
            false
        }
    }

    // ============================================================
    // NETWORK -> STORE (HANDLE) OPERATIONS
    // ============================================================

    /// Store handles lock request
    /// Returns true if message was found and processed
    pub fn store_handle_lock_req(&mut self, store_id: u64, txn_id: u64) -> (result: bool)
        requires
            old(self).spec_valid_store(store_id),
        ensures
            result ==> self.stores@.len() == old(self).stores@.len(),
    {
        let expected_msg = ExecMessage::lock_req(store_id, txn_id);
        
        if !self.net.lose(&expected_msg) {
            return false;
        }

        let store_idx = store_id as usize;
        
        // Check for stale transaction using immutable borrow
        let is_stale = self.stores[store_idx].is_stale_txn_id(txn_id);
        if is_stale {
            return true; // Message consumed but ignored (stale)
        }

        // Get a mutable reference and perform operations
        // We need to use Vec::swap to work around Verus limitations
        let mut store = self.stores.remove(store_idx);
        
        // Update txn_id
        store.update_txn_id(txn_id);

        // Check if key_aprime already exists (already renamed)
        let key_aprime_exists = store.contains_key(self.key_aprime.as_str());
        
        if key_aprime_exists {
            // Lock failed - key already renamed
            let resp = ExecMessage::lock_resp(store_id, false, txn_id);
            self.net.send(resp);
        } else {
            // Lock both keys
            store.lock(self.key_a.as_str());
            store.lock(self.key_aprime.as_str());
            // Send success response
            let resp = ExecMessage::lock_resp(store_id, true, txn_id);
            self.net.send(resp);
        }

        // Put the store back
        self.stores.insert(store_idx, store);

        true
    }

    /// Store handles rename request
    /// Returns true if message was found and processed
    pub fn store_handle_rename_req(&mut self, store_id: u64, txn_id: u64) -> (result: bool)
        requires
            old(self).spec_valid_store(store_id),
        ensures
            result ==> self.stores@.len() == old(self).stores@.len(),
    {
        let expected_msg = ExecMessage::rename_req(store_id, txn_id);
        
        if !self.net.lose(&expected_msg) {
            return false;
        }

        let store_idx = store_id as usize;
        
        // Check for stale transaction using immutable borrow
        let is_stale = self.stores[store_idx].is_stale_txn_id(txn_id);
        if is_stale {
            return true; // Message consumed but ignored (stale)
        }

        // Get a mutable reference by removing and re-inserting
        let mut store = self.stores.remove(store_idx);
        
        // Update txn_id
        store.update_txn_id(txn_id);

        // Check if already renamed (idempotent)
        let key_aprime_exists = store.contains_key(self.key_aprime.as_str());
        let key_a_locked = store.is_locked(self.key_a.as_str());
        let key_aprime_locked = store.is_locked(self.key_aprime.as_str());
        let key_a_exists = store.contains_key(self.key_a.as_str());
        
        if key_aprime_exists {
            // Already renamed - send success (idempotent)
            let resp = ExecMessage::rename_resp(store_id, txn_id);
            self.net.send(resp);
        } else if key_a_locked && key_aprime_locked && key_a_exists {
            // Perform rename
            store.rename(self.key_a.as_str(), self.key_aprime.as_str());
            // Send success response
            let resp = ExecMessage::rename_resp(store_id, txn_id);
            self.net.send(resp);
        }
        // else: preconditions not met, no response

        // Put the store back
        self.stores.insert(store_idx, store);

        true
    }

    /// Store handles unlock request
    /// Returns true if message was found and processed
    pub fn store_handle_unlock_req(&mut self, store_id: u64, txn_id: u64) -> (result: bool)
        requires
            old(self).spec_valid_store(store_id),
        ensures
            result ==> self.stores@.len() == old(self).stores@.len(),
    {
        let expected_msg = ExecMessage::unlock_req(store_id, txn_id);
        
        if !self.net.lose(&expected_msg) {
            return false;
        }

        let store_idx = store_id as usize;
        
        // Check for stale transaction using immutable borrow
        let is_stale = self.stores[store_idx].is_stale_txn_id(txn_id);
        if is_stale {
            return true; // Message consumed but ignored (stale)
        }

        // Get a mutable reference by removing and re-inserting
        let mut store = self.stores.remove(store_idx);
        
        // Update txn_id
        store.update_txn_id(txn_id);

        // Unlock both keys
        store.unlock(self.key_a.as_str());
        store.unlock(self.key_aprime.as_str());

        // Send success response
        let resp = ExecMessage::unlock_resp(store_id, txn_id);
        self.net.send(resp);

        // Put the store back
        self.stores.insert(store_idx, store);

        true
    }

    // ============================================================
    // ENVIRONMENT (NETWORK-ONLY) OPERATIONS
    // ============================================================

    /// Lose a message from the network
    pub fn net_lose(&mut self, msg: &ExecMessage) -> (result: bool)
        ensures
            result == old(self).net.spec_contains(msg@),
    {
        self.net.lose(msg)
    }

    /// Duplicate a message in the network
    pub fn net_duplicate(&mut self, msg: &ExecMessage) -> (result: bool)
        ensures
            result == old(self).net.spec_contains(msg@),
            result ==> self.net.spec_contains(msg@),
    {
        self.net.duplicate(msg)
    }

    // ============================================================
    // COORDINATOR CRASH/RECOVERY
    // ============================================================

    /// Coordinator crashes
    pub fn coord_crash(&mut self)
        requires
            old(self).coord.spec_phase().spec_can_crash(),
        ensures
            self.coord.spec_phase() == CoordPhase::Crashed,
    {
        self.coord.crash();
    }

    /// Coordinator recovers
    pub fn coord_recover(&mut self)
        requires
            old(self).coord.spec_phase() == CoordPhase::Crashed,
            old(self).coord.spec_txn_id() < u64::MAX as nat,
        ensures
            self.coord.spec_txn_id() == old(self).coord.spec_txn_id() + 1,
            old(self).coord.spec_is_committed() ==> self.coord.spec_phase() == CoordPhase::Committed,
            !old(self).coord.spec_is_committed() ==> self.coord.spec_phase() == CoordPhase::Cleanup,
    {
        self.coord.recover();
    }

    // ============================================================
    // QUERY OPERATIONS
    // ============================================================

    /// Get the current phase of the coordinator
    pub fn get_coord_phase(&self) -> (result: CoordPhase)
        ensures
            result == self.coord.spec_phase()
    {
        self.coord.get_phase()
    }

    /// Get the current transaction ID
    pub fn get_txn_id(&self) -> (result: u64)
        ensures
            result as nat == self.coord.spec_txn_id()
    {
        self.coord.get_txn_id()
    }

    /// Check if coordinator is committed
    pub fn is_committed(&self) -> (result: bool)
        ensures
            result == self.coord.spec_is_committed()
    {
        self.coord.is_committed()
    }

    /// Get the number of stores
    pub fn num_stores(&self) -> (result: usize)
        ensures
            result as nat == self.spec_num_stores()
    {
        self.stores.len()
    }

    /// Check if a store has the source key
    pub fn store_has_key_a(&self, store_id: u64) -> (result: bool)
        requires
            self.spec_valid_store(store_id),
    {
        self.stores[store_id as usize].contains_key(self.key_a.as_str())
    }

    /// Check if a store has the destination key
    pub fn store_has_key_aprime(&self, store_id: u64) -> (result: bool)
        requires
            self.spec_valid_store(store_id),
    {
        self.stores[store_id as usize].contains_key(self.key_aprime.as_str())
    }

    /// Get value at source key from a store
    pub fn store_get_key_a(&self, store_id: u64) -> (result: Option<u64>)
        requires
            self.spec_valid_store(store_id),
    {
        self.stores[store_id as usize].get(self.key_a.as_str())
    }

    /// Get value at destination key from a store
    pub fn store_get_key_aprime(&self, store_id: u64) -> (result: Option<u64>)
        requires
            self.spec_valid_store(store_id),
    {
        self.stores[store_id as usize].get(self.key_aprime.as_str())
    }

    /// Check if network is empty
    pub fn net_is_empty(&self) -> (result: bool)
        ensures
            result == self.net.spec_is_empty()
    {
        self.net.is_empty()
    }

    /// Directly put a value into a store (for testing)
    pub fn store_put(&mut self, store_id: u64, key: &str, value: u64)
        requires
            old(self).spec_valid_store(store_id),
        ensures
            self.stores@.len() == old(self).stores@.len(),
    {
        let store_idx = store_id as usize;
        let mut store = self.stores.remove(store_idx);
        store.put(key, value);
        self.stores.insert(store_idx, store);
    }

    /// Update txn_id for a store (for testing)
    pub fn store_update_txn_id(&mut self, store_id: u64, txn_id: u64)
        requires
            old(self).spec_valid_store(store_id),
        ensures
            self.stores@.len() == old(self).stores@.len(),
    {
        let store_idx = store_id as usize;
        let mut store = self.stores.remove(store_idx);
        store.update_txn_id(txn_id);
        self.stores.insert(store_idx, store);
    }

    /// Check if a store's txn_id is stale
    pub fn store_is_stale_txn_id(&self, store_id: u64, txn_id: u64) -> (result: bool)
        requires
            self.spec_valid_store(store_id),
    {
        self.stores[store_id as usize].is_stale_txn_id(txn_id)
    }
}

// ============================================================
// UNIT TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test: Create new system
    fn test_new_system() {
        let sys = ExecSystem::new(2, "A", "A'", 100);
        
        assert(sys.num_stores() == 2);
        assert(sys.get_coord_phase() == CoordPhase::Idle);
        assert(sys.net_is_empty());
        assert(sys.store_has_key_a(0));
        assert(sys.store_has_key_a(1));
        assert(!sys.store_has_key_aprime(0));
        assert(!sys.store_has_key_aprime(1));
    }

    /// Test: Happy path - full 2PC rename protocol
    fn test_happy_path() {
        let mut sys = ExecSystem::new(2, "A", "A'", 42);
        let txn_id = sys.get_txn_id();
        
        // Phase 1: Send lock requests
        sys.coord_send_lock_req(0);
        sys.coord_send_lock_req(1);
        assert(sys.get_coord_phase() == CoordPhase::Preparing);
        
        // Stores handle lock requests
        assert(sys.store_handle_lock_req(0, txn_id));
        assert(sys.store_handle_lock_req(1, txn_id));
        
        // Coordinator receives lock responses
        assert(sys.coord_recv_lock_resp_success(0));
        assert(sys.coord_recv_lock_resp_success(1));
        
        // Coordinator decides to commit
        sys.coord_decide_commit();
        assert(sys.get_coord_phase() == CoordPhase::Committed);
        assert(sys.is_committed());
        
        // Phase 2: Send rename requests
        sys.coord_send_rename_req(0);
        sys.coord_send_rename_req(1);
        
        // Stores handle rename requests
        assert(sys.store_handle_rename_req(0, txn_id));
        assert(sys.store_handle_rename_req(1, txn_id));
        
        // Verify rename happened
        assert(!sys.store_has_key_a(0));
        assert(sys.store_has_key_aprime(0));
        assert(!sys.store_has_key_a(1));
        assert(sys.store_has_key_aprime(1));
        
        // Coordinator receives rename responses
        assert(sys.coord_recv_rename_resp(0));
        assert(sys.coord_recv_rename_resp(1));
        assert(sys.get_coord_phase() == CoordPhase::Cleanup);
        
        // Phase 3: Send unlock requests
        sys.coord_send_unlock_req(0);
        sys.coord_send_unlock_req(1);
        
        // Stores handle unlock requests
        assert(sys.store_handle_unlock_req(0, txn_id));
        assert(sys.store_handle_unlock_req(1, txn_id));
        
        // Coordinator receives unlock responses
        assert(sys.coord_recv_unlock_resp(0));
        assert(sys.coord_recv_unlock_resp(1));
        
        // Protocol complete
        assert(sys.get_coord_phase() == CoordPhase::Done);
    }

    /// Test: Lock failure leads to cleanup
    fn test_lock_failure() {
        let mut sys = ExecSystem::new(1, "A", "A'", 42);
        let txn_id = sys.get_txn_id();
        
        // Manually put key_aprime to simulate already renamed
        sys.store_put(0, "A'", 99);
        
        // Send lock request
        sys.coord_send_lock_req(0);
        
        // Store handles lock request - should fail because A' exists
        assert(sys.store_handle_lock_req(0, txn_id));
        
        // Coordinator receives lock failure
        assert(sys.coord_recv_lock_resp_failure(0));
        assert(sys.get_coord_phase() == CoordPhase::Cleanup);
    }

    /// Test: Crash and recovery (committed)
    fn test_crash_recovery_committed() {
        let mut sys = ExecSystem::new(1, "A", "A'", 42);
        
        // Get to committed state
        sys.coord_send_lock_req(0);
        let txn_id = sys.get_txn_id();
        sys.store_handle_lock_req(0, txn_id);
        sys.coord_recv_lock_resp_success(0);
        sys.coord_decide_commit();
        
        assert(sys.is_committed());
        assert(sys.get_coord_phase() == CoordPhase::Committed);
        
        // Crash
        sys.coord_crash();
        assert(sys.get_coord_phase() == CoordPhase::Crashed);
        assert(sys.is_committed()); // Durable state preserved
        
        // Recover
        sys.coord_recover();
        assert(sys.get_txn_id() == txn_id + 1);
        assert(sys.get_coord_phase() == CoordPhase::Committed); // Resume commit
    }

    /// Test: Crash and recovery (not committed)
    fn test_crash_recovery_not_committed() {
        let mut sys = ExecSystem::new(1, "A", "A'", 42);
        
        // Start preparing but don't commit
        sys.coord_send_lock_req(0);
        let txn_id = sys.get_txn_id();
        
        assert(!sys.is_committed());
        assert(sys.get_coord_phase() == CoordPhase::Preparing);
        
        // Crash
        sys.coord_crash();
        assert(sys.get_coord_phase() == CoordPhase::Crashed);
        
        // Recover
        sys.coord_recover();
        assert(sys.get_txn_id() == txn_id + 1);
        assert(sys.get_coord_phase() == CoordPhase::Cleanup); // Go to cleanup
    }

    /// Test: Network duplication
    fn test_network_duplication() {
        let mut sys = ExecSystem::new(1, "A", "A'", 42);
        
        // Send lock request
        sys.coord_send_lock_req(0);
        let txn_id = sys.get_txn_id();
        
        // Duplicate the message
        let msg = ExecMessage::lock_req(0, txn_id);
        assert(sys.net_duplicate(&msg));
        
        // Both copies can be processed
        assert(sys.store_handle_lock_req(0, txn_id));
        assert(sys.store_handle_lock_req(0, txn_id)); // Second copy
        
        // Two responses should be in the network
        let resp = ExecMessage::lock_resp(0, true, txn_id);
        assert(sys.net.count(&resp) == 2);
    }

    /// Test: Stale message rejection
    fn test_stale_message_rejection() {
        let mut sys = ExecSystem::new(1, "A", "A'", 42);
        
        // First transaction
        sys.coord_send_lock_req(0);
        let old_txn_id = sys.get_txn_id();
        sys.store_handle_lock_req(0, old_txn_id);
        
        // Crash and recover (increments txn_id)
        sys.coord_crash();
        sys.coord_recover();
        let new_txn_id = sys.get_txn_id();
        assert(new_txn_id > old_txn_id);
        
        // Update store's txn_id with a new message
        sys.store_update_txn_id(0, new_txn_id);
        
        // Old message should be stale
        assert(sys.store_is_stale_txn_id(0, old_txn_id));
    }
}

} // verus!
