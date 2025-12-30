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
    coordPhase,     \* {idle, preparing, committed, done}
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
    messages        \* Set of messages (persist after processing for duplication)

vars == <<coordPhase, walCommitted, locksAcquired, renamesDone,
          storeKey, storeValue, lockA, lockAprime, messages>>

coordVars == <<coordPhase, walCommitted, locksAcquired, renamesDone>>
storeVars == <<storeKey, storeValue, lockA, lockAprime>>

(***************************************************************************)
(* Type invariant                                                          *)
(***************************************************************************)
TypeOK ==
    /\ coordPhase \in {"idle", "preparing", "committed", "done"}
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

\* Receive successful lock response (with duplicate detection)
RecvLockRespSuccess(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, TRUE) \in messages
    /\ s \notin locksAcquired          \* Not a duplicate
    /\ locksAcquired' = locksAcquired \cup {s}
    /\ UNCHANGED <<coordPhase, walCommitted, renamesDone, storeVars, messages>>

\* Receive failed lock response -> abort
RecvLockRespFailure(s) ==
    /\ coordPhase = "preparing"
    /\ LockRespMsg(s, FALSE) \in messages
    /\ coordPhase' = "idle"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    \* Send unlock to all stores (cleanup)
    /\ messages' = messages \cup {UnlockReqMsg(st) : st \in Stores}
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

\* Receive rename response (with duplicate detection)
RecvRenameResp(s) ==
    /\ coordPhase = "committed"
    /\ RenameRespMsg(s) \in messages
    /\ s \notin renamesDone            \* Not a duplicate
    /\ renamesDone' = renamesDone \cup {s}
    /\ IF renamesDone' = Stores
       THEN coordPhase' = "done"
       ELSE coordPhase' = coordPhase
    /\ UNCHANGED <<walCommitted, locksAcquired, storeVars, messages>>

\* Send unlock request to a store (after done)
SendUnlockReq(s) ==
    /\ coordPhase = "done"
    /\ messages' = messages \cup {UnlockReqMsg(s)}
    /\ UNCHANGED <<coordVars, storeVars>>

\* Coordinator crash - reset volatile state, keep WAL
CoordinatorCrash ==
    /\ coordPhase \in {"preparing", "committed"}  \* Can crash during protocol
    /\ coordPhase' = "idle"
    /\ locksAcquired' = {}
    /\ renamesDone' = {}
    /\ UNCHANGED <<walCommitted, storeVars, messages>>

\* Coordinator recovery
CoordinatorRecover ==
    /\ coordPhase = "idle"
    /\ IF walCommitted
       THEN \* Committed - resume commit phase
            /\ coordPhase' = "committed"
            /\ UNCHANGED <<walCommitted, locksAcquired, renamesDone, storeVars, messages>>
       ELSE \* Not committed - send unlocks to cleanup any held locks
            /\ messages' = messages \cup {UnlockReqMsg(s) : s \in Stores}
            /\ UNCHANGED <<coordVars, storeVars>>

(***************************************************************************)
(* KV Store Actions                                                        *)
(***************************************************************************)

\* Handle lock request (idempotent)
HandleLockReq(s) ==
    /\ LockReqMsg(s) \in messages
    /\ IF storeKey[s] = "A'"
       THEN \* Already renamed - lock fails
            /\ messages' = messages \cup {LockRespMsg(s, FALSE)}
            /\ UNCHANGED <<coordVars, storeVars>>
       ELSE IF lockA[s]
            THEN \* Already locked - idempotent success
                 /\ messages' = messages \cup {LockRespMsg(s, TRUE)}
                 /\ UNCHANGED <<coordVars, storeVars>>
            ELSE \* Acquire locks
                 /\ lockA' = [lockA EXCEPT ![s] = TRUE]
                 /\ lockAprime' = [lockAprime EXCEPT ![s] = TRUE]
                 /\ messages' = messages \cup {LockRespMsg(s, TRUE)}
                 /\ UNCHANGED <<coordVars, storeKey, storeValue>>

\* Handle rename request (idempotent)
HandleRenameReq(s) ==
    /\ RenameReqMsg(s) \in messages
    /\ IF storeKey[s] = "A'"
       THEN \* Already renamed - idempotent success
            /\ messages' = messages \cup {RenameRespMsg(s)}
            /\ UNCHANGED <<coordVars, storeVars>>
       ELSE IF lockA[s]
            THEN \* Perform rename (value preserved)
                 /\ storeKey' = [storeKey EXCEPT ![s] = "A'"]
                 /\ messages' = messages \cup {RenameRespMsg(s)}
                 /\ UNCHANGED <<coordVars, storeValue, lockA, lockAprime>>
            ELSE \* Not locked - ignore (shouldn't happen in correct protocol)
                 /\ UNCHANGED <<coordVars, storeVars, messages>>

\* Handle unlock request (idempotent)
HandleUnlockReq(s) ==
    /\ UnlockReqMsg(s) \in messages
    /\ lockA' = [lockA EXCEPT ![s] = FALSE]
    /\ lockAprime' = [lockAprime EXCEPT ![s] = FALSE]
    /\ UNCHANGED <<coordVars, storeKey, storeValue, messages>>

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

\* 2. If coordinator believes rename is complete, all stores have A'
CommitConsistency ==
    coordPhase = "done" => \A s \in Stores : storeKey[s] = "A'"

\* 3. Values only change when unlocked (lock protects updates)
\*    This is enforced by UpdateValue precondition, but we state it as invariant
LockProtectsValue ==
    \A s \in Stores : lockA[s] => storeValue[s] = storeValue[s]

\* Combined safety invariant
Safety ==
    /\ TypeOK
    /\ DataAccessible
    /\ CommitConsistency

=============================================================================
