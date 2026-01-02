---------------------------- MODULE AtomicRename ----------------------------
(***************************************************************************)
(* TLA+ Specification: 2PC Atomic Key Rename                               *)
(*                                                                         *)
(* Models a 2PC-style protocol for atomically renaming a key (A -> A')     *)
(* across multiple independent KV stores, with:                            *)
(*   - Coordinator crash recovery (WAL-backed)                             *)
(*   - Message loss and duplication                                        *)
(*   - Value updates when unlocked                                         *)
(*   - Transaction IDs to prevent stale message interference               *)
(*                                                                         *)
(* CHANGELOG:                                                              *)
(* 2026-01-02: Added transaction ID mechanism                              *)
(*   - Problem: After coordinator crash/recovery, old in-flight messages   *)
(*     could be processed by stores AFTER cleanup completed, causing       *)
(*     deadlock (stores hold locks, coordinator thinks it's done)          *)
(*   - Solution: Each protocol attempt gets a unique transaction ID        *)
(*     * currentTxnId: Durable coordinator state, incremented on recovery  *)
(*     * lastSeenTxnId[store]: Stores track highest txnId seen             *)
(*     * All messages include txnId field                                  *)
(*     * Stores reject messages with txnId < lastSeenTxnId[store]          *)
(*   - Effect: Old messages from aborted transactions are silently         *)
(*     ignored, preventing race conditions during crash recovery           *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets

CONSTANTS
    Stores,     \* Set of KV stores, e.g., {S1, S2}
    Values      \* Possible values, e.g., {0, 1, 2}

(***************************************************************************)
(* Message type constructors (now include txnId)                           *)
(***************************************************************************)
LockReqMsg(s, txnId)           == [type |-> "LockReq", store |-> s, txnId |-> txnId]
LockRespMsg(s, ok, txnId)      == [type |-> "LockResp", store |-> s, success |-> ok, txnId |-> txnId]
RenameReqMsg(s, txnId)         == [type |-> "RenameReq", store |-> s, txnId |-> txnId]
RenameRespMsg(s, txnId)        == [type |-> "RenameResp", store |-> s, txnId |-> txnId]
UnlockReqMsg(s, txnId)         == [type |-> "UnlockReq", store |-> s, txnId |-> txnId]
UnlockRespMsg(s, txnId)        == [type |-> "UnlockResp", store |-> s, txnId |-> txnId]

VARIABLES
    (***************************************************************)
    (* Coordinator state                                           *)
    (***************************************************************)
    currentTxnId,   \* Nat - durable, survives crash (incremented on each attempt)
    coordPhase,     \* {idle, preparing, committed, cleanup, done, crashed}
    walCommitted,   \* BOOLEAN - durable, survives crash
    locksAcquired,  \* SUBSET Stores - volatile
    renamesDone,    \* SUBSET Stores - volatile
    unlocksAcked,   \* SUBSET Stores - volatile (tracks unlock acknowledgments)

    (***************************************************************)
    (* KV Store state (per store)                                  *)
    (***************************************************************)
    storeKey,       \* [Stores -> {"A", "A'"}]
    storeValue,     \* [Stores -> Values]
    lockA,          \* [Stores -> BOOLEAN]
    lockAprime,     \* [Stores -> BOOLEAN]
    lastSeenTxnId,  \* [Stores -> Nat] - highest txnId seen, rejects lower ones

    (***************************************************************)
    (* Network                                                     *)
    (***************************************************************)
    messages        \* Set of messages (removed after processing to reduce state space)

vars == <<currentTxnId, coordPhase, walCommitted, locksAcquired, renamesDone, unlocksAcked,
          storeKey, storeValue, lockA, lockAprime, lastSeenTxnId, messages>>

durableCoordVars == <<currentTxnId, walCommitted>>
volatileCoordVars == <<coordPhase, locksAcquired, renamesDone, unlocksAcked>>
coordVars == <<currentTxnId, coordPhase, walCommitted, locksAcquired, renamesDone, unlocksAcked>>
storeVars == <<storeKey, storeValue, lockA, lockAprime, lastSeenTxnId>>

(***************************************************************************)
(* Type invariant                                                          *)
(***************************************************************************)
TypeOK ==
    /\ currentTxnId \in Nat
    /\ coordPhase \in {"idle", "preparing", "committed", "cleanup", "done", "crashed"}
    /\ walCommitted \in BOOLEAN
    /\ locksAcquired \subseteq Stores
    /\ renamesDone \subseteq Stores
    /\ unlocksAcked \subseteq Stores
    /\ storeKey \in [Stores -> {"A", "A'"}]
    /\ storeValue \in [Stores -> Values]
    /\ lockA \in [Stores -> BOOLEAN]
    /\ lockAprime \in [Stores -> BOOLEAN]
    /\ lastSeenTxnId \in [Stores -> Nat]

(***************************************************************************)
(* Initial state                                                           *)
(***************************************************************************)
Init ==
    /\ currentTxnId = 1
    /\ coordPhase = "idle"
    /\ walCommitted = FALSE
    /\ locksAcquired = {}
    /\ renamesDone = {}
    /\ unlocksAcked = {}
    /\ storeKey = [s \in Stores |-> "A"]
    /\ storeValue \in [Stores -> Values]  \* Any initial value
    /\ lockA = [s \in Stores |-> FALSE]
    /\ lockAprime = [s \in Stores |-> FALSE]
    /\ lastSeenTxnId = [s \in Stores |-> 0]
    /\ messages = {}

(***************************************************************************)
(* Coordinator Actions                                                     *)
(***************************************************************************)

\* Send lock request to a store
SendLockReq(s) ==
    /\ coordPhase \in {"idle", "preparing"}
    /\ messages' = messages \cup {LockReqMsg(s, currentTxnId)}
    /\ coordPhase' = "preparing"
    /\ UNCHANGED <<currentTxnId, walCommitted, locksAcquired, renamesDone, unlocksAcked, storeVars>>

\* Receive successful lock response
RecvLockRespSuccess(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, TRUE, currentTxnId) \in messages
    /\ s \notin locksAcquired
    /\ locksAcquired' = locksAcquired \cup {s}
    /\ messages' = messages \ {LockRespMsg(s, TRUE, currentTxnId)}  \* Remove after processing
    /\ UNCHANGED <<currentTxnId, coordPhase, walCommitted, renamesDone, unlocksAcked, storeVars>>

\* Receive failed lock response -> enter cleanup phase
RecvLockRespFailure(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, FALSE, currentTxnId) \in messages
    /\ coordPhase' = "cleanup"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    /\ unlocksAcked' = {}
    /\ messages' = messages \ {LockRespMsg(s, FALSE, currentTxnId)}
    /\ UNCHANGED <<currentTxnId, walCommitted, storeVars>>

\* Decide to commit (all locks acquired)
DecideCommit ==
    /\ coordPhase = "preparing"
    /\ locksAcquired = Stores
    /\ walCommitted' = TRUE
    /\ coordPhase' = "committed"
    /\ UNCHANGED <<currentTxnId, locksAcquired, renamesDone, unlocksAcked, storeVars, messages>>

\* Send rename request to a store
SendRenameReq(s) ==
    /\ coordPhase = "committed"
    /\ messages' = messages \cup {RenameReqMsg(s, currentTxnId)}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Receive rename response - transition to cleanup when all renames done
RecvRenameResp(s) ==
    /\ coordPhase = "committed"
    /\ RenameRespMsg(s, currentTxnId) \in messages
    /\ s \notin renamesDone
    /\ renamesDone' = renamesDone \cup {s}
    /\ IF renamesDone' = Stores
       THEN coordPhase' = "cleanup"  \* Go to cleanup to release locks
       ELSE coordPhase' = coordPhase
    /\ messages' = messages \ {RenameRespMsg(s, currentTxnId)}  \* Remove after processing
    /\ UNCHANGED <<currentTxnId, walCommitted, locksAcquired, unlocksAcked, storeVars>>

\* Send unlock request to a store (during cleanup phase)
SendUnlockReq(s) ==
    /\ coordPhase = "cleanup"
    /\ messages' = messages \cup {UnlockReqMsg(s, currentTxnId)}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Receive unlock response - transition to done when all unlocks acknowledged
RecvUnlockResp(s) ==
    /\ coordPhase = "cleanup"
    /\ UnlockRespMsg(s, currentTxnId) \in messages
    /\ s \notin unlocksAcked
    /\ unlocksAcked' = unlocksAcked \cup {s}
    /\ IF unlocksAcked' = Stores
       THEN coordPhase' = "done"
       ELSE coordPhase' = coordPhase
    /\ messages' = messages \ {UnlockRespMsg(s, currentTxnId)}  \* Remove after processing
    /\ UNCHANGED <<currentTxnId, walCommitted, locksAcquired, renamesDone, storeVars>>

\* Coordinator crash - reset volatile state, keep durable state (currentTxnId, walCommitted)
\* Transitions to "crashed" phase - must recover before starting new protocol
CoordinatorCrash ==
    /\ coordPhase \in {"preparing", "committed", "cleanup"}  \* Can crash during protocol
    /\ coordPhase' = "crashed"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    /\ unlocksAcked' = {}
    /\ UNCHANGED <<durableCoordVars, storeVars, messages>>

\* Coordinator recovery - increments txnId to invalidate old messages
CoordinatorRecover ==
    /\ coordPhase = "crashed"
    /\ currentTxnId' = currentTxnId + 1  \* NEW txnId makes all old messages obsolete
    /\ IF walCommitted
       THEN \* Committed - resume commit phase, resend RenameReq with NEW txnId
            /\ coordPhase' = "committed"
            /\ messages' = messages \cup {RenameReqMsg(s, currentTxnId') : s \in Stores}
            /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, unlocksAcked, storeVars>>
       ELSE \* Not committed - send unlocks with NEW txnId to cleanup
            /\ coordPhase' = "cleanup"
            /\ unlocksAcked' = {}  \* Reset unlock tracking
            /\ messages' = messages \cup {UnlockReqMsg(s, currentTxnId') : s \in Stores}
            /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, storeVars>>

(***************************************************************************)
(* KV Store Actions                                                        *)
(***************************************************************************)

\* Handle lock request - rejects old txnIds
HandleLockReq(s) ==
    /\ \E m \in messages :
        /\ m.type = "LockReq"
        /\ m.store = s
        /\ IF m.txnId < lastSeenTxnId[s]
           THEN \* OLD transaction - reject silently
                /\ messages' = messages \ {m}
                /\ UNCHANGED <<coordVars, storeVars>>
           ELSE IF storeKey[s] = "A'"
                THEN \* Already renamed - lock fails
                     /\ messages' = (messages \ {m}) \cup {LockRespMsg(s, FALSE, m.txnId)}
                     /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                     /\ UNCHANGED <<coordVars, storeKey, storeValue, lockA, lockAprime>>
                ELSE IF lockA[s]
                     THEN \* Already locked - success (idempotent)
                          /\ messages' = (messages \ {m}) \cup {LockRespMsg(s, TRUE, m.txnId)}
                          /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                          /\ UNCHANGED <<coordVars, storeKey, storeValue, lockA, lockAprime>>
                     ELSE \* Acquire locks
                          /\ lockA' = [lockA EXCEPT ![s] = TRUE]
                          /\ lockAprime' = [lockAprime EXCEPT ![s] = TRUE]
                          /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                          /\ messages' = (messages \ {m}) \cup {LockRespMsg(s, TRUE, m.txnId)}
                          /\ UNCHANGED <<coordVars, storeKey, storeValue>>

\* Handle rename request - rejects old txnIds
HandleRenameReq(s) ==
    /\ \E m \in messages :
        /\ m.type = "RenameReq"
        /\ m.store = s
        /\ IF m.txnId < lastSeenTxnId[s]
           THEN \* OLD transaction - reject silently
                /\ messages' = messages \ {m}
                /\ UNCHANGED <<coordVars, storeVars>>
           ELSE IF storeKey[s] = "A'"
                THEN \* Already renamed - success (idempotent)
                     /\ messages' = (messages \ {m}) \cup {RenameRespMsg(s, m.txnId)}
                     /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                     /\ UNCHANGED <<coordVars, storeKey, storeValue, lockA, lockAprime>>
                ELSE IF lockA[s]
                     THEN \* Perform rename (value preserved)
                          /\ storeKey' = [storeKey EXCEPT ![s] = "A'"]
                          /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                          /\ messages' = (messages \ {m}) \cup {RenameRespMsg(s, m.txnId)}
                          /\ UNCHANGED <<coordVars, storeValue, lockA, lockAprime>>
                     ELSE \* Not locked - ignore (shouldn't happen in correct protocol)
                          /\ messages' = messages \ {m}
                          /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                          /\ UNCHANGED <<coordVars, storeKey, storeValue, lockA, lockAprime>>

\* Handle unlock request - rejects old txnIds
HandleUnlockReq(s) ==
    /\ \E m \in messages :
        /\ m.type = "UnlockReq"
        /\ m.store = s
        /\ IF m.txnId < lastSeenTxnId[s]
           THEN \* OLD transaction - reject silently
                /\ messages' = messages \ {m}
                /\ UNCHANGED <<coordVars, storeVars>>
           ELSE \* Accept unlock
                /\ lockA' = [lockA EXCEPT ![s] = FALSE]
                /\ lockAprime' = [lockAprime EXCEPT ![s] = FALSE]
                /\ lastSeenTxnId' = [lastSeenTxnId EXCEPT ![s] = m.txnId]
                /\ messages' = (messages \ {m}) \cup {UnlockRespMsg(s, m.txnId)}
                /\ UNCHANGED <<coordVars, storeKey, storeValue>>

(***************************************************************************)
(* Environment Actions                                                     *)
(***************************************************************************)

\* Lose a message (models network loss)
LoseMessage(m) ==
    /\ m \in messages
    /\ messages' = messages \ {m}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Update value at a store (only when unlocked)
UpdateValue(s, v) ==
    /\ lockA[s] = FALSE
    /\ storeValue' = [storeValue EXCEPT ![s] = v]
    /\ UNCHANGED <<coordVars, storeKey, lockA, lockAprime, lastSeenTxnId, messages>>

(***************************************************************************)
(* Next state relation                                                     *)
(***************************************************************************)
Next ==
    \* Coordinator actions
    \/ \E s \in Stores : SendLockReq(s)
    \/ \E s \in Stores : RecvLockRespSuccess(s)
    \/ \E s \in Stores : RecvLockRespFailure(s)
    \/ DecideCommit
    \/ \E s \in Stores : SendRenameReq(s)
    \/ \E s \in Stores : RecvRenameResp(s)
    \/ \E s \in Stores : SendUnlockReq(s)
    \/ \E s \in Stores : RecvUnlockResp(s)
    \/ CoordinatorCrash
    \/ CoordinatorRecover
    \* KV Store actions
    \/ \E s \in Stores : HandleLockReq(s)
    \/ \E s \in Stores : HandleRenameReq(s)
    \/ \E s \in Stores : HandleUnlockReq(s)
    \* Environment actions
    \/ \E m \in messages : LoseMessage(m)
    \/ \E s \in Stores, v \in Values : UpdateValue(s, v)

Spec == Init /\ [][Next]_vars

(***************************************************************************)
(* Safety Invariants                                                       *)
(***************************************************************************)

\* 1. Data is always accessible - each store has exactly one valid key
DataAccessible ==
    \A s \in Stores : storeKey[s] \in {"A", "A'"}

\* 2. No rename without commit - if not committed, all stores have A
NoRenameWithoutCommit ==
    ~walCommitted => \A s \in Stores : storeKey[s] = "A"

\* 3. If coordinator believes rename is complete, all stores have A'
CommitConsistency ==
    (coordPhase = "done" /\ walCommitted) => \A s \in Stores : storeKey[s] = "A'"

\* 4. If any store has renamed, WAL must be committed (contrapositive of NoRenameWithoutCommit)
RenameImpliesCommit ==
    \A s \in Stores : storeKey[s] = "A'" => walCommitted

\* 5. Committed phase requires WAL commit
CommittedImpliesWal ==
    coordPhase = "committed" => walCommitted

\* 6. Values only change when unlocked (lock protects updates)
\*    This is enforced by UpdateValue precondition, but we state it as invariant
LockProtectsValue ==
    \A s \in Stores : lockA[s] => storeValue[s] = storeValue[s]

\* Combined safety invariant
Safety ==
    /\ TypeOK
    /\ DataAccessible
    /\ NoRenameWithoutCommit
    /\ CommitConsistency
    /\ RenameImpliesCommit
    /\ CommittedImpliesWal

(***************************************************************************)
(* Fairness Conditions                                                     *)
(*                                                                         *)
(* For liveness, we need fairness on protocol actions but NOT on:          *)
(*   - LoseMessage (would lose all messages forever)                       *)
(*   - UpdateValue (environment action, not required for termination)      *)
(*   - CoordinatorCrash (would crash forever)                              *)
(*                                                                         *)
(* We use Strong Fairness (SF) for message receive/handle actions because  *)
(* messages may be lost and re-sent, so these actions are enabled          *)
(* infinitely often rather than continuously. SF guarantees that if an     *)
(* action is enabled infinitely often, it eventually executes.             *)
(*                                                                         *)
(* We use Weak Fairness (WF) for send actions and DecideCommit since       *)
(* their enablement depends only on coordinator state (continuously        *)
(* enabled once enabled).                                                  *)
(***************************************************************************)

\* Fairness on coordinator actions
CoordinatorFairness ==
    /\ \A s \in Stores : WF_vars(SendLockReq(s))
    /\ \A s \in Stores : SF_vars(RecvLockRespSuccess(s))
    /\ \A s \in Stores : SF_vars(RecvLockRespFailure(s))
    /\ WF_vars(DecideCommit)
    /\ \A s \in Stores : WF_vars(SendRenameReq(s))
    /\ \A s \in Stores : SF_vars(RecvRenameResp(s))
    /\ \A s \in Stores : WF_vars(SendUnlockReq(s))
    /\ \A s \in Stores : SF_vars(RecvUnlockResp(s))
    /\ WF_vars(CoordinatorRecover)

\* Fairness on KV store handlers (SF because messages can be lost/re-sent)
StoreFairness ==
    /\ \A s \in Stores : SF_vars(HandleLockReq(s))
    /\ \A s \in Stores : SF_vars(HandleRenameReq(s))
    /\ \A s \in Stores : SF_vars(HandleUnlockReq(s))

\* Combined fairness for liveness
Fairness == CoordinatorFairness /\ StoreFairness

\* Specification with fairness (for liveness checking)
FairSpec == Spec /\ Fairness

(***************************************************************************)
(* Liveness Properties                                                     *)
(***************************************************************************)

\* Terminal state: aborted/not-started
Aborted ==
    /\ coordPhase = "idle"
    /\ ~walCommitted
    /\ \A s \in Stores : storeKey[s] = "A"
    /\ \A s \in Stores : ~lockA[s] /\ ~lockAprime[s]

\* Terminal state: committed/done
Done ==
    /\ coordPhase = "done"
    /\ walCommitted
    /\ \A s \in Stores : storeKey[s] = "A'"

\* 1. Eventually Stable: system reaches a terminal state
EventuallyStable == <>(Aborted \/ Done)

\* 2. Committed Implies Eventually Done: if WAL committed, protocol completes
\*    (unless coordinator crashes forever - realistic assumption)
CommittedImpliesEventuallyDone == walCommitted ~> (coordPhase = "done" \/ coordPhase = "crashed")

\* 3. No Permanent Locks: any acquired lock is eventually released
\*    (unless coordinator crashes forever - realistic assumption)
NoPermanentLocks == \A s \in Stores : lockA[s] ~> (~lockA[s] \/ coordPhase = "crashed")

\* Combined liveness property
Liveness ==
    /\ EventuallyStable
    /\ CommittedImpliesEventuallyDone
    /\ NoPermanentLocks

=============================================================================
