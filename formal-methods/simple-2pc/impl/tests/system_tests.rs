// Runtime tests for the executable ExecSystem implementation.
// These mirror the verified tests in src/system_v.rs but run under `cargo test`.

use kv_store::{CoordPhase, ExecMessage, ExecSystem};

#[test]
fn test_new_system() {
    let sys = ExecSystem::new(2, "A", "A'", 100);

    assert_eq!(sys.num_stores(), 2);
    assert_eq!(sys.get_coord_phase(), CoordPhase::Idle);
    assert!(sys.net_is_empty());
    assert!(sys.store_has_key_a(0));
    assert!(sys.store_has_key_a(1));
    assert!(!sys.store_has_key_aprime(0));
    assert!(!sys.store_has_key_aprime(1));
}

#[test]
fn test_happy_path() {
    let mut sys = ExecSystem::new(2, "A", "A'", 42);
    let txn_id = sys.get_txn_id();

    // Phase 1: Send lock requests
    sys.coord_send_lock_req(0);
    sys.coord_send_lock_req(1);
    assert_eq!(sys.get_coord_phase(), CoordPhase::Preparing);

    // Stores handle lock requests
    assert!(sys.store_handle_lock_req(0, txn_id));
    assert!(sys.store_handle_lock_req(1, txn_id));

    // Coordinator receives lock responses
    assert!(sys.coord_recv_lock_resp_success(0));
    assert!(sys.coord_recv_lock_resp_success(1));

    // Coordinator decides to commit
    sys.coord_decide_commit();
    assert_eq!(sys.get_coord_phase(), CoordPhase::Committed);
    assert!(sys.is_committed());

    // Phase 2: Send rename requests
    sys.coord_send_rename_req(0);
    sys.coord_send_rename_req(1);

    // Stores handle rename requests
    assert!(sys.store_handle_rename_req(0, txn_id));
    assert!(sys.store_handle_rename_req(1, txn_id));

    // Verify rename happened
    assert!(!sys.store_has_key_a(0));
    assert!(sys.store_has_key_aprime(0));
    assert!(!sys.store_has_key_a(1));
    assert!(sys.store_has_key_aprime(1));

    // Coordinator receives rename responses
    assert!(sys.coord_recv_rename_resp(0));
    assert!(sys.coord_recv_rename_resp(1));
    assert_eq!(sys.get_coord_phase(), CoordPhase::Cleanup);

    // Phase 3: Send unlock requests
    sys.coord_send_unlock_req(0);
    sys.coord_send_unlock_req(1);

    // Stores handle unlock requests
    assert!(sys.store_handle_unlock_req(0, txn_id));
    assert!(sys.store_handle_unlock_req(1, txn_id));

    // Coordinator receives unlock responses
    assert!(sys.coord_recv_unlock_resp(0));
    assert!(sys.coord_recv_unlock_resp(1));

    // Protocol complete
    assert_eq!(sys.get_coord_phase(), CoordPhase::Done);
}

#[test]
fn test_lock_failure() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);
    let txn_id = sys.get_txn_id();

    // Manually put key_aprime to simulate already renamed
    sys.store_put(0, "A'", 99);

    // Send lock request
    sys.coord_send_lock_req(0);

    // Store handles lock request - should fail because A' exists
    assert!(sys.store_handle_lock_req(0, txn_id));

    // Coordinator receives lock failure
    assert!(sys.coord_recv_lock_resp_failure(0));
    assert_eq!(sys.get_coord_phase(), CoordPhase::Cleanup);
}

#[test]
fn test_crash_recovery_committed() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);

    // Get to committed state
    sys.coord_send_lock_req(0);
    let txn_id = sys.get_txn_id();
    sys.store_handle_lock_req(0, txn_id);
    sys.coord_recv_lock_resp_success(0);
    sys.coord_decide_commit();

    assert!(sys.is_committed());
    assert_eq!(sys.get_coord_phase(), CoordPhase::Committed);

    // Crash
    sys.coord_crash();
    assert_eq!(sys.get_coord_phase(), CoordPhase::Crashed);
    assert!(sys.is_committed()); // Durable state preserved

    // Recover
    sys.coord_recover();
    assert_eq!(sys.get_txn_id(), txn_id + 1);
    assert_eq!(sys.get_coord_phase(), CoordPhase::Committed); // Resume commit
}

#[test]
fn test_crash_recovery_not_committed() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);

    // Start preparing but don't commit
    sys.coord_send_lock_req(0);
    let txn_id = sys.get_txn_id();

    assert!(!sys.is_committed());
    assert_eq!(sys.get_coord_phase(), CoordPhase::Preparing);

    // Crash
    sys.coord_crash();
    assert_eq!(sys.get_coord_phase(), CoordPhase::Crashed);

    // Recover
    sys.coord_recover();
    assert_eq!(sys.get_txn_id(), txn_id + 1);
    assert_eq!(sys.get_coord_phase(), CoordPhase::Cleanup); // Go to cleanup
}

#[test]
fn test_network_duplication() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);

    // Send lock request
    sys.coord_send_lock_req(0);
    let txn_id = sys.get_txn_id();

    // Duplicate the message
    let msg = ExecMessage::lock_req(0, txn_id);
    assert!(sys.net_duplicate(&msg));

    // Both copies can be processed
    assert!(sys.store_handle_lock_req(0, txn_id));
    assert!(sys.store_handle_lock_req(0, txn_id)); // Second copy

    // Two responses should be in the network
    let resp = ExecMessage::lock_resp(0, true, txn_id);
    assert_eq!(sys.net.count(&resp), 2);
}

#[test]
fn test_stale_message_rejection() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);

    // First transaction
    sys.coord_send_lock_req(0);
    let old_txn_id = sys.get_txn_id();
    sys.store_handle_lock_req(0, old_txn_id);

    // Crash and recover (increments txn_id)
    sys.coord_crash();
    sys.coord_recover();
    let new_txn_id = sys.get_txn_id();
    assert!(new_txn_id > old_txn_id);

    // Update store's txn_id with a new message
    sys.store_update_txn_id(0, new_txn_id);

    // Old message should be stale
    assert!(sys.store_is_stale_txn_id(0, old_txn_id));
}

#[test]
fn test_single_store_full_protocol() {
    let mut sys = ExecSystem::new(1, "A", "A'", 123);
    let txn_id = sys.get_txn_id();

    // Verify initial state
    assert_eq!(sys.store_get_key_a(0), Some(123));
    assert_eq!(sys.store_get_key_aprime(0), None);

    // Phase 1: Lock
    sys.coord_send_lock_req(0);
    sys.store_handle_lock_req(0, txn_id);
    sys.coord_recv_lock_resp_success(0);

    // Commit
    sys.coord_decide_commit();

    // Phase 2: Rename
    sys.coord_send_rename_req(0);
    sys.store_handle_rename_req(0, txn_id);
    sys.coord_recv_rename_resp(0);

    // Verify rename happened
    assert_eq!(sys.store_get_key_a(0), None);
    assert_eq!(sys.store_get_key_aprime(0), Some(123));

    // Phase 3: Unlock
    sys.coord_send_unlock_req(0);
    sys.store_handle_unlock_req(0, txn_id);
    sys.coord_recv_unlock_resp(0);

    // Protocol complete
    assert_eq!(sys.get_coord_phase(), CoordPhase::Done);
}

#[test]
fn test_net_lose() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);

    sys.coord_send_lock_req(0);
    let txn_id = sys.get_txn_id();

    let msg = ExecMessage::lock_req(0, txn_id);
    assert!(sys.net.contains(&msg));

    // Lose the message
    assert!(sys.net_lose(&msg));
    assert!(!sys.net.contains(&msg));

    // Trying to lose again should fail
    assert!(!sys.net_lose(&msg));
}

#[test]
fn test_message_not_found() {
    let mut sys = ExecSystem::new(1, "A", "A'", 42);
    let txn_id = sys.get_txn_id();

    // Try to handle a message that doesn't exist
    assert!(!sys.store_handle_lock_req(0, txn_id));
    assert!(!sys.store_handle_rename_req(0, txn_id));
    assert!(!sys.store_handle_unlock_req(0, txn_id));
}

