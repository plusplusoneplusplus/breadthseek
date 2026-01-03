// lib.rs - 2PC Atomic Rename Protocol Implementation
//
// A verified implementation of the 2PC atomic key rename protocol.
//
// Structure:
// - kv_store_s: KV store specification layer (ghost types, lemmas)
// - kv_store_v: Verified executable KV store implementation
// - network_s: Network and message specification layer (ghost)
// - network_v: Verified executable network implementation (mocked with Vec)
// - coordinator_s: Coordinator specification layer (ghost types, lemmas)
// - coordinator_v: Verified executable coordinator implementation
// - system_s: System specification layer (ghost composition)
// - system_v: Verified executable system driver

use vstd::prelude::*;

pub mod kv_store_s;
pub mod kv_store_v;
pub mod network_s;
pub mod network_v;
pub mod coordinator_s;
pub mod coordinator_v;
pub mod system_s;
pub mod system_v;

// Re-export main types for convenience
pub use kv_store_s::KvStoreSpec;
pub use kv_store_v::KvStore;
pub use network_s::{Message, NetworkSpec, StoreId};
pub use network_v::{ExecMessage, ExecNetwork};
pub use coordinator_s::{CoordPhase, CoordinatorSpec};
pub use coordinator_v::Coordinator;
pub use system_s::SystemSpec;
pub use system_v::ExecSystem;
