// Runtime tests for the executable ExecNetwork and ExecMessage implementation.
// These mirror the verified tests in src/network_v.rs but run under `cargo test`.

use kv_store::{ExecMessage, ExecNetwork};

#[test]
fn test_new_network() {
    let net = ExecNetwork::new();
    assert!(net.is_empty());
    assert_eq!(net.len(), 0);
}

#[test]
fn test_send_contains() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    assert!(!net.contains(&msg));

    net.send(msg.clone());

    assert!(net.contains(&msg));
    assert_eq!(net.len(), 1);
}

#[test]
fn test_send_multiple() {
    let mut net = ExecNetwork::new();
    let msg1 = ExecMessage::lock_req(0, 1);
    let msg2 = ExecMessage::lock_req(1, 1);

    net.send(msg1.clone());
    net.send(msg2.clone());

    assert!(net.contains(&msg1));
    assert!(net.contains(&msg2));
    assert_eq!(net.len(), 2);
}

#[test]
fn test_receive() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    net.send(msg.clone());
    assert!(net.contains(&msg));

    let received = net.receive(&msg);
    assert!(received.is_some());
    assert!(!net.contains(&msg));
    assert!(net.is_empty());
}

#[test]
fn test_receive_not_found() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    let received = net.receive(&msg);
    assert!(received.is_none());
    assert!(net.is_empty());
}

#[test]
fn test_lose() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    net.send(msg.clone());
    net.send(msg.clone());
    assert_eq!(net.count(&msg), 2);

    let lost = net.lose(&msg);
    assert!(lost);
    assert_eq!(net.count(&msg), 1);
    assert!(net.contains(&msg));
}

#[test]
fn test_duplicate() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    net.send(msg.clone());
    assert_eq!(net.count(&msg), 1);

    let dup = net.duplicate(&msg);
    assert!(dup);
    assert_eq!(net.count(&msg), 2);
}

#[test]
fn test_duplicate_not_found() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(0, 1);

    let dup = net.duplicate(&msg);
    assert!(!dup);
    assert!(net.is_empty());
}

#[test]
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

    assert_eq!(net.len(), 6);
    assert!(net.contains(&lock_req));
    assert!(net.contains(&lock_resp));
    assert!(net.contains(&rename_req));
    assert!(net.contains(&rename_resp));
    assert!(net.contains(&unlock_req));
    assert!(net.contains(&unlock_resp));
}

#[test]
fn test_message_accessors() {
    let msg = ExecMessage::lock_req(5, 42);
    assert_eq!(msg.get_store(), 5);
    assert_eq!(msg.get_txn_id(), 42);
    assert!(msg.is_request());
    assert!(!msg.is_response());

    let resp = ExecMessage::lock_resp(3, true, 10);
    assert_eq!(resp.get_store(), 3);
    assert_eq!(resp.get_txn_id(), 10);
    assert!(!resp.is_request());
    assert!(resp.is_response());
    assert!(resp.is_lock_success());
    assert!(!resp.is_lock_failure());

    let fail_resp = ExecMessage::lock_resp(3, false, 10);
    assert!(!fail_resp.is_lock_success());
    assert!(fail_resp.is_lock_failure());
}

#[test]
fn test_message_equality() {
    let msg1 = ExecMessage::lock_req(0, 1);
    let msg2 = ExecMessage::lock_req(0, 1);
    let msg3 = ExecMessage::lock_req(0, 2);
    let msg4 = ExecMessage::lock_req(1, 1);

    assert!(msg1.eq(&msg2));
    assert!(!msg1.eq(&msg3));
    assert!(!msg1.eq(&msg4));
}

#[test]
fn test_message_clone() {
    let msg = ExecMessage::lock_resp(5, true, 42);
    let cloned = msg.clone();

    assert!(msg.eq(&cloned));
    assert_eq!(msg.get_store(), cloned.get_store());
    assert_eq!(msg.get_txn_id(), cloned.get_txn_id());
}

#[test]
fn test_duplication_then_loss() {
    let mut net = ExecNetwork::new();
    let msg = ExecMessage::lock_req(1, 1);

    // Send message
    net.send(msg.clone());
    assert_eq!(net.count(&msg), 1);

    // Network duplicates it
    net.duplicate(&msg);
    assert_eq!(net.count(&msg), 2);

    // One copy is lost
    net.lose(&msg);
    assert_eq!(net.count(&msg), 1);

    // Message still available
    assert!(net.contains(&msg));
}

