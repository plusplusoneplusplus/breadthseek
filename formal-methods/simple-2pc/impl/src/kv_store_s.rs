// kv_store_s.rs - Specification layer for KV store
//
// This file contains:
// - KvStoreSpec: ghost struct for verification
// - Spec functions for state transitions
// - Proof lemmas (prefixed with lemma_)
// - Protocol invariants

use vstd::prelude::*;

verus! {

// ============================================================
// SPEC TYPES
// ============================================================

/// Spec-level key-value store (ghost/proof only)
/// This is the abstract model used for verification.
pub ghost struct KvStoreSpec<V> {
    /// The actual key-value data
    pub data: Map<Seq<char>, V>,
    /// Set of currently locked keys
    pub locked_keys: Set<Seq<char>>,
}

impl<V> KvStoreSpec<V> {
    // ============================================================
    // SPEC FUNCTIONS - State observations
    // ============================================================

    /// Check if a key is locked
    pub open spec fn is_locked(&self, key: Seq<char>) -> bool {
        self.locked_keys.contains(key)
    }

    /// Check if a key exists
    pub open spec fn contains_key(&self, key: Seq<char>) -> bool {
        self.data.contains_key(key)
    }

    /// Get value for key (only meaningful if key exists)
    pub open spec fn get(&self, key: Seq<char>) -> V
        recommends self.contains_key(key)
    {
        self.data[key]
    }

    // ============================================================
    // SPEC FUNCTIONS - State transitions
    // ============================================================

    /// Create empty store
    pub open spec fn empty() -> Self {
        KvStoreSpec {
            data: Map::empty(),
            locked_keys: Set::empty(),
        }
    }

    /// Put a value (only if not locked)
    pub open spec fn put(self, key: Seq<char>, value: V) -> Self {
        if self.is_locked(key) {
            self
        } else {
            KvStoreSpec {
                data: self.data.insert(key, value),
                locked_keys: self.locked_keys,
            }
        }
    }

    /// Delete a key (only if not locked)
    pub open spec fn delete(self, key: Seq<char>) -> Self {
        if self.is_locked(key) {
            self
        } else {
            KvStoreSpec {
                data: self.data.remove(key),
                locked_keys: self.locked_keys,
            }
        }
    }

    /// Lock a key (idempotent)
    pub open spec fn lock(self, key: Seq<char>) -> Self {
        KvStoreSpec {
            data: self.data,
            locked_keys: self.locked_keys.insert(key),
        }
    }

    /// Unlock a key (idempotent)
    pub open spec fn unlock(self, key: Seq<char>) -> Self {
        KvStoreSpec {
            data: self.data,
            locked_keys: self.locked_keys.remove(key),
        }
    }

    /// Rename: move value from old_key to new_key
    pub open spec fn rename(self, old_key: Seq<char>, new_key: Seq<char>) -> Self
        recommends
            self.is_locked(old_key),
            self.is_locked(new_key),
            self.contains_key(old_key),
    {
        let value = self.data[old_key];
        KvStoreSpec {
            data: self.data.remove(old_key).insert(new_key, value),
            locked_keys: self.locked_keys,
        }
    }

    // ============================================================
    // PROOF LEMMAS - Properties of operations
    // ============================================================

    /// Lock is idempotent: lock(lock(s)) == lock(s)
    pub proof fn lemma_lock_idempotent(self, key: Seq<char>)
        ensures
            self.lock(key).lock(key) == self.lock(key)
    {
        assert(self.locked_keys.insert(key).insert(key) =~= self.locked_keys.insert(key));
    }

    /// Unlock is idempotent: unlock(unlock(s)) == unlock(s)
    pub proof fn lemma_unlock_idempotent(self, key: Seq<char>)
        ensures
            self.unlock(key).unlock(key) == self.unlock(key)
    {
        assert(self.locked_keys.remove(key).remove(key) =~= self.locked_keys.remove(key));
    }

    /// Put on locked key is no-op
    pub proof fn lemma_put_locked_noop(self, key: Seq<char>, value: V)
        requires
            self.is_locked(key)
        ensures
            self.put(key, value) == self
    {
    }

    /// Delete on locked key is no-op
    pub proof fn lemma_delete_locked_noop(self, key: Seq<char>)
        requires
            self.is_locked(key)
        ensures
            self.delete(key) == self
    {
    }

    /// Lock preserves data
    pub proof fn lemma_lock_preserves_data(self, key: Seq<char>)
        ensures
            self.lock(key).data == self.data
    {
    }

    /// Unlock preserves data
    pub proof fn lemma_unlock_preserves_data(self, key: Seq<char>)
        ensures
            self.unlock(key).data == self.data
    {
    }

    /// Rename preserves value and moves it atomically
    pub proof fn lemma_rename_preserves_value(self, old_key: Seq<char>, new_key: Seq<char>)
        requires
            self.is_locked(old_key),
            self.is_locked(new_key),
            self.contains_key(old_key),
            old_key != new_key,
        ensures
            self.rename(old_key, new_key).contains_key(new_key),
            self.rename(old_key, new_key).get(new_key) == self.get(old_key),
            !self.rename(old_key, new_key).contains_key(old_key),
    {
        let new_store = self.rename(old_key, new_key);
        let value = self.data[old_key];
        assert(new_store.data.contains_key(new_key));
        assert(new_store.data[new_key] == value);
        assert(!new_store.data.contains_key(old_key));
    }
}

// ============================================================
// PROTOCOL INVARIANTS
// ============================================================

/// Invariant: Data is always accessible at exactly one of {A, A'}
/// This is the key safety property for the 2PC rename protocol.
pub open spec fn data_accessible<V>(
    store: KvStoreSpec<V>,
    key_a: Seq<char>,
    key_aprime: Seq<char>,
) -> bool {
    (store.contains_key(key_a) && !store.contains_key(key_aprime))
    || (!store.contains_key(key_a) && store.contains_key(key_aprime))
}

/// Rename preserves the data_accessible invariant
pub proof fn lemma_data_accessible_preserved<V>(
    store: KvStoreSpec<V>,
    key_a: Seq<char>,
    key_aprime: Seq<char>,
)
    requires
        store.is_locked(key_a),
        store.is_locked(key_aprime),
        store.contains_key(key_a),
        !store.contains_key(key_aprime),
        key_a != key_aprime,
    ensures
        data_accessible(store, key_a, key_aprime),
        data_accessible(store.rename(key_a, key_aprime), key_a, key_aprime),
{
    let new_store = store.rename(key_a, key_aprime);
    store.lemma_rename_preserves_value(key_a, key_aprime);
    assert(store.contains_key(key_a));
    assert(!store.contains_key(key_aprime));
    assert(!new_store.contains_key(key_a));
    assert(new_store.contains_key(key_aprime));
}

} // verus!
