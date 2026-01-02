// lib.rs - 2PC Atomic Rename Protocol Implementation
//
// A verified implementation of the 2PC atomic key rename protocol.
//
// Structure:
// - kv_store_s: KV store specification layer (ghost types, lemmas)
// - kv_store_v: Verified executable KV store implementation
// - network_s: Network and message specification layer

use vstd::prelude::*;

pub mod kv_store_s;
pub mod kv_store_v;
pub mod network_s;

// Re-export main types for convenience
pub use kv_store_s::KvStoreSpec;
pub use kv_store_v::KvStore;
pub use network_s::{Message, NetworkSpec, StoreId};

