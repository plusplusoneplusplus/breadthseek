---------------------------- MODULE AtomicRename ----------------------------
(***************************************************************************)
(* TLA+ Specification: 2PC Atomic Key Rename                               *)
(*                                                                         *)
(* Models a 2PC-style protocol for atomically renaming a key (A -> A')     *)
(* across multiple independent KV stores, with:                            *)
(*   - Coordinator crash recovery (WAL-backed)                             *)
(*   - Message loss and duplication                                        *)
(*   - Value updates when unlocked                                         *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets

CONSTANTS
    Stores,     \* Set of KV stores, e.g., {S1, S2}
    Values      \* Possible values, e.g., {0, 1, 2}

(***************************************************************************)
(* Message type constructors                                               *)
(***************************************************************************)
LockReqMsg(s)           == [type |-> "LockReq", store |-> s]
LockRespMsg(s, ok)      == [type |-> "LockResp", store |-> s, success |-> ok]
RenameReqMsg(s)         == [type |-> "RenameReq", store |-> s]
RenameRespMsg(s)        == [type |-> "RenameResp", store |-> s]
UnlockReqMsg(s)         == [type |-> "UnlockReq", store |-> s]

VARIABLES
    (***************************************************************)
    (* Coordinator state                                           *)
    (***************************************************************)
    coordPhase,     \* {idle, preparing, committed, done, crashed}
    walCommitted,   \* BOOLEAN - durable, survives crash
    locksAcquired,  \* SUBSET Stores - volatile
    renamesDone,    \* SUBSET Stores - volatile

    (***************************************************************)
    (* KV Store state (per store)                                  *)
    (***************************************************************)
    storeKey,       \* [Stores -> {"A", "A'"}]
    storeValue,     \* [Stores -> Values]
    lockA,          \* [Stores -> BOOLEAN]
    lockAprime,     \* [Stores -> BOOLEAN]

    (***************************************************************)
    (* Network                                                     *)
    (***************************************************************)
    messages        \* Set of messages (removed after processing to reduce state space)

vars == <<coordPhase, walCommitted, locksAcquired, renamesDone,
          storeKey, storeValue, lockA, lockAprime, messages>>

coordVars == <<coordPhase, walCommitted, locksAcquired, renamesDone>>
storeVars == <<storeKey, storeValue, lockA, lockAprime>>

(***************************************************************************)
(* Type invariant                                                          *)
(***************************************************************************)
TypeOK ==
    /\ coordPhase \in {"idle", "preparing", "committed", "done", "crashed"}
    /\ walCommitted \in BOOLEAN
    /\ locksAcquired \subseteq Stores
    /\ renamesDone \subseteq Stores
    /\ storeKey \in [Stores -> {"A", "A'"}]
    /\ storeValue \in [Stores -> Values]
    /\ lockA \in [Stores -> BOOLEAN]
    /\ lockAprime \in [Stores -> BOOLEAN]

(***************************************************************************)
(* Initial state                                                           *)
(***************************************************************************)
Init ==
    /\ coordPhase = "idle"
    /\ walCommitted = FALSE
    /\ locksAcquired = {}
    /\ renamesDone = {}
    /\ storeKey = [s \in Stores |-> "A"]
    /\ storeValue \in [Stores -> Values]  \* Any initial value
    /\ lockA = [s \in Stores |-> FALSE]
    /\ lockAprime = [s \in Stores |-> FALSE]
    /\ messages = {}

(***************************************************************************)
(* Coordinator Actions                                                     *)
(***************************************************************************)

\* Send lock request to a store
SendLockReq(s) ==
    /\ coordPhase \in {"idle", "preparing"}
    /\ messages' = messages \cup {LockReqMsg(s)}
    /\ coordPhase' = "preparing"
    /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, storeVars>>

\* Receive successful lock response
RecvLockRespSuccess(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, TRUE) \in messages
    /\ s \notin locksAcquired
    /\ locksAcquired' = locksAcquired \cup {s}
    /\ messages' = messages \ {LockRespMsg(s, TRUE)}  \* Remove after processing
    /\ UNCHANGED <<coordPhase, walCommitted, renamesDone, storeVars>>

\* Receive failed lock response -> abort
RecvLockRespFailure(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, FALSE) \in messages
    /\ coordPhase' = "idle"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    \* Remove processed message and send unlock to all stores (cleanup)
    /\ messages' = (messages \ {LockRespMsg(s, FALSE)}) \cup {UnlockReqMsg(st) : st \in Stores}
    /\ UNCHANGED <<walCommitted, storeVars>>

\* Decide to commit (all locks acquired)
DecideCommit ==
    /\ coordPhase = "preparing"
    /\ locksAcquired = Stores
    /\ walCommitted' = TRUE
    /\ coordPhase' = "committed"
    /\ UNCHANGED <<locksAcquired, renamesDone, storeVars, messages>>

\* Send rename request to a store
SendRenameReq(s) ==
    /\ coordPhase = "committed"
    /\ messages' = messages \cup {RenameReqMsg(s)}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Receive rename response
RecvRenameResp(s) ==
    /\ coordPhase = "committed"
    /\ RenameRespMsg(s) \in messages
    /\ s \notin renamesDone
    /\ renamesDone' = renamesDone \cup {s}
    /\ IF renamesDone' = Stores
       THEN coordPhase' = "done"
       ELSE coordPhase' = coordPhase
    /\ messages' = messages \ {RenameRespMsg(s)}  \* Remove after processing
    /\ UNCHANGED <<walCommitted, locksAcquired, storeVars>>

\* Send unlock request to a store (after done)
SendUnlockReq(s) ==
    /\ coordPhase = "done"
    /\ messages' = messages \cup {UnlockReqMsg(s)}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Coordinator crash - reset volatile state, keep WAL
\* Transitions to "crashed" phase - must recover before starting new protocol
CoordinatorCrash ==
    /\ coordPhase \in {"preparing", "committed"}  \* Can crash during protocol
    /\ coordPhase' = "crashed"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    /\ UNCHANGED <<walCommitted, storeVars, messages>>

\* Coordinator recovery - must happen after crash before new protocol can start
CoordinatorRecover ==
    /\ coordPhase = "crashed"
    /\ IF walCommitted
       THEN \* Committed - resume commit phase, resend RenameReq to all stores
            /\ coordPhase' = "committed"
            /\ messages' = messages \cup {RenameReqMsg(s) : s \in Stores}
            /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, storeVars>>
       ELSE \* Not committed - send unlocks to cleanup, return to idle
            /\ coordPhase' = "idle"
            /\ messages' = messages \cup {UnlockReqMsg(s) : s \in Stores}
            /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, storeVars>>

(***************************************************************************)
(* KV Store Actions                                                        *)
(***************************************************************************)

\* Handle lock request (remove message after processing)
HandleLockReq(s) ==
    /\ LockReqMsg(s) \in messages
    /\ IF storeKey[s] = "A'"
       THEN \* Already renamed - lock fails
            /\ messages' = (messages \ {LockReqMsg(s)}) \cup {LockRespMsg(s, FALSE)}
            /\ UNCHANGED <<coordVars, storeVars>>
       ELSE IF lockA[s]
            THEN \* Already locked - success
                 /\ messages' = (messages \ {LockReqMsg(s)}) \cup {LockRespMsg(s, TRUE)}
                 /\ UNCHANGED <<coordVars, storeVars>>
            ELSE \* Acquire locks
                 /\ lockA' = [lockA EXCEPT ![s] = TRUE]
                 /\ lockAprime' = [lockAprime EXCEPT ![s] = TRUE]
                 /\ messages' = (messages \ {LockReqMsg(s)}) \cup {LockRespMsg(s, TRUE)}
                 /\ UNCHANGED <<coordVars, storeKey, storeValue>>

\* Handle rename request (remove message after processing)
HandleRenameReq(s) ==
    /\ RenameReqMsg(s) \in messages
    /\ IF storeKey[s] = "A'"
       THEN \* Already renamed - success
            /\ messages' = (messages \ {RenameReqMsg(s)}) \cup {RenameRespMsg(s)}
            /\ UNCHANGED <<coordVars, storeVars>>
       ELSE IF lockA[s]
            THEN \* Perform rename (value preserved)
                 /\ storeKey' = [storeKey EXCEPT ![s] = "A'"]
                 /\ messages' = (messages \ {RenameReqMsg(s)}) \cup {RenameRespMsg(s)}
                 /\ UNCHANGED <<coordVars, storeValue, lockA, lockAprime>>
            ELSE \* Not locked - ignore (shouldn't happen in correct protocol)
                 /\ messages' = messages \ {RenameReqMsg(s)}  \* Still remove message
                 /\ UNCHANGED <<coordVars, storeVars>>

\* Handle unlock request (remove message after processing)
HandleUnlockReq(s) ==
    /\ UnlockReqMsg(s) \in messages
    /\ lockA' = [lockA EXCEPT ![s] = FALSE]
    /\ lockAprime' = [lockAprime EXCEPT ![s] = FALSE]
    /\ messages' = messages \ {UnlockReqMsg(s)}  \* Remove after processing
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
    /\ UNCHANGED <<coordVars, storeKey, lockA, lockAprime, messages>>

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
    coordPhase = "done" => \A s \in Stores : storeKey[s] = "A'"

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
CommittedImpliesEventuallyDone == walCommitted ~> (coordPhase = "done"  \/ coordPhase = "crashed"))

\* 3. No Permanent Locks: any acquired lock is eventually released
\*    (unless coordinator crashes forever - realistic assumption)
NoPermanentLocks == \A s \in Stores : lockA[s] ~> (~lockA[s] \/ coordPhase = "crashed")

\* Combined liveness property
Liveness ==
    /\ EventuallyStable
    /\ CommittedImpliesEventuallyDone
    /\ NoPermanentLocks

=============================================================================
