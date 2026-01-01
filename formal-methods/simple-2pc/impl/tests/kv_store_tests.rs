// Runtime tests for the executable KvStore implementation.
// These mirror the verified tests in src/lib.rs but run under `cargo test`.

use kv_store::KvStore;

#[test]
fn test_new() {
    let store = KvStore::new();
    assert!(!store.contains_key("any_key"));
    assert!(!store.is_locked("any_key"));
}

#[test]
fn test_put_get() {
    let mut store = KvStore::new();

    let success = store.put("key1", 42);
    assert!(success);

    let result = store.get("key1");
    assert_eq!(result, Some(42u64));

    let result2 = store.get("nonexistent");
    assert_eq!(result2, None);
}

#[test]
fn test_lock_blocks_put() {
    let mut store = KvStore::new();

    store.put("key1", 10);

    store.lock("key1");
    assert!(store.is_locked("key1"));

    let success = store.put("key1", 99);
    assert!(!success);
    assert_eq!(store.get("key1"), Some(10u64));
}

#[test]
fn test_lock_blocks_delete() {
    let mut store = KvStore::new();

    store.put("key1", 10);
    store.lock("key1");

    let success = store.delete("key1");
    assert!(!success);
    assert_eq!(store.get("key1"), Some(10u64));
}

#[test]
fn test_unlock_allows_put() {
    let mut store = KvStore::new();

    store.put("key1", 10);
    store.lock("key1");
    assert!(!store.put("key1", 20));

    store.unlock("key1");
    assert!(!store.is_locked("key1"));

    let success = store.put("key1", 20);
    assert!(success);
    assert_eq!(store.get("key1"), Some(20u64));
}

#[test]
fn test_rename_moves_value() {
    let mut store = KvStore::new();

    store.put("A", 123);

    // Precondition for rename: both keys must be locked and distinct
    store.lock("A");
    store.lock("B");

    let result = store.rename("A", "B");
    assert_eq!(result, Some(123u64));

    assert!(!store.contains_key("A"));
    assert!(store.contains_key("B"));
    assert_eq!(store.get("B"), Some(123u64));
}

#[test]
fn test_rename_nonexistent() {
    let mut store = KvStore::new();

    store.lock("A");
    store.lock("B");

    let result = store.rename("A", "B");
    assert_eq!(result, None);
}

#[test]
fn test_multiple_keys_independent() {
    let mut store = KvStore::new();

    store.put("key1", 1);
    store.put("key2", 2);
    store.put("key3", 3);

    store.lock("key2");

    assert!(store.put("key1", 11));
    assert!(store.put("key3", 33));
    assert!(!store.put("key2", 22));

    assert_eq!(store.get("key1"), Some(11u64));
    assert_eq!(store.get("key2"), Some(2u64));
    assert_eq!(store.get("key3"), Some(33u64));
}

