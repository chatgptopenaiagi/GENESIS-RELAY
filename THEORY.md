# Continuation capsules: preserving engineering knowledge

A backup preserves bytes. A continuation capsule additionally records what those bytes mean for future work: documented purpose, intended human experience, current verified behavior, historical failures, environment interfaces, consistency boundaries, unfinished ideas and a concrete next mission. It is not a replacement for an independent backup or a way to transfer hidden model thoughts.

## Evidence and context

The project is the unit of scope. Source documents and operator requirements support claims; actual tests support bounded results. Historical reports remain timestamped historical evidence. Rationale inferred from code is labelled inference, missing context UNKNOWN, future plans proposals. A receiving engineer can inspect the evidence index without the sending chat or login. External files become new session input; they do not modify model weights or silently refresh an already running conversation.

## Consistent source evidence

The implementation keeps a root-relative logical manifest and a content-addressed object store. Streaming SHA-256 identifies exact included bytes; duplicate objects need one payload. Original names/line endings remain in source evidence even when a working-platform filename must change. Explicit dispositions prevent convenient exclusions from becoming invisible data loss. Dependency references preserve source environment information without pretending a foreign binary environment is installed on a different architecture.

File-level before/after signatures, copied-byte digests, a second source digest and entry-set checks detect ordinary capture races. Retries are bounded. They are not a universal transactional filesystem snapshot or proof against a malicious kernel. The known Science Lab profile adds application coordination: verify owned idle service, quiesce briefly, SQLite backup, stable artifacts and database relationships, then restore previous service state. SQLite backup provides a coherent committed database view; arbitrary cross-application transactions need their own adapter.

## Reconstructing capabilities

A working copy is new state, separate from immutable evidence. Destination interpreters, package origins, external executables and services must be discovered there. Installed metadata is weaker than an import, and an import is weaker than a correct experiment. Native Windows x64, WSL Linux x64 and relocated Linux ARM64 are different observations. Missing required dependencies block the affected workflow; missing optional engines must not erase supported workflows. Numerical agreement uses declared analytic expectations/tolerances, not arbitrary output byte identity across BLAS versions and operating systems.

Environment recipes capture requested, portable intent separately from exact source versions. Linux packages and site-packages cannot be renamed into a Windows environment. Focused adapters may change process management, ports, Unix resources and launchers while preserving scientific algorithms and recording the diff. Windows cannot be marked ready merely because PowerShell parses on Linux.

## State, trust and interruption

Persisted milestones describe what actually happened. A capsule being available locally is VERIFIED_FOR_TRANSFER, not proof of transport. A destination receipt establishes receipt scope; source hash verification, restoration, tests and continuation readiness follow independently. Failure events do not erase prior successful evidence. A local loopback roundtrip is useful but does not become a disconnected workstation success.

Canonical metadata and exact digest coverage prevent ambiguous self-hashing. Hashes establish differences against a retained reference, not the identity of its author. Imported source, scripts and AGENTS are inputs, not unrestricted authority. Receiver validation and a reviewed explicit bootstrap precede execution. Authentication, tokens and private keys stay on their respective machines; research can remain private even after credentials are excluded.

Single-writer ownership, partial names, bounded commands, streaming data and atomic replacements reduce resource pressure and prevent incomplete output from replacing valid output. Receipt/object identities allow safe resume and duplicate refusal. Atomic file rename does not provide a global multi-file transaction, and recovery logs are not proof against every hardware or power-loss scenario.

## Two-way knowledge

A return letter relates changes to the common source capsule and destination adaptation baseline. Three-way hashes distinguish an unchanged base, a harmless new addition and independently edited conflicts. Source-specific changes, platform adaptations, guidance and database work have different review requirements. Databases are not line-based text patches. Selected application and rollback preserve newer work; neither return import nor a prior successful receipt gives permission to overwrite an unrelated project.

## Established techniques and project composition

ZIP/ZIP64, content addressing, SHA-256, SQLite backup, Git bundles/patches, canonical serialization, process identity, file locks, atomic rename, journals, three-way comparison and scoped environment recreation are established engineering techniques. Relay's project-specific contribution is their explicit continuation contract: the engineering letter, complete disposition accounting, independent human-visible milestones, source/destination separation, route-qualified acceptance and return protocol. No historical priority, universal novelty or access to private model reasoning is claimed.

Read CAPSULE-FORMAT.md, ARCHITECTURE.md and RETURN-PROTOCOL.md for implemented contracts and TEST-RESULTS.json for actual scope. A concise receiving mission should be small and testable: use the recorded interpreter to run one known experiment, inspect its saved provenance, and write a new handoff without changing immutable evidence or global authentication.

## Public demonstration and attribution

The public lightweight laboratory uses invented values, a small SQLite database, saved deterministic results and a bounded continuation task. It tests the continuation contract without requiring the author's phone, scientific installations or AI account. A native Windows demo result is evidence about that exact demo and artifact, not the full private scientific laboratory or every project using the capsule format.

The operator of `chatgptopenaiagi` originated and directed GENESIS RELAY; implementation was AI-assisted using Codex. The theory preserves observable design rationale and documented requirements, with established techniques acknowledged. No claim is made to transfer hidden reasoning, model weights or personal authentication.
