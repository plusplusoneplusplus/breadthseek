// kv_store_v.rs - Verified executable implementation of KV store
//
// This file contains:
// - KvStore: executable struct using StringHashMap
// - View implementation connecting exec to spec
// - Verified exec functions with postconditions

use vstd::prelude::*;
use vstd::hash_map::StringHashMap;
use vstd::string::*;

use crate::kv_store_s::*;

verus! {

// ============================================================
// EXEC LAYER - Executable implementation
// ============================================================

/// Executable key-value store using HashMap
pub struct KvStore {
    /// Key-value data storage
    pub data: StringHashMap<u64>,
    /// Locked keys (key -> true means locked)
    pub locked: StringHashMap<bool>,
    /// Last seen transaction ID - used to reject stale messages
    pub last_seen_txn_id: u64,
}

impl View for KvStore {
    type V = KvStoreSpec<u64>;

    /// Connect exec state to spec state
    closed spec fn view(&self) -> KvStoreSpec<u64> {
        KvStoreSpec {
            data: self.data@,
            locked_keys: Set::new(|k: Seq<char>| self.locked@.contains_key(k)),
            last_seen_txn_id: self.last_seen_txn_id as nat,
        }
    }
}

impl KvStore {
    // ============================================================
    // SPEC HELPERS - For use in ensures clauses
    // ============================================================

    pub open spec fn spec_is_locked(&self, key: Seq<char>) -> bool {
        self.locked@.contains_key(key)
    }

    pub open spec fn spec_contains_key(&self, key: Seq<char>) -> bool {
        self.data@.contains_key(key)
    }

    pub open spec fn spec_get(&self, key: Seq<char>) -> u64
        recommends self.spec_contains_key(key)
    {
        self.data@[key]
    }

    pub open spec fn spec_last_seen_txn_id(&self) -> nat {
        self.last_seen_txn_id as nat
    }

    pub open spec fn spec_is_stale_txn_id(&self, txn_id: nat) -> bool {
        txn_id <= self.last_seen_txn_id as nat
    }

    // ============================================================
    // EXEC FUNCTIONS - Verified implementations
    // ============================================================

    /// Create a new empty KV store
    pub fn new() -> (result: Self)
        ensures
            result@.data == Map::<Seq<char>, u64>::empty(),
            result@.locked_keys == Set::<Seq<char>>::empty(),
            result@.last_seen_txn_id == 0,
    {
        KvStore {
            data: StringHashMap::new(),
            locked: StringHashMap::new(),
            last_seen_txn_id: 0,
        }
    }

    /// Get value for key
    pub fn get(&self, key: &str) -> (result: Option<u64>)
        ensures
            match result {
                Some(v) => self.spec_contains_key(key@) && v == self.spec_get(key@),
                None => !self.spec_contains_key(key@),
            }
    {
        match self.data.get(key) {
            Some(v) => Some(*v),
            None => None,
        }
    }

    /// Check if key is locked
    pub fn is_locked(&self, key: &str) -> (result: bool)
        ensures
            result == self.spec_is_locked(key@)
    {
        self.locked.contains_key(key)
    }

    /// Check if key exists
    pub fn contains_key(&self, key: &str) -> (result: bool)
        ensures
            result == self.spec_contains_key(key@)
    {
        self.data.contains_key(key)
    }

    /// Get the last seen transaction ID
    pub fn get_last_seen_txn_id(&self) -> (result: u64)
        ensures
            result as nat == self.spec_last_seen_txn_id()
    {
        self.last_seen_txn_id
    }

    /// Check if a transaction ID is stale (older than or equal to last seen)
    pub fn is_stale_txn_id(&self, txn_id: u64) -> (result: bool)
        ensures
            result == self.spec_is_stale_txn_id(txn_id as nat)
    {
        txn_id <= self.last_seen_txn_id
    }

    /// Update the last seen transaction ID (only updates if newer)
    pub fn update_txn_id(&mut self, txn_id: u64)
        ensures
            // Updates to new txn_id if greater, otherwise unchanged
            self.last_seen_txn_id == if txn_id > old(self).last_seen_txn_id {
                txn_id
            } else {
                old(self).last_seen_txn_id
            },
            // Data unchanged
            self.data@ == old(self).data@,
            // Locks unchanged
            self.locked@ == old(self).locked@,
    {
        if txn_id > self.last_seen_txn_id {
            self.last_seen_txn_id = txn_id;
        }
    }

    /// Put value for key (fails if locked)
    /// Returns true if successful, false if key is locked
    pub fn put(&mut self, key: &str, value: u64) -> (success: bool)
        ensures
            success == !old(self).spec_is_locked(key@),
            // If locked, state unchanged
            old(self).spec_is_locked(key@) ==> (
                self.data@ == old(self).data@
                && self.locked@ == old(self).locked@
            ),
            // If not locked, key is inserted
            !old(self).spec_is_locked(key@) ==> (
                self.data@ == old(self).data@.insert(key@, value)
                && self.locked@ == old(self).locked@
            ),
            // txn_id unchanged
            self.last_seen_txn_id == old(self).last_seen_txn_id,
    {
        if self.locked.contains_key(key) {
            false
        } else {
            self.data.insert(key.to_owned(), value);
            true
        }
    }

    /// Delete key (fails if locked)
    /// Returns true if successful, false if key is locked
    pub fn delete(&mut self, key: &str) -> (success: bool)
        ensures
            success == !old(self).spec_is_locked(key@),
            // If locked, state unchanged
            old(self).spec_is_locked(key@) ==> (
                self.data@ == old(self).data@
                && self.locked@ == old(self).locked@
            ),
            // If not locked, key is removed
            !old(self).spec_is_locked(key@) ==> (
                self.data@ == old(self).data@.remove(key@)
                && self.locked@ == old(self).locked@
            ),
            // txn_id unchanged
            self.last_seen_txn_id == old(self).last_seen_txn_id,
    {
        if self.locked.contains_key(key) {
            false
        } else {
            self.data.remove(key);
            true
        }
    }

    /// Lock a key (idempotent)
    pub fn lock(&mut self, key: &str)
        ensures
            // Key is now locked
            self.spec_is_locked(key@),
            // Data unchanged
            self.data@ == old(self).data@,
            // Other locks unchanged
            forall|k: Seq<char>| k != key@ ==>
                (self.spec_is_locked(k) == old(self).spec_is_locked(k)),
            // txn_id unchanged
            self.last_seen_txn_id == old(self).last_seen_txn_id,
    {
        self.locked.insert(key.to_owned(), true);
    }

    /// Unlock a key (idempotent)
    pub fn unlock(&mut self, key: &str)
        ensures
            // Key is now unlocked
            !self.spec_is_locked(key@),
            // Data unchanged
            self.data@ == old(self).data@,
            // Other locks unchanged
            forall|k: Seq<char>| k != key@ ==>
                (self.spec_is_locked(k) == old(self).spec_is_locked(k)),
            // txn_id unchanged
            self.last_seen_txn_id == old(self).last_seen_txn_id,
    {
        self.locked.remove(key);
    }

    /// Rename: move value from old_key to new_key
    /// Precondition: both keys must be locked and different
    /// Returns the value that was moved, or None if old_key doesn't exist
    pub fn rename(&mut self, old_key: &str, new_key: &str) -> (result: Option<u64>)
        requires
            old(self).spec_is_locked(old_key@),
            old(self).spec_is_locked(new_key@),
            old_key@ != new_key@,
        ensures
            // Locks unchanged
            self.locked@ == old(self).locked@,
            // Result matches whether old_key existed
            result.is_some() == old(self).spec_contains_key(old_key@),
            // If succeeded, the value is correct
            result.is_some() ==> result == Some(old(self).spec_get(old_key@)),
            // If succeeded, new_key now has the value
            result.is_some() ==> self.spec_contains_key(new_key@),
            result.is_some() ==> self.spec_get(new_key@) == old(self).spec_get(old_key@),
            // If succeeded, old_key is removed
            result.is_some() ==> !self.spec_contains_key(old_key@),
            // If failed, data unchanged
            result.is_none() ==> self.data@ == old(self).data@,
            // txn_id unchanged
            self.last_seen_txn_id == old(self).last_seen_txn_id,
    {
        match self.data.get(old_key) {
            Some(v) => {
                let value = *v;
                let new_key_owned = new_key.to_owned();
                self.data.remove(old_key);
                self.data.insert(new_key_owned, value);
                Some(value)
            }
            None => None,
        }
    }
}

// ============================================================
// UNIT TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test: Create empty store
    fn test_new() {
        let store = KvStore::new();
        assert(!store.contains_key("any_key"));
        assert(!store.is_locked("any_key"));
    }

    /// Test: Put and get
    fn test_put_get() {
        let mut store = KvStore::new();

        // Put a value
        let success = store.put("key1", 42);
        assert(success);

        // Get it back
        let result = store.get("key1");
        assert(result == Some(42u64));

        // Non-existent key
        let result2 = store.get("nonexistent");
        assert(result2.is_none());
    }

    /// Test: Lock blocks put
    fn test_lock_blocks_put() {
        let mut store = KvStore::new();

        // Put initial value
        store.put("key1", 10);

        // Lock the key
        store.lock("key1");
        assert(store.is_locked("key1"));

        // Try to overwrite - should fail
        let success = store.put("key1", 99);
        assert(!success);

        // Value should be unchanged
        assert(store.get("key1") == Some(10u64));
    }

    /// Test: Lock blocks delete
    fn test_lock_blocks_delete() {
        let mut store = KvStore::new();

        // Put initial value
        store.put("key1", 10);

        // Lock the key
        store.lock("key1");

        // Try to delete - should fail
        let success = store.delete("key1");
        assert(!success);

        // Value should still exist
        assert(store.get("key1") == Some(10u64));
    }

    /// Test: Unlock allows modification
    fn test_unlock_allows_put() {
        let mut store = KvStore::new();

        store.put("key1", 10);
        store.lock("key1");

        // Can't modify while locked
        assert(!store.put("key1", 20));

        // Unlock
        store.unlock("key1");
        assert(!store.is_locked("key1"));

        // Now can modify
        let success = store.put("key1", 20);
        assert(success);
        assert(store.get("key1") == Some(20u64));
    }

    /// Test: Rename moves value
    fn test_rename() {
        let mut store = KvStore::new();

        // Setup: put value at "A"
        store.put("A", 123);

        // Lock both keys (required for rename)
        store.lock("A");
        store.lock("B");

        // Rename A -> B
        let result = store.rename("A", "B");

        // Should succeed with the value
        assert(result == Some(123u64));

        // A should be gone, B should have the value
        assert(!store.contains_key("A"));
        assert(store.contains_key("B"));
        assert(store.get("B") == Some(123u64));
    }

    /// Test: Rename non-existent key
    fn test_rename_nonexistent() {
        let mut store = KvStore::new();

        // Lock both keys
        store.lock("A");
        store.lock("B");

        // Rename non-existent A -> B
        let result = store.rename("A", "B");

        // Should return None
        assert(result.is_none());
    }

    /// Test: Multiple keys independent
    fn test_multiple_keys() {
        let mut store = KvStore::new();

        store.put("key1", 1);
        store.put("key2", 2);
        store.put("key3", 3);

        // Lock only key2
        store.lock("key2");

        // Can modify key1 and key3
        assert(store.put("key1", 11));
        assert(store.put("key3", 33));

        // Cannot modify key2
        assert(!store.put("key2", 22));

        // Verify values
        assert(store.get("key1") == Some(11u64));
        assert(store.get("key2") == Some(2u64));  // unchanged
        assert(store.get("key3") == Some(33u64));
    }

    /// Test: New store has txn_id 0
    fn test_new_txn_id() {
        let store = KvStore::new();
        assert(store.get_last_seen_txn_id() == 0);
    }

    /// Test: Stale txn_id detection
    fn test_is_stale_txn_id() {
        let mut store = KvStore::new();

        // Initially, txn_id 0 is stale (equal to last_seen)
        assert(store.is_stale_txn_id(0));

        // txn_id 1 is not stale
        assert(!store.is_stale_txn_id(1));

        // Update to txn_id 5
        store.update_txn_id(5);
        assert(store.get_last_seen_txn_id() == 5);

        // Now 0-5 are stale, 6+ are not
        assert(store.is_stale_txn_id(0));
        assert(store.is_stale_txn_id(3));
        assert(store.is_stale_txn_id(5));
        assert(!store.is_stale_txn_id(6));
    }

    /// Test: Update txn_id only increases
    fn test_update_txn_id_monotonic() {
        let mut store = KvStore::new();

        // Update to 10
        store.update_txn_id(10);
        assert(store.get_last_seen_txn_id() == 10);

        // Try to update to 5 (should be ignored)
        store.update_txn_id(5);
        assert(store.get_last_seen_txn_id() == 10);

        // Update to 15 (should succeed)
        store.update_txn_id(15);
        assert(store.get_last_seen_txn_id() == 15);
    }

    /// Test: txn_id preserved during put
    fn test_txn_id_preserved_put() {
        let mut store = KvStore::new();
        store.update_txn_id(42);

        store.put("key1", 100);
        assert(store.get_last_seen_txn_id() == 42);
    }

    /// Test: txn_id preserved during lock/unlock
    fn test_txn_id_preserved_lock_unlock() {
        let mut store = KvStore::new();
        store.update_txn_id(42);

        store.lock("key1");
        assert(store.get_last_seen_txn_id() == 42);

        store.unlock("key1");
        assert(store.get_last_seen_txn_id() == 42);
    }

    /// Test: txn_id preserved during rename
    fn test_txn_id_preserved_rename() {
        let mut store = KvStore::new();
        store.put("A", 123);
        store.update_txn_id(42);

        store.lock("A");
        store.lock("B");

        store.rename("A", "B");
        assert(store.get_last_seen_txn_id() == 42);
    }

    /// Test: Stale message rejection scenario
    fn test_stale_message_rejection_scenario() {
        let mut store = KvStore::new();

        // Simulate: coordinator sends lock request with txn_id 1
        // Store processes it and updates txn_id
        store.update_txn_id(1);
        store.lock("A");
        store.lock("B");

        // Coordinator crashes and recovers with new txn_id 2
        // Store receives new lock request with txn_id 2
        store.update_txn_id(2);

        // Old message with txn_id 1 arrives (stale)
        assert(store.is_stale_txn_id(1));

        // New message with txn_id 2 is not stale
        assert(!store.is_stale_txn_id(3));
    }
}

} // verus!
