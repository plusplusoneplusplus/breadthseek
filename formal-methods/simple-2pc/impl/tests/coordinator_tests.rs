// Runtime tests for the executable Coordinator implementation.
// These mirror the verified tests in src/coordinator_v.rs but run under `cargo test`.

use kv_store::{Coordinator, CoordPhase};

#[test]
fn test_new() {
    let coord = Coordinator::new();
    assert_eq!(coord.get_txn_id(), 1);
    assert!(!coord.is_committed());
    assert_eq!(coord.get_phase(), CoordPhase::Idle);
}

#[test]
fn test_start_preparing() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    assert_eq!(coord.get_phase(), CoordPhase::Preparing);
    assert_eq!(coord.get_txn_id(), 1);
}

#[test]
fn test_record_lock_success() {
    let mut coord = Coordinator::new();
    coord.start_preparing();

    coord.record_lock_success(0);
    assert!(coord.has_lock(0));
    assert!(!coord.has_lock(1));

    coord.record_lock_success(1);
    assert!(coord.has_lock(0));
    assert!(coord.has_lock(1));
}

#[test]
fn test_handle_lock_failure() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.record_lock_success(0);

    coord.handle_lock_failure();
    assert_eq!(coord.get_phase(), CoordPhase::Cleanup);
    assert!(!coord.has_lock(0)); // Locks cleared
}

#[test]
fn test_decide_commit() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.record_lock_success(0);
    coord.record_lock_success(1);

    coord.decide_commit();
    assert!(coord.is_committed());
    assert_eq!(coord.get_phase(), CoordPhase::Committed);
}

#[test]
fn test_record_rename_done() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.decide_commit();

    let all_done = coord.record_rename_done(0, 2);
    assert!(!all_done);
    assert!(coord.has_renamed(0));
    assert_eq!(coord.get_phase(), CoordPhase::Committed);

    let all_done = coord.record_rename_done(1, 2);
    assert!(all_done);
    assert!(coord.has_renamed(1));
    assert_eq!(coord.get_phase(), CoordPhase::Cleanup);
}

#[test]
fn test_record_unlock_acked() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.decide_commit();
    coord.record_rename_done(0, 2);
    coord.record_rename_done(1, 2);

    let all_done = coord.record_unlock_acked(0, 2);
    assert!(!all_done);
    assert!(coord.has_unlocked(0));
    assert_eq!(coord.get_phase(), CoordPhase::Cleanup);

    let all_done = coord.record_unlock_acked(1, 2);
    assert!(all_done);
    assert!(coord.has_unlocked(1));
    assert_eq!(coord.get_phase(), CoordPhase::Done);
}

#[test]
fn test_crash_recover_committed() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.decide_commit();
    coord.record_rename_done(0, 2);

    // Crash
    coord.crash();
    assert_eq!(coord.get_phase(), CoordPhase::Crashed);
    assert!(coord.is_committed()); // Durable state preserved
    assert_eq!(coord.get_txn_id(), 1); // Txn ID preserved

    // Recover
    coord.recover();
    assert_eq!(coord.get_txn_id(), 2); // Txn ID incremented
    assert!(coord.is_committed()); // WAL preserved
    assert_eq!(coord.get_phase(), CoordPhase::Committed); // Resume commit
    assert!(!coord.has_renamed(0)); // Volatile state cleared
}

#[test]
fn test_crash_recover_not_committed() {
    let mut coord = Coordinator::new();
    coord.start_preparing();
    coord.record_lock_success(0);

    // Crash before commit
    coord.crash();
    assert_eq!(coord.get_phase(), CoordPhase::Crashed);
    assert!(!coord.is_committed());

    // Recover
    coord.recover();
    assert_eq!(coord.get_txn_id(), 2);
    assert!(!coord.is_committed());
    assert_eq!(coord.get_phase(), CoordPhase::Cleanup); // Go to cleanup
}

#[test]
fn test_phase_can_crash() {
    assert!(!CoordPhase::Idle.can_crash());
    assert!(CoordPhase::Preparing.can_crash());
    assert!(CoordPhase::Committed.can_crash());
    assert!(CoordPhase::Cleanup.can_crash());
    assert!(!CoordPhase::Done.can_crash());
    assert!(!CoordPhase::Crashed.can_crash());
}

#[test]
fn test_phase_is_terminal() {
    assert!(!CoordPhase::Idle.is_terminal());
    assert!(!CoordPhase::Preparing.is_terminal());
    assert!(!CoordPhase::Committed.is_terminal());
    assert!(!CoordPhase::Cleanup.is_terminal());
    assert!(CoordPhase::Done.is_terminal());
    assert!(!CoordPhase::Crashed.is_terminal());
}

#[test]
fn test_phase_is_active() {
    assert!(CoordPhase::Idle.is_active());
    assert!(CoordPhase::Preparing.is_active());
    assert!(CoordPhase::Committed.is_active());
    assert!(CoordPhase::Cleanup.is_active());
    assert!(!CoordPhase::Done.is_active());
    assert!(!CoordPhase::Crashed.is_active());
}

