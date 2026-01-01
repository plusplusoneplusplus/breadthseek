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
}

impl View for KvStore {
    type V = KvStoreSpec<u64>;

    /// Connect exec state to spec state
    closed spec fn view(&self) -> KvStoreSpec<u64> {
        KvStoreSpec {
            data: self.data@,
            locked_keys: Set::new(|k: Seq<char>| self.locked@.contains_key(k)),
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

    // ============================================================
    // EXEC FUNCTIONS - Verified implementations
    // ============================================================

    /// Create a new empty KV store
    pub fn new() -> (result: Self)
        ensures
            result@.data == Map::<Seq<char>, u64>::empty(),
            result@.locked_keys == Set::<Seq<char>>::empty(),
    {
        KvStore {
            data: StringHashMap::new(),
            locked: StringHashMap::new(),
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

} // verus!
