// system_s.rs - System/driver specification layer
//
// Composes:
// - CoordinatorSpec (protocol state machine)
// - KvStoreSpec (per-store key/value + locks + txn id tracking)
// - NetworkSpec (multiset of in-flight messages, with loss/duplication)
//
// This is the missing glue that wires the coordinator and stores together via the network:
// coordinator "send" actions create messages in the network; store/coordinator "deliver"
// actions consume one copy and may enqueue responses.

use vstd::prelude::*;

use crate::coordinator_s::*;
use crate::kv_store_s::*;
use crate::network_s::*;

verus! {

/// Spec-level global system state (ghost/proof only).
pub ghost struct SystemSpec {
    pub coord: CoordinatorSpec,
    pub net: NetworkSpec,
    pub stores: Map<StoreId, KvStoreSpec<u64>>,
    pub all_stores: Set<StoreId>,
}

impl SystemSpec {
    // ============================================================
    // Observations / basic helpers
    // ============================================================

    pub open spec fn type_ok(&self) -> bool {
        &&& self.all_stores == self.stores.dom()
        &&& self.coord.current_txn_id >= 1
    }

    pub open spec fn store(&self, s: StoreId) -> KvStoreSpec<u64>
        recommends self.stores.contains_key(s)
    {
        self.stores[s]
    }

    pub open spec fn with_store(self, s: StoreId, new_store: KvStoreSpec<u64>) -> Self
        recommends self.stores.contains_key(s)
    {
        SystemSpec { stores: self.stores.insert(s, new_store), ..self }
    }

    pub open spec fn with_coord(self, new_coord: CoordinatorSpec) -> Self {
        SystemSpec { coord: new_coord, ..self }
    }

    pub open spec fn with_net(self, new_net: NetworkSpec) -> Self {
        SystemSpec { net: new_net, ..self }
    }

    // ============================================================
    // Coordinator -> Network (send) actions
    // ============================================================

    pub open spec fn coord_send_lock_req(self, s: StoreId) -> Self
        recommends self.all_stores.contains(s)
    {
        let (new_coord, msg) = self.coord.send_lock_req(s);
        SystemSpec { coord: new_coord, net: self.net.send(msg), ..self }
    }

    pub open spec fn coord_decide_commit(self) -> Self
        recommends self.coord.phase == CoordPhase::Preparing
    {
        self.with_coord(self.coord.decide_commit())
    }

    pub open spec fn coord_send_rename_req(self, s: StoreId) -> Self
        recommends self.all_stores.contains(s)
    {
        let (new_coord, msg) = self.coord.send_rename_req(s);
        SystemSpec { coord: new_coord, net: self.net.send(msg), ..self }
    }

    pub open spec fn coord_send_unlock_req(self, s: StoreId) -> Self
        recommends self.all_stores.contains(s)
    {
        let (new_coord, msg) = self.coord.send_unlock_req(s);
        SystemSpec { coord: new_coord, net: self.net.send(msg), ..self }
    }

    // ============================================================
    // Network -> Coordinator (deliver/receive) actions
    // ============================================================

    pub open spec fn coord_recv_lock_resp_success(self, s: StoreId) -> Self
        recommends
            self.coord.phase == CoordPhase::Preparing,
            self.net.contains(lock_resp_msg(s, true, self.coord.current_txn_id)),
            !self.coord.locks_acquired.contains(s),
    {
        let msg = lock_resp_msg(s, true, self.coord.current_txn_id);
        let new_net = self.net.lose(msg);
        let new_coord = self.coord.recv_lock_resp_success(s);
        SystemSpec { coord: new_coord, net: new_net, ..self }
    }

    pub open spec fn coord_recv_lock_resp_failure(self, s: StoreId) -> Self
        recommends
            self.coord.phase == CoordPhase::Preparing,
            self.net.contains(lock_resp_msg(s, false, self.coord.current_txn_id)),
    {
        let msg = lock_resp_msg(s, false, self.coord.current_txn_id);
        let new_net = self.net.lose(msg);
        let new_coord = self.coord.recv_lock_resp_failure();
        SystemSpec { coord: new_coord, net: new_net, ..self }
    }

    pub open spec fn coord_recv_rename_resp(self, s: StoreId) -> Self
        recommends
            self.coord.phase == CoordPhase::Committed,
            self.net.contains(rename_resp_msg(s, self.coord.current_txn_id)),
            self.all_stores.contains(s),
            !self.coord.renames_done.contains(s),
    {
        let msg = rename_resp_msg(s, self.coord.current_txn_id);
        let new_net = self.net.lose(msg);
        let new_coord = self.coord.recv_rename_resp(s, self.all_stores);
        SystemSpec { coord: new_coord, net: new_net, ..self }
    }

    pub open spec fn coord_recv_unlock_resp(self, s: StoreId) -> Self
        recommends
            self.coord.phase == CoordPhase::Cleanup,
            self.net.contains(unlock_resp_msg(s, self.coord.current_txn_id)),
            self.all_stores.contains(s),
            !self.coord.unlocks_acked.contains(s),
    {
        let msg = unlock_resp_msg(s, self.coord.current_txn_id);
        let new_net = self.net.lose(msg);
        let new_coord = self.coord.recv_unlock_resp(s, self.all_stores);
        SystemSpec { coord: new_coord, net: new_net, ..self }
    }

    // ============================================================
    // Coordinator crash/recovery (local state transition)
    // ============================================================

    pub open spec fn coord_crash(self) -> Self
        recommends self.coord.phase.spec_can_crash()
    {
        self.with_coord(self.coord.crash())
    }

    pub open spec fn coord_recover(self) -> Self
        recommends self.coord.phase == CoordPhase::Crashed
    {
        self.with_coord(self.coord.recover())
    }

    // ============================================================
    // Network -> Store (deliver/handle) actions
    // ============================================================

    /// Handle one `LockReq` message for store `s` and txn `txn_id`.
    ///
    /// - Consumes exactly one copy of the request from the network.
    /// - Rejects stale txn ids (no state change; no response).
    /// - Otherwise updates `last_seen_txn_id`, locks both keys, and sends `LockResp`.
    /// - Fails if `key_aprime` already exists (interpreted as already renamed).
    pub open spec fn store_handle_lock_req(
        self,
        s: StoreId,
        txn_id: TxnId,
        key_a: Seq<char>,
        key_aprime: Seq<char>,
    ) -> Self
        recommends
            self.all_stores.contains(s),
            self.net.contains(lock_req_msg(s, txn_id)),
            self.stores.contains_key(s),
            key_a != key_aprime,
    {
        let req = lock_req_msg(s, txn_id);
        let net1 = self.net.lose(req);
        let st0 = self.store(s);

        if st0.is_stale_txn_id(txn_id) {
            SystemSpec { net: net1, ..self }
        } else {
            let st1 = st0.update_txn_id(txn_id);
            if st1.contains_key(key_aprime) {
                let net2 = net1.send(lock_resp_msg(s, false, txn_id));
                SystemSpec { net: net2, stores: self.stores.insert(s, st1), ..self }
            } else {
                let st2 = st1.lock(key_a).lock(key_aprime);
                let net2 = net1.send(lock_resp_msg(s, true, txn_id));
                SystemSpec { net: net2, stores: self.stores.insert(s, st2), ..self }
            }
        }
    }

    /// Handle one `RenameReq` message for store `s` and txn `txn_id`.
    ///
    /// - Consumes exactly one copy of the request from the network.
    /// - Rejects stale txn ids (no state change; no response).
    /// - If already renamed (has `key_aprime`), responds success (idempotent).
    /// - If both keys are locked and `key_a` exists, performs rename and responds success.
    pub open spec fn store_handle_rename_req(
        self,
        s: StoreId,
        txn_id: TxnId,
        key_a: Seq<char>,
        key_aprime: Seq<char>,
    ) -> Self
        recommends
            self.all_stores.contains(s),
            self.net.contains(rename_req_msg(s, txn_id)),
            self.stores.contains_key(s),
            key_a != key_aprime,
    {
        let req = rename_req_msg(s, txn_id);
        let net1 = self.net.lose(req);
        let st0 = self.store(s);

        if st0.is_stale_txn_id(txn_id) {
            SystemSpec { net: net1, ..self }
        } else {
            let st1 = st0.update_txn_id(txn_id);
            if st1.contains_key(key_aprime) {
                let net2 = net1.send(rename_resp_msg(s, txn_id));
                SystemSpec { net: net2, stores: self.stores.insert(s, st1), ..self }
            } else if st1.is_locked(key_a) && st1.is_locked(key_aprime) && st1.contains_key(key_a) {
                let st2 = st1.rename(key_a, key_aprime);
                let net2 = net1.send(rename_resp_msg(s, txn_id));
                SystemSpec { net: net2, stores: self.stores.insert(s, st2), ..self }
            } else {
                SystemSpec { net: net1, stores: self.stores.insert(s, st1), ..self }
            }
        }
    }

    /// Handle one `UnlockReq` message for store `s` and txn `txn_id`.
    ///
    /// - Consumes exactly one copy of the request from the network.
    /// - Rejects stale txn ids (no state change; no response).
    /// - Otherwise updates `last_seen_txn_id`, unlocks both keys, and sends `UnlockResp`.
    pub open spec fn store_handle_unlock_req(
        self,
        s: StoreId,
        txn_id: TxnId,
        key_a: Seq<char>,
        key_aprime: Seq<char>,
    ) -> Self
        recommends
            self.all_stores.contains(s),
            self.net.contains(unlock_req_msg(s, txn_id)),
            self.stores.contains_key(s),
            key_a != key_aprime,
    {
        let req = unlock_req_msg(s, txn_id);
        let net1 = self.net.lose(req);
        let st0 = self.store(s);

        if st0.is_stale_txn_id(txn_id) {
            SystemSpec { net: net1, ..self }
        } else {
            let st1 = st0.update_txn_id(txn_id);
            let st2 = st1.unlock(key_a).unlock(key_aprime);
            let net2 = net1.send(unlock_resp_msg(s, txn_id));
            SystemSpec { net: net2, stores: self.stores.insert(s, st2), ..self }
        }
    }

    // ============================================================
    // Environment (network-only) actions
    // ============================================================

    pub open spec fn net_lose(self, msg: Message) -> Self
        recommends self.net.contains(msg)
    {
        self.with_net(self.net.lose(msg))
    }

    pub open spec fn net_duplicate(self, msg: Message) -> Self
        recommends self.net.contains(msg)
    {
        self.with_net(self.net.duplicate(msg))
    }
}

// ============================================================
// TESTS
// ============================================================

#[cfg(test)]
mod tests {
    use super::*;

    spec fn key_a() -> Seq<char> { "A"@ }
    spec fn key_aprime() -> Seq<char> { "A'"@ }

    spec fn mk_one_store_system() -> SystemSpec {
        let s0: StoreId = 0;
        let all = Set::empty().insert(s0);
        let st0 = KvStoreSpec::empty().put(key_a(), 10u64);
        let stores = Map::empty().insert(s0, st0);
        SystemSpec {
            coord: CoordinatorSpec::init(),
            net: NetworkSpec::empty(),
            stores,
            all_stores: all,
        }
    }

    spec fn mk_two_store_system() -> SystemSpec {
        let s0: StoreId = 0;
        let s1: StoreId = 1;
        let all = Set::empty().insert(s0).insert(s1);
        let st0 = KvStoreSpec::empty().put(key_a(), 10u64);
        let st1 = KvStoreSpec::empty().put(key_a(), 20u64);
        let stores = Map::empty().insert(s0, st0).insert(s1, st1);
        SystemSpec {
            coord: CoordinatorSpec::init(),
            net: NetworkSpec::empty(),
            stores,
            all_stores: all,
        }
    }

    /// End-to-end happy path:
    /// - coordinator sends LockReq
    /// - stores lock and respond
    /// - coordinator commits and sends RenameReq
    /// - stores rename and respond
    /// - coordinator sends UnlockReq
    /// - stores unlock and respond
    /// - coordinator reaches Done
    proof fn test_success_path_two_stores() {
        let s0: StoreId = 0;
        let s1: StoreId = 1;
        let txn: TxnId = 1;

        let sys0 = mk_two_store_system();

        let sys1 = sys0
            .coord_send_lock_req(s0)
            .coord_send_lock_req(s1);

        assert(sys1.coord.phase == CoordPhase::Preparing);
        assert(sys1.net.contains(lock_req_msg(s0, txn)));
        assert(sys1.net.contains(lock_req_msg(s1, txn)));

        let sys2 = sys1
            .store_handle_lock_req(s0, txn, key_a(), key_aprime())
            .store_handle_lock_req(s1, txn, key_a(), key_aprime());

        assert(sys2.net.contains(lock_resp_msg(s0, true, txn)));
        assert(sys2.net.contains(lock_resp_msg(s1, true, txn)));
        assert(sys2.store(s0).is_locked(key_a()));
        assert(sys2.store(s0).is_locked(key_aprime()));

        let sys3 = sys2
            .coord_recv_lock_resp_success(s0)
            .coord_recv_lock_resp_success(s1);

        assert(sys3.coord.locks_acquired == sys3.all_stores);

        let sys4 = sys3.coord_decide_commit();
        assert(sys4.coord.phase == CoordPhase::Committed);
        assert(sys4.coord.wal_committed);

        let sys5 = sys4
            .coord_send_rename_req(s0)
            .coord_send_rename_req(s1);

        assert(sys5.net.contains(rename_req_msg(s0, txn)));
        assert(sys5.net.contains(rename_req_msg(s1, txn)));

        let sys6 = sys5
            .store_handle_rename_req(s0, txn, key_a(), key_aprime())
            .store_handle_rename_req(s1, txn, key_a(), key_aprime());

        assert(sys6.net.contains(rename_resp_msg(s0, txn)));
        assert(sys6.net.contains(rename_resp_msg(s1, txn)));

        let sys7 = sys6
            .coord_recv_rename_resp(s0)
            .coord_recv_rename_resp(s1);

        assert(sys7.coord.phase == CoordPhase::Cleanup);
        assert(sys7.store(s0).contains_key(key_aprime()));
        assert(!sys7.store(s0).contains_key(key_a()));

        let sys8 = sys7
            .coord_send_unlock_req(s0)
            .coord_send_unlock_req(s1);

        assert(sys8.net.contains(unlock_req_msg(s0, txn)));
        assert(sys8.net.contains(unlock_req_msg(s1, txn)));

        let sys9 = sys8
            .store_handle_unlock_req(s0, txn, key_a(), key_aprime())
            .store_handle_unlock_req(s1, txn, key_a(), key_aprime());

        assert(sys9.net.contains(unlock_resp_msg(s0, txn)));
        assert(sys9.net.contains(unlock_resp_msg(s1, txn)));

        let sys10 = sys9
            .coord_recv_unlock_resp(s0)
            .coord_recv_unlock_resp(s1);

        assert(sys10.coord.phase == CoordPhase::Done);
        assert(!sys10.store(s0).is_locked(key_a()));
        assert(!sys10.store(s0).is_locked(key_aprime()));
    }

    /// Network duplication at the request layer:
    /// duplicating a `LockReq` results in multiple `LockResp` messages.
    proof fn test_duplicate_lock_req_produces_two_resps() {
        let s0: StoreId = 0;
        let txn: TxnId = 1;

        let sys0 = mk_one_store_system();
        let sys1 = sys0.coord_send_lock_req(s0);

        let req = lock_req_msg(s0, txn);
        assert(sys1.net.contains(req));

        let sys2 = sys1.net_duplicate(req);
        let sys3 = sys2.store_handle_lock_req(s0, txn, key_a(), key_aprime());
        assert(sys3.net.contains(req)); // one duplicate copy remains

        let sys4 = sys3.store_handle_lock_req(s0, txn, key_a(), key_aprime());
        let resp = lock_resp_msg(s0, true, txn);

        assert(sys4.net.count(resp) == 2);
    }

    /// Stale transaction IDs are rejected by stores: no response is generated.
    proof fn test_store_rejects_stale_txn_id() {
        let s0: StoreId = 0;
        let old_txn: TxnId = 4;
        let last_seen: TxnId = 5;

        let st0 = KvStoreSpec::empty()
            .put(key_a(), 10u64)
            .update_txn_id(last_seen);

        let stores = Map::empty().insert(s0, st0);
        let all = Set::empty().insert(s0);
        let net = NetworkSpec::empty().send(lock_req_msg(s0, old_txn));

        let sys0 = SystemSpec {
            coord: CoordinatorSpec::init(),
            net,
            stores,
            all_stores: all,
        };

        let sys1 = sys0.store_handle_lock_req(s0, old_txn, key_a(), key_aprime());

        assert(sys1.net.is_empty());
        assert(sys1.store(s0).get_last_seen_txn_id() == last_seen);
        assert(!sys1.store(s0).is_locked(key_a()));
        assert(!sys1.store(s0).is_locked(key_aprime()));
    }
}

} // verus!
