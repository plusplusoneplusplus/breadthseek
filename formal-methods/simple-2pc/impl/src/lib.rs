// lib.rs - KV Store with verification
//
// A verified key-value store with per-key locking for the 2PC protocol.
//
// Structure:
// - kv_store_s: Specification layer (ghost types, lemmas)
// - kv_store_v: Verified executable implementation

use vstd::prelude::*;

pub mod kv_store_s;
pub mod kv_store_v;

// Re-export main types for convenience
pub use kv_store_s::KvStoreSpec;
pub use kv_store_v::KvStore;

verus! {

// ============================================================
// UNIT TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::kv_store_v::KvStore;

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
}

} // verus!
