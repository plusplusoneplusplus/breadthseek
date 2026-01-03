// network_v.rs - Verified executable implementation of Network and Messages
//
// This file contains:
// - ExecMessage: executable message enum (mirrors ghost Message)
// - ExecNetwork: executable network using Vec as a message queue (mocked network)
// - View implementations connecting exec to spec
// - Verified exec functions with postconditions

use vstd::prelude::*;

use crate::network_s::*;

verus! {

// ============================================================
// EXECUTABLE MESSAGE TYPE
// ============================================================

/// Executable message type - mirrors the ghost Message enum
/// Uses u64 for StoreId and TxnId to match exec types
pub enum ExecMessage {
    LockReq { store: u64, txn_id: u64 },
    LockResp { store: u64, success: bool, txn_id: u64 },
    RenameReq { store: u64, txn_id: u64 },
    RenameResp { store: u64, txn_id: u64 },
    UnlockReq { store: u64, txn_id: u64 },
    UnlockResp { store: u64, txn_id: u64 },
}

impl ExecMessage {
    /// Check equality with another message
    pub fn eq(&self, other: &Self) -> (result: bool)
        ensures
            result == (self@ == other@)
    {
        match (self, other) {
            (ExecMessage::LockReq { store: s1, txn_id: t1 },
             ExecMessage::LockReq { store: s2, txn_id: t2 }) => *s1 == *s2 && *t1 == *t2,
            (ExecMessage::LockResp { store: s1, success: ok1, txn_id: t1 },
             ExecMessage::LockResp { store: s2, success: ok2, txn_id: t2 }) => *s1 == *s2 && *ok1 == *ok2 && *t1 == *t2,
            (ExecMessage::RenameReq { store: s1, txn_id: t1 },
             ExecMessage::RenameReq { store: s2, txn_id: t2 }) => *s1 == *s2 && *t1 == *t2,
            (ExecMessage::RenameResp { store: s1, txn_id: t1 },
             ExecMessage::RenameResp { store: s2, txn_id: t2 }) => *s1 == *s2 && *t1 == *t2,
            (ExecMessage::UnlockReq { store: s1, txn_id: t1 },
             ExecMessage::UnlockReq { store: s2, txn_id: t2 }) => *s1 == *s2 && *t1 == *t2,
            (ExecMessage::UnlockResp { store: s1, txn_id: t1 },
             ExecMessage::UnlockResp { store: s2, txn_id: t2 }) => *s1 == *s2 && *t1 == *t2,
            _ => false,
        }
    }

    /// Clone the message
    pub fn clone(&self) -> (result: Self)
        ensures
            result@ == self@
    {
        match self {
            ExecMessage::LockReq { store, txn_id } =>
                ExecMessage::LockReq { store: *store, txn_id: *txn_id },
            ExecMessage::LockResp { store, success, txn_id } =>
                ExecMessage::LockResp { store: *store, success: *success, txn_id: *txn_id },
            ExecMessage::RenameReq { store, txn_id } =>
                ExecMessage::RenameReq { store: *store, txn_id: *txn_id },
            ExecMessage::RenameResp { store, txn_id } =>
                ExecMessage::RenameResp { store: *store, txn_id: *txn_id },
            ExecMessage::UnlockReq { store, txn_id } =>
                ExecMessage::UnlockReq { store: *store, txn_id: *txn_id },
            ExecMessage::UnlockResp { store, txn_id } =>
                ExecMessage::UnlockResp { store: *store, txn_id: *txn_id },
        }
    }
}

impl View for ExecMessage {
    type V = Message;

    open spec fn view(&self) -> Message {
        match *self {
            ExecMessage::LockReq { store, txn_id } =>
                Message::LockReq { store: store as nat, txn_id: txn_id as nat },
            ExecMessage::LockResp { store, success, txn_id } =>
                Message::LockResp { store: store as nat, success, txn_id: txn_id as nat },
            ExecMessage::RenameReq { store, txn_id } =>
                Message::RenameReq { store: store as nat, txn_id: txn_id as nat },
            ExecMessage::RenameResp { store, txn_id } =>
                Message::RenameResp { store: store as nat, txn_id: txn_id as nat },
            ExecMessage::UnlockReq { store, txn_id } =>
                Message::UnlockReq { store: store as nat, txn_id: txn_id as nat },
            ExecMessage::UnlockResp { store, txn_id } =>
                Message::UnlockResp { store: store as nat, txn_id: txn_id as nat },
        }
    }
}

impl ExecMessage {
    // ============================================================
    // CONSTRUCTORS
    // ============================================================

    /// Create a lock request message
    pub fn lock_req(store: u64, txn_id: u64) -> (result: Self)
        ensures
            result@ == lock_req_msg(store as nat, txn_id as nat)
    {
        ExecMessage::LockReq { store, txn_id }
    }

    /// Create a lock response message
    pub fn lock_resp(store: u64, success: bool, txn_id: u64) -> (result: Self)
        ensures
            result@ == lock_resp_msg(store as nat, success, txn_id as nat)
    {
        ExecMessage::LockResp { store, success, txn_id }
    }

    /// Create a rename request message
    pub fn rename_req(store: u64, txn_id: u64) -> (result: Self)
        ensures
            result@ == rename_req_msg(store as nat, txn_id as nat)
    {
        ExecMessage::RenameReq { store, txn_id }
    }

    /// Create a rename response message
    pub fn rename_resp(store: u64, txn_id: u64) -> (result: Self)
        ensures
            result@ == rename_resp_msg(store as nat, txn_id as nat)
    {
        ExecMessage::RenameResp { store, txn_id }
    }

    /// Create an unlock request message
    pub fn unlock_req(store: u64, txn_id: u64) -> (result: Self)
        ensures
            result@ == unlock_req_msg(store as nat, txn_id as nat)
    {
        ExecMessage::UnlockReq { store, txn_id }
    }

    /// Create an unlock response message
    pub fn unlock_resp(store: u64, txn_id: u64) -> (result: Self)
        ensures
            result@ == unlock_resp_msg(store as nat, txn_id as nat)
    {
        ExecMessage::UnlockResp { store, txn_id }
    }

    // ============================================================
    // ACCESSORS
    // ============================================================

    /// Get the store ID from the message
    pub fn get_store(&self) -> (result: u64)
        ensures
            result as nat == self@.get_store()
    {
        match self {
            ExecMessage::LockReq { store, .. } => *store,
            ExecMessage::LockResp { store, .. } => *store,
            ExecMessage::RenameReq { store, .. } => *store,
            ExecMessage::RenameResp { store, .. } => *store,
            ExecMessage::UnlockReq { store, .. } => *store,
            ExecMessage::UnlockResp { store, .. } => *store,
        }
    }

    /// Get the transaction ID from the message
    pub fn get_txn_id(&self) -> (result: u64)
        ensures
            result as nat == self@.get_txn_id()
    {
        match self {
            ExecMessage::LockReq { txn_id, .. } => *txn_id,
            ExecMessage::LockResp { txn_id, .. } => *txn_id,
            ExecMessage::RenameReq { txn_id, .. } => *txn_id,
            ExecMessage::RenameResp { txn_id, .. } => *txn_id,
            ExecMessage::UnlockReq { txn_id, .. } => *txn_id,
            ExecMessage::UnlockResp { txn_id, .. } => *txn_id,
        }
    }

    /// Check if this is a request message
    pub fn is_request(&self) -> (result: bool)
        ensures
            result == self@.is_request()
    {
        match self {
            ExecMessage::LockReq { .. } => true,
            ExecMessage::RenameReq { .. } => true,
            ExecMessage::UnlockReq { .. } => true,
            _ => false,
        }
    }

    /// Check if this is a response message
    pub fn is_response(&self) -> (result: bool)
        ensures
            result == self@.is_response()
    {
        match self {
            ExecMessage::LockResp { .. } => true,
            ExecMessage::RenameResp { .. } => true,
            ExecMessage::UnlockResp { .. } => true,
            _ => false,
        }
    }

    /// Check if this is a successful lock response
    pub fn is_lock_success(&self) -> (result: bool)
        ensures
            result == self@.is_lock_success()
    {
        match self {
            ExecMessage::LockResp { success, .. } => *success,
            _ => false,
        }
    }

    /// Check if this is a failed lock response
    pub fn is_lock_failure(&self) -> (result: bool)
        ensures
            result == self@.is_lock_failure()
    {
        match self {
            ExecMessage::LockResp { success, .. } => !*success,
            _ => false,
        }
    }
}

// ============================================================
// EXECUTABLE NETWORK (MOCKED WITH VEC)
// ============================================================

/// Executable network implementation using Vec as a message queue.
/// This is a mocked/simulated network for testing purposes.
/// 
/// Key properties:
/// - Messages are stored in a Vec (FIFO queue semantics for receive)
/// - send() appends to the queue
/// - receive() removes and returns the first matching message
/// - lose() removes one copy of a message (simulates network loss)
/// - duplicate() adds another copy (simulates network duplication)
pub struct ExecNetwork {
    /// Message queue - stores in-flight messages
    pub messages: Vec<ExecMessage>,
}

impl ExecNetwork {
    // ============================================================
    // SPEC HELPERS
    // ============================================================

    /// Spec function: check if message exists at index i
    pub open spec fn spec_msg_at(&self, i: int) -> Message
        recommends 0 <= i < self.messages@.len()
    {
        self.messages@[i]@
    }

    /// Spec function: check if network is empty
    pub open spec fn spec_is_empty(&self) -> bool {
        self.messages@.len() == 0
    }

    /// Spec function: check if message exists in the queue (by view equality)
    pub open spec fn spec_contains(&self, msg: Message) -> bool {
        exists|i: int| 0 <= i < self.messages@.len() && self.messages@[i]@ == msg
    }

    // ============================================================
    // EXEC FUNCTIONS
    // ============================================================

    /// Create a new empty network
    pub fn new() -> (result: Self)
        ensures
            result.spec_is_empty(),
            !result.spec_contains(lock_req_msg(0, 0)),  // example: empty means no messages
    {
        ExecNetwork { messages: Vec::new() }
    }

    /// Send a message (add to the queue)
    pub fn send(&mut self, msg: ExecMessage)
        ensures
            self.spec_contains(msg@),
            self.messages@.len() == old(self).messages@.len() + 1,
    {
        let ghost old_len = self.messages@.len();
        self.messages.push(msg);
        proof {
            // The pushed message is at the last index
            assert(self.messages@[old_len as int]@ == msg@);
        }
    }

    /// Check if the network contains a message
    pub fn contains(&self, msg: &ExecMessage) -> (result: bool)
        ensures
            result == self.spec_contains(msg@)
    {
        let mut i: usize = 0;
        while i < self.messages.len()
            invariant
                0 <= i <= self.messages.len(),
                forall|j: int| #![auto] 0 <= j < i ==> self.messages@[j]@ != msg@,
            decreases
                self.messages.len() - i,
        {
            if self.messages[i].eq(msg) {
                return true;
            }
            i = i + 1;
        }
        false
    }

    /// Check if the network is empty
    pub fn is_empty(&self) -> (result: bool)
        ensures
            result == self.spec_is_empty()
    {
        self.messages.len() == 0
    }

    /// Receive a message (remove and return the first matching message)
    /// Returns None if no matching message exists
    pub fn receive(&mut self, msg: &ExecMessage) -> (result: Option<ExecMessage>)
        ensures
            result.is_some() == old(self).spec_contains(msg@),
            result.is_some() ==> result.unwrap()@ == msg@,
            result.is_some() ==> self.messages@.len() == old(self).messages@.len() - 1,
            result.is_none() ==> self.messages@ == old(self).messages@,
    {
        let mut i: usize = 0;
        while i < self.messages.len()
            invariant
                0 <= i <= self.messages.len(),
                forall|j: int| #![auto] 0 <= j < i ==> self.messages@[j]@ != msg@,
                self.messages@ == old(self).messages@,
            decreases
                self.messages.len() - i,
        {
            if self.messages[i].eq(msg) {
                let removed = self.messages.remove(i);
                return Some(removed);
            }
            i = i + 1;
        }
        None
    }

    /// Lose a message (remove one copy from the network)
    /// Returns true if a message was removed, false if not found
    pub fn lose(&mut self, msg: &ExecMessage) -> (result: bool)
        ensures
            result == old(self).spec_contains(msg@),
            result ==> self.messages@.len() == old(self).messages@.len() - 1,
            !result ==> self.messages@ == old(self).messages@,
    {
        self.receive(msg).is_some()
    }

    /// Duplicate a message (add another copy if it exists)
    /// Returns true if the message was duplicated, false if not found
    pub fn duplicate(&mut self, msg: &ExecMessage) -> (result: bool)
        ensures
            result == old(self).spec_contains(msg@),
            result ==> self.spec_contains(msg@),
            result ==> self.messages@.len() == old(self).messages@.len() + 1,
            !result ==> self.messages@ == old(self).messages@,
    {
        if self.contains(msg) {
            let ghost old_len = self.messages@.len();
            self.messages.push(msg.clone());
            proof {
                // The pushed message is at the last index
                assert(self.messages@[old_len as int]@ == msg@);
            }
            true
        } else {
            false
        }
    }

    /// Get the number of messages in the network
    pub fn len(&self) -> (result: usize)
        ensures
            result == self.messages@.len()
    {
        self.messages.len()
    }

    /// Count how many copies of a message are in the network
    pub fn count(&self, msg: &ExecMessage) -> (result: usize)
    {
        let mut count: usize = 0;
        let mut i: usize = 0;
        while i < self.messages.len()
            invariant
                0 <= i <= self.messages.len(),
                count <= i,
            decreases
                self.messages.len() - i,
        {
            if self.messages[i].eq(msg) {
                // count <= i < self.messages.len() <= usize::MAX, so count + 1 won't overflow
                count = count + 1;
            }
            i = i + 1;
        }
        count
    }
}

// ============================================================
// UNIT TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    /// Test: Create empty network
    fn test_new_network() {
        let net = ExecNetwork::new();
        assert(net.is_empty());
        assert(net.len() == 0);
    }

    /// Test: Send and contains
    fn test_send_contains() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        assert(!net.contains(&msg));
        
        net.send(msg.clone());
        
        assert(net.contains(&msg));
        assert(net.len() == 1);
    }

    /// Test: Send multiple messages
    fn test_send_multiple() {
        let mut net = ExecNetwork::new();
        let msg1 = ExecMessage::lock_req(0, 1);
        let msg2 = ExecMessage::lock_req(1, 1);
        
        net.send(msg1.clone());
        net.send(msg2.clone());
        
        assert(net.contains(&msg1));
        assert(net.contains(&msg2));
        assert(net.len() == 2);
    }

    /// Test: Receive removes message
    fn test_receive() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        net.send(msg.clone());
        assert(net.contains(&msg));
        
        let received = net.receive(&msg);
        assert(received.is_some());
        assert(!net.contains(&msg));
        assert(net.is_empty());
    }

    /// Test: Receive non-existent message
    fn test_receive_not_found() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        let received = net.receive(&msg);
        assert(received.is_none());
        assert(net.is_empty());
    }

    /// Test: Lose removes one copy
    fn test_lose() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        net.send(msg.clone());
        net.send(msg.clone());
        assert(net.count(&msg) == 2);
        
        let lost = net.lose(&msg);
        assert(lost);
        assert(net.count(&msg) == 1);
        assert(net.contains(&msg));
    }

    /// Test: Duplicate adds copy
    fn test_duplicate() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        net.send(msg.clone());
        assert(net.count(&msg) == 1);
        
        let dup = net.duplicate(&msg);
        assert(dup);
        assert(net.count(&msg) == 2);
    }

    /// Test: Duplicate non-existent fails
    fn test_duplicate_not_found() {
        let mut net = ExecNetwork::new();
        let msg = ExecMessage::lock_req(0, 1);
        
        let dup = net.duplicate(&msg);
        assert(!dup);
        assert(net.is_empty());
    }

    /// Test: Different message types
    fn test_different_message_types() {
        let mut net = ExecNetwork::new();
        
        let lock_req = ExecMessage::lock_req(0, 1);
        let lock_resp = ExecMessage::lock_resp(0, true, 1);
        let rename_req = ExecMessage::rename_req(0, 1);
        let rename_resp = ExecMessage::rename_resp(0, 1);
        let unlock_req = ExecMessage::unlock_req(0, 1);
        let unlock_resp = ExecMessage::unlock_resp(0, 1);
        
        net.send(lock_req.clone());
        net.send(lock_resp.clone());
        net.send(rename_req.clone());
        net.send(rename_resp.clone());
        net.send(unlock_req.clone());
        net.send(unlock_resp.clone());
        
        assert(net.len() == 6);
        assert(net.contains(&lock_req));
        assert(net.contains(&lock_resp));
        assert(net.contains(&rename_req));
        assert(net.contains(&rename_resp));
        assert(net.contains(&unlock_req));
        assert(net.contains(&unlock_resp));
    }

    /// Test: Message accessors
    fn test_message_accessors() {
        let msg = ExecMessage::lock_req(5, 42);
        assert(msg.get_store() == 5);
        assert(msg.get_txn_id() == 42);
        assert(msg.is_request());
        assert(!msg.is_response());
        
        let resp = ExecMessage::lock_resp(3, true, 10);
        assert(resp.get_store() == 3);
        assert(resp.get_txn_id() == 10);
        assert(!resp.is_request());
        assert(resp.is_response());
        assert(resp.is_lock_success());
        assert(!resp.is_lock_failure());
        
        let fail_resp = ExecMessage::lock_resp(3, false, 10);
        assert(!fail_resp.is_lock_success());
        assert(fail_resp.is_lock_failure());
    }
}

} // verus!
