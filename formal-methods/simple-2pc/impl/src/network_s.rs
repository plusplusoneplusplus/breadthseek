// network_s.rs - Specification layer for network and messages
//
// This file contains:
// - Message: enum representing protocol messages (matches TLA+ spec)
// - NetworkSpec: ghost struct for network state using Multiset
// - Spec functions for network operations
// - Proof lemmas for network properties
// - Tests for spec verification
//
// Note: Uses Multiset instead of Set to realistically model network duplication.
// - Sending a message adds one copy
// - Losing a message removes one copy (others remain)
// - Multiple copies can exist independently

use vstd::prelude::*;
use vstd::multiset::*;

verus! {

// ============================================================
// STORE IDENTIFIER
// ============================================================

/// Store identifier - represents a KV store in the distributed system
/// Using nat for simplicity; could be made more abstract if needed.
pub type StoreId = nat;

// ============================================================
// MESSAGE TYPES
// ============================================================

/// Transaction ID type - used to prevent stale message interference after crash recovery
pub type TxnId = nat;

/// Protocol messages matching TLA+ spec:
/// - LockReqMsg(s, txnId): Request to lock both A and A' at store s
/// - LockRespMsg(s, ok, txnId): Response with success/failure
/// - RenameReqMsg(s, txnId): Request to rename A -> A' at store s
/// - RenameRespMsg(s, txnId): Confirmation of rename completion
/// - UnlockReqMsg(s, txnId): Request to release locks at store s
/// - UnlockRespMsg(s, txnId): Confirmation of unlock completion
///
/// All messages include txnId to prevent stale messages from old transactions
/// being processed after coordinator crash/recovery.
#[derive(PartialEq, Eq)]
pub ghost enum Message {
    LockReq { store: StoreId, txn_id: TxnId },
    LockResp { store: StoreId, success: bool, txn_id: TxnId },
    RenameReq { store: StoreId, txn_id: TxnId },
    RenameResp { store: StoreId, txn_id: TxnId },
    UnlockReq { store: StoreId, txn_id: TxnId },
    UnlockResp { store: StoreId, txn_id: TxnId },
}

impl Message {
    /// Get the store this message is associated with
    pub open spec fn get_store(&self) -> StoreId {
        match *self {
            Message::LockReq { store, .. } => store,
            Message::LockResp { store, .. } => store,
            Message::RenameReq { store, .. } => store,
            Message::RenameResp { store, .. } => store,
            Message::UnlockReq { store, .. } => store,
            Message::UnlockResp { store, .. } => store,
        }
    }

    /// Get the transaction ID this message is associated with
    pub open spec fn get_txn_id(&self) -> TxnId {
        match *self {
            Message::LockReq { txn_id, .. } => txn_id,
            Message::LockResp { txn_id, .. } => txn_id,
            Message::RenameReq { txn_id, .. } => txn_id,
            Message::RenameResp { txn_id, .. } => txn_id,
            Message::UnlockReq { txn_id, .. } => txn_id,
            Message::UnlockResp { txn_id, .. } => txn_id,
        }
    }

    /// Check if this is a request message (sent by coordinator)
    pub open spec fn is_request(&self) -> bool {
        match *self {
            Message::LockReq { .. } => true,
            Message::RenameReq { .. } => true,
            Message::UnlockReq { .. } => true,
            _ => false,
        }
    }

    /// Check if this is a response message (sent by store)
    pub open spec fn is_response(&self) -> bool {
        match *self {
            Message::LockResp { .. } => true,
            Message::RenameResp { .. } => true,
            Message::UnlockResp { .. } => true,
            _ => false,
        }
    }

    /// Check if this is a successful lock response
    pub open spec fn is_lock_success(&self) -> bool {
        match *self {
            Message::LockResp { success, .. } => success,
            _ => false,
        }
    }

    /// Check if this is a failed lock response
    pub open spec fn is_lock_failure(&self) -> bool {
        match *self {
            Message::LockResp { success, .. } => !success,
            _ => false,
        }
    }
}

// ============================================================
// MESSAGE CONSTRUCTORS (matching TLA+ style)
// ============================================================

/// Create a lock request message
pub open spec fn lock_req_msg(store: StoreId, txn_id: TxnId) -> Message {
    Message::LockReq { store, txn_id }
}

/// Create a lock response message
pub open spec fn lock_resp_msg(store: StoreId, success: bool, txn_id: TxnId) -> Message {
    Message::LockResp { store, success, txn_id }
}

/// Create a rename request message
pub open spec fn rename_req_msg(store: StoreId, txn_id: TxnId) -> Message {
    Message::RenameReq { store, txn_id }
}

/// Create a rename response message
pub open spec fn rename_resp_msg(store: StoreId, txn_id: TxnId) -> Message {
    Message::RenameResp { store, txn_id }
}

/// Create an unlock request message
pub open spec fn unlock_req_msg(store: StoreId, txn_id: TxnId) -> Message {
    Message::UnlockReq { store, txn_id }
}

/// Create an unlock response message
pub open spec fn unlock_resp_msg(store: StoreId, txn_id: TxnId) -> Message {
    Message::UnlockResp { store, txn_id }
}

// ============================================================
// NETWORK SPEC
// ============================================================

/// Spec-level network state (ghost/proof only)
///
/// Models the network as a multiset of in-flight messages.
/// Key properties:
/// - Messages can be duplicated (send adds one copy)
/// - Messages can be lost (lose removes one copy, others remain)
/// - Multiple copies of the same message can exist independently
pub ghost struct NetworkSpec {
    /// Multiset of messages currently in the network
    pub messages: Multiset<Message>,
}

impl NetworkSpec {
    // ============================================================
    // SPEC FUNCTIONS - State observations
    // ============================================================

    /// Check if a message is in the network (at least one copy)
    pub open spec fn contains(&self, msg: Message) -> bool {
        self.messages.count(msg) > 0
    }

    /// Count how many copies of a message are in the network
    pub open spec fn count(&self, msg: Message) -> nat {
        self.messages.count(msg)
    }

    /// Check if network is empty
    pub open spec fn is_empty(&self) -> bool {
        self.messages =~= Multiset::empty()
    }

    /// Check if there's a lock request for a store with specific txn_id
    pub open spec fn has_lock_req(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(lock_req_msg(store, txn_id))
    }

    /// Check if there's a successful lock response for a store with specific txn_id
    pub open spec fn has_lock_resp_success(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(lock_resp_msg(store, true, txn_id))
    }

    /// Check if there's a failed lock response for a store with specific txn_id
    pub open spec fn has_lock_resp_failure(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(lock_resp_msg(store, false, txn_id))
    }

    /// Check if there's a rename request for a store with specific txn_id
    pub open spec fn has_rename_req(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(rename_req_msg(store, txn_id))
    }

    /// Check if there's a rename response for a store with specific txn_id
    pub open spec fn has_rename_resp(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(rename_resp_msg(store, txn_id))
    }

    /// Check if there's an unlock request for a store with specific txn_id
    pub open spec fn has_unlock_req(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(unlock_req_msg(store, txn_id))
    }

    /// Check if there's an unlock response for a store with specific txn_id
    pub open spec fn has_unlock_resp(&self, store: StoreId, txn_id: TxnId) -> bool {
        self.contains(unlock_resp_msg(store, txn_id))
    }

    // ============================================================
    // SPEC FUNCTIONS - State transitions
    // ============================================================

    /// Create empty network
    pub open spec fn empty() -> Self {
        NetworkSpec {
            messages: Multiset::empty(),
        }
    }

    /// Send a message (add one copy to network)
    /// NOT idempotent: sending twice creates two copies
    pub open spec fn send(self, msg: Message) -> Self {
        NetworkSpec {
            messages: self.messages.insert(msg),
        }
    }

    /// Lose a message (remove one copy from network)
    /// If multiple copies exist, only one is removed
    pub open spec fn lose(self, msg: Message) -> Self {
        NetworkSpec {
            messages: self.messages.remove(msg),
        }
    }

    /// Duplicate a message (add another copy of an existing message)
    /// Models network-level packet duplication
    pub open spec fn duplicate(self, msg: Message) -> Self
        recommends self.contains(msg)
    {
        NetworkSpec {
            messages: self.messages.insert(msg),
        }
    }

    /// Receive a message (message stays in network for idempotency)
    /// This is a no-op on state; receiving just observes the message.
    /// Use lose() if you want to model message consumption.
    pub open spec fn receive(self, msg: Message) -> Self
        recommends self.contains(msg)
    {
        self // Message stays for idempotency
    }

    // ============================================================
    // PROOF LEMMAS - Properties of network operations
    // ============================================================

    /// Send increases count by 1
    pub proof fn lemma_send_increases_count(self, msg: Message)
        ensures
            self.send(msg).count(msg) == self.count(msg) + 1
    {
    }

    /// Send then check: after send, message is in network
    pub proof fn lemma_send_contains(self, msg: Message)
        ensures
            self.send(msg).contains(msg)
    {
    }

    /// Lose decreases count by 1 (if message exists)
    pub proof fn lemma_lose_decreases_count(self, msg: Message)
        requires
            self.contains(msg)
        ensures
            self.lose(msg).count(msg) == self.count(msg) - 1
    {
    }

    /// Lose preserves existence if multiple copies
    pub proof fn lemma_lose_preserves_if_multiple(self, msg: Message)
        requires
            self.count(msg) >= 2
        ensures
            self.lose(msg).contains(msg)
    {
    }

    /// Lose removes last copy
    pub proof fn lemma_lose_removes_last(self, msg: Message)
        requires
            self.count(msg) == 1
        ensures
            !self.lose(msg).contains(msg)
    {
    }

    /// Send preserves other messages
    pub proof fn lemma_send_preserves_others(self, msg: Message, other: Message)
        requires
            msg != other
        ensures
            self.send(msg).count(other) == self.count(other)
    {
    }

    /// Lose preserves other messages
    pub proof fn lemma_lose_preserves_others(self, msg: Message, other: Message)
        requires
            msg != other
        ensures
            self.lose(msg).count(other) == self.count(other)
    {
    }

    /// Empty network contains no messages
    pub proof fn lemma_empty_contains_nothing(msg: Message)
        ensures
            !Self::empty().contains(msg),
            Self::empty().count(msg) == 0
    {
    }

    /// Send to empty creates network with one copy
    pub proof fn lemma_empty_send_count(msg: Message)
        ensures
            Self::empty().send(msg).count(msg) == 1,
            Self::empty().send(msg).contains(msg)
    {
    }

    /// Duplicate increases count (same as send)
    pub proof fn lemma_duplicate_increases_count(self, msg: Message)
        requires
            self.contains(msg)
        ensures
            self.duplicate(msg).count(msg) == self.count(msg) + 1
    {
    }

    /// Send twice creates two copies
    pub proof fn lemma_send_twice_creates_two(msg: Message)
        ensures
            Self::empty().send(msg).send(msg).count(msg) == 2
    {
    }

    /// Lose one of two copies leaves one
    pub proof fn lemma_lose_one_of_two(msg: Message)
        ensures
            Self::empty().send(msg).send(msg).lose(msg).count(msg) == 1,
            Self::empty().send(msg).send(msg).lose(msg).contains(msg)
    {
    }

    /// Different message types are distinct (with same store and txn_id)
    pub proof fn lemma_message_types_distinct(store: StoreId, txn_id: TxnId)
        ensures
            lock_req_msg(store, txn_id) != lock_resp_msg(store, true, txn_id),
            lock_req_msg(store, txn_id) != lock_resp_msg(store, false, txn_id),
            lock_req_msg(store, txn_id) != rename_req_msg(store, txn_id),
            lock_req_msg(store, txn_id) != rename_resp_msg(store, txn_id),
            lock_req_msg(store, txn_id) != unlock_req_msg(store, txn_id),
            lock_req_msg(store, txn_id) != unlock_resp_msg(store, txn_id),
            lock_resp_msg(store, true, txn_id) != lock_resp_msg(store, false, txn_id),
            rename_req_msg(store, txn_id) != rename_resp_msg(store, txn_id),
            unlock_req_msg(store, txn_id) != unlock_resp_msg(store, txn_id),
    {
    }

    /// Messages for different stores are distinct (with same txn_id)
    pub proof fn lemma_different_stores_distinct(s1: StoreId, s2: StoreId, txn_id: TxnId)
        requires
            s1 != s2
        ensures
            lock_req_msg(s1, txn_id) != lock_req_msg(s2, txn_id),
            lock_resp_msg(s1, true, txn_id) != lock_resp_msg(s2, true, txn_id),
            rename_req_msg(s1, txn_id) != rename_req_msg(s2, txn_id),
            rename_resp_msg(s1, txn_id) != rename_resp_msg(s2, txn_id),
            unlock_req_msg(s1, txn_id) != unlock_req_msg(s2, txn_id),
            unlock_resp_msg(s1, txn_id) != unlock_resp_msg(s2, txn_id),
    {
    }

    /// Messages with different txn_ids are distinct (same store, same type)
    pub proof fn lemma_different_txn_ids_distinct(store: StoreId, t1: TxnId, t2: TxnId)
        requires
            t1 != t2
        ensures
            lock_req_msg(store, t1) != lock_req_msg(store, t2),
            lock_resp_msg(store, true, t1) != lock_resp_msg(store, true, t2),
            rename_req_msg(store, t1) != rename_req_msg(store, t2),
            rename_resp_msg(store, t1) != rename_resp_msg(store, t2),
            unlock_req_msg(store, t1) != unlock_req_msg(store, t2),
            unlock_resp_msg(store, t1) != unlock_resp_msg(store, t2),
    {
    }
}

// ============================================================
// TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    // Default txn_id for tests
    spec fn default_txn_id() -> TxnId { 1 }

    /// Test: Empty network contains no messages
    proof fn test_empty_network() {
        let net = NetworkSpec::empty();
        let txn_id = default_txn_id();
        assert(net.is_empty());
        assert(!net.contains(lock_req_msg(0, txn_id)));
        assert(net.count(lock_req_msg(0, txn_id)) == 0);
    }

    /// Test: Send adds one copy to network
    proof fn test_send_message() {
        let net = NetworkSpec::empty();
        let txn_id = default_txn_id();
        let msg = lock_req_msg(1, txn_id);

        let net2 = net.send(msg);

        net.lemma_send_contains(msg);
        assert(net2.contains(msg));
        assert(net2.count(msg) == 1);
    }

    /// Test: Send is NOT idempotent - sends accumulate
    proof fn test_send_not_idempotent() {
        let net = NetworkSpec::empty();
        let txn_id = default_txn_id();
        let msg = lock_req_msg(1, txn_id);

        let net1 = net.send(msg);
        let net2 = net1.send(msg);

        // Two sends create two copies
        NetworkSpec::lemma_send_twice_creates_two(msg);
        assert(net1.count(msg) == 1);
        assert(net2.count(msg) == 2);
        assert(net1 != net2);
    }

    /// Test: Lose removes one copy
    proof fn test_lose_one_copy() {
        let txn_id = default_txn_id();
        let net = NetworkSpec::empty().send(lock_req_msg(1, txn_id)).send(lock_req_msg(1, txn_id));
        let msg = lock_req_msg(1, txn_id);

        assert(net.count(msg) == 2);

        let net2 = net.lose(msg);

        // One copy remains
        NetworkSpec::lemma_lose_one_of_two(msg);
        assert(net2.count(msg) == 1);
        assert(net2.contains(msg));
    }

    /// Test: Lose removes last copy
    proof fn test_lose_last_copy() {
        let txn_id = default_txn_id();
        let net = NetworkSpec::empty().send(lock_req_msg(1, txn_id));
        let msg = lock_req_msg(1, txn_id);

        assert(net.count(msg) == 1);

        let net2 = net.lose(msg);

        net.lemma_lose_removes_last(msg);
        assert(net2.count(msg) == 0);
        assert(!net2.contains(msg));
    }

    /// Test: Send preserves other messages
    proof fn test_send_preserves_others() {
        let net = NetworkSpec::empty();
        let txn_id = default_txn_id();
        let msg1 = lock_req_msg(1, txn_id);
        let msg2 = lock_req_msg(2, txn_id);

        let net1 = net.send(msg1);
        let net2 = net1.send(msg2);

        net1.lemma_send_preserves_others(msg2, msg1);
        assert(net2.count(msg1) == 1);
        assert(net2.count(msg2) == 1);
    }

    /// Test: Lose preserves other messages
    proof fn test_lose_preserves_others() {
        let txn_id = default_txn_id();
        let net = NetworkSpec::empty().send(lock_req_msg(1, txn_id)).send(lock_req_msg(2, txn_id));
        let msg1 = lock_req_msg(1, txn_id);
        let msg2 = lock_req_msg(2, txn_id);

        let net2 = net.lose(msg1);

        net.lemma_lose_preserves_others(msg1, msg2);
        assert(!net2.contains(msg1));
        assert(net2.contains(msg2));
    }

    /// Test: Message type predicates
    proof fn test_message_predicates() {
        let txn_id = default_txn_id();
        let lock_req = lock_req_msg(1, txn_id);
        let lock_resp_ok = lock_resp_msg(1, true, txn_id);
        let lock_resp_fail = lock_resp_msg(1, false, txn_id);
        let rename_req = rename_req_msg(1, txn_id);
        let rename_resp = rename_resp_msg(1, txn_id);
        let unlock_req = unlock_req_msg(1, txn_id);
        let unlock_resp = unlock_resp_msg(1, txn_id);

        // Request/response classification
        assert(lock_req.is_request());
        assert(!lock_req.is_response());

        assert(!lock_resp_ok.is_request());
        assert(lock_resp_ok.is_response());

        assert(rename_req.is_request());
        assert(rename_resp.is_response());

        assert(unlock_req.is_request());
        assert(!unlock_req.is_response());

        assert(!unlock_resp.is_request());
        assert(unlock_resp.is_response());

        // Lock response success/failure
        assert(lock_resp_ok.is_lock_success());
        assert(!lock_resp_ok.is_lock_failure());

        assert(!lock_resp_fail.is_lock_success());
        assert(lock_resp_fail.is_lock_failure());
    }

    /// Test: Store accessor
    proof fn test_get_store() {
        let txn_id = default_txn_id();
        assert(lock_req_msg(5, txn_id).get_store() == 5);
        assert(lock_resp_msg(3, true, txn_id).get_store() == 3);
        assert(rename_req_msg(7, txn_id).get_store() == 7);
        assert(rename_resp_msg(2, txn_id).get_store() == 2);
        assert(unlock_req_msg(9, txn_id).get_store() == 9);
        assert(unlock_resp_msg(4, txn_id).get_store() == 4);
    }

    /// Test: TxnId accessor
    proof fn test_get_txn_id() {
        let txn_id: TxnId = 42;
        assert(lock_req_msg(5, txn_id).get_txn_id() == 42);
        assert(lock_resp_msg(3, true, txn_id).get_txn_id() == 42);
        assert(rename_req_msg(7, txn_id).get_txn_id() == 42);
        assert(rename_resp_msg(2, txn_id).get_txn_id() == 42);
        assert(unlock_req_msg(9, txn_id).get_txn_id() == 42);
        assert(unlock_resp_msg(4, txn_id).get_txn_id() == 42);
    }

    /// Test: Convenience methods
    proof fn test_convenience_methods() {
        let txn_id = default_txn_id();
        let net = NetworkSpec::empty()
            .send(lock_req_msg(1, txn_id))
            .send(lock_resp_msg(1, true, txn_id))
            .send(rename_req_msg(2, txn_id))
            .send(unlock_resp_msg(3, txn_id));

        assert(net.has_lock_req(1, txn_id));
        assert(!net.has_lock_req(2, txn_id));

        assert(net.has_lock_resp_success(1, txn_id));
        assert(!net.has_lock_resp_failure(1, txn_id));

        assert(net.has_rename_req(2, txn_id));
        assert(!net.has_rename_resp(2, txn_id));

        assert(net.has_unlock_resp(3, txn_id));
        assert(!net.has_unlock_req(3, txn_id));
    }

    /// Test: Duplicate adds another copy
    proof fn test_duplicate() {
        let txn_id = default_txn_id();
        let msg = lock_req_msg(1, txn_id);
        let net = NetworkSpec::empty().send(msg);

        assert(net.count(msg) == 1);

        let net2 = net.duplicate(msg);

        net.lemma_duplicate_increases_count(msg);
        assert(net2.count(msg) == 2);
    }

    /// Test: Different message types are distinct
    proof fn test_message_distinctness() {
        let txn_id = default_txn_id();
        NetworkSpec::lemma_message_types_distinct(1, txn_id);

        assert(lock_req_msg(1, txn_id) != lock_resp_msg(1, true, txn_id));
        assert(lock_req_msg(1, txn_id) != rename_req_msg(1, txn_id));
        assert(lock_resp_msg(1, true, txn_id) != lock_resp_msg(1, false, txn_id));
        assert(unlock_req_msg(1, txn_id) != unlock_resp_msg(1, txn_id));
    }

    /// Test: Messages for different stores are distinct
    proof fn test_different_stores() {
        let txn_id = default_txn_id();
        NetworkSpec::lemma_different_stores_distinct(1, 2, txn_id);

        assert(lock_req_msg(1, txn_id) != lock_req_msg(2, txn_id));
        assert(rename_resp_msg(1, txn_id) != rename_resp_msg(2, txn_id));
        assert(unlock_resp_msg(1, txn_id) != unlock_resp_msg(2, txn_id));
    }

    /// Test: Realistic duplication scenario
    /// Network duplicates a message, one copy is lost, receiver still gets it
    proof fn test_duplication_then_loss() {
        let txn_id = default_txn_id();
        let msg = lock_req_msg(1, txn_id);

        // Send message
        let net1 = NetworkSpec::empty().send(msg);
        assert(net1.count(msg) == 1);

        // Network duplicates it
        let net2 = net1.duplicate(msg);
        assert(net2.count(msg) == 2);

        // One copy is lost
        let net3 = net2.lose(msg);
        assert(net3.count(msg) == 1);

        // Message still available for receiver
        assert(net3.contains(msg));
    }

    /// Test: Messages with different txn_ids are distinct
    proof fn test_different_txn_ids() {
        let txn1: TxnId = 1;
        let txn2: TxnId = 2;

        NetworkSpec::lemma_different_txn_ids_distinct(1, txn1, txn2);

        assert(lock_req_msg(1, txn1) != lock_req_msg(1, txn2));
        assert(lock_resp_msg(1, true, txn1) != lock_resp_msg(1, true, txn2));
        assert(unlock_resp_msg(1, txn1) != unlock_resp_msg(1, txn2));
    }

    /// Test: Stale message scenario
    /// Old txn_id message is different from new txn_id message
    proof fn test_stale_vs_new_message() {
        let old_txn: TxnId = 1;
        let new_txn: TxnId = 2;

        let old_lock_req = lock_req_msg(1, old_txn);
        let new_lock_req = lock_req_msg(1, new_txn);

        // Same store, same message type, but different txn_ids
        assert(old_lock_req != new_lock_req);
        assert(old_lock_req.get_store() == new_lock_req.get_store());
        assert(old_lock_req.get_txn_id() < new_lock_req.get_txn_id());

        // Network can contain both
        let net = NetworkSpec::empty().send(old_lock_req).send(new_lock_req);
        assert(net.contains(old_lock_req));
        assert(net.contains(new_lock_req));
        assert(net.count(old_lock_req) == 1);
        assert(net.count(new_lock_req) == 1);
    }
}

} // verus!
