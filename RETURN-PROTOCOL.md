# Return continuation protocol, version 1.0

A return is a new private continuation message, not a blind overwrite or a Git patch detached from platform context. It references the original capsule and the destination adaptation baseline. No return is applied merely because it is received or inspected.

## Common base and identities

The trusted receiver records a hash inventory immediately after materialization, and the explicit destination adapter records an updated baseline after sanctioned platform adaptation **before** new acceptance/results/work. `record_adaptation(receipt, details)` stores this baseline under `_relay/adaptation-baseline.json`, with its digest in the receiver receipt. The original immutable capsule remains independent.

`create_return(receipt, output)` compares the current mutable work against that baseline. Each changed/new/deleted file records its source logical path, working path, adaptation-base hash, original source-base hash where known, returned hash, size, mode and operation. The protocol does not claim that the source and adapted baselines are identical. Platform-adapted files require separate review before replacing source-platform code.

## Container and digests

The container is conventional ZIP/ZIP64 with DEFLATE. Logical contents:

```text
RETURN.json
RETURN-MANIFEST.json
RETURN-LETTER.md
objects/SHA256
SHA256SUMS.txt
```

Canonical JSON is UTF-8, sorted keys, compact separators, no nonfinite numbers, a terminal newline, and literal Unicode (`ensure_ascii=False`) for this return format. This definition is independent of the primary capsule JSON encoding; verification hashes actual archived bytes against the declared manifests.

SHA256SUMS.txt hashes every other member, including RETURN.json and the human letter. It excludes itself. Each object member name is its payload SHA-256 and must match the file-manifest result hash and size. The complete ZIP's hash is stored outside the archive as `ARCHIVE.zip.sha256`; there is no circular self-hash. Hash agreement is integrity against a retained reference, not sender authenticity.

The reader rejects unsupported major versions, duplicate/case-colliding ZIP members, arbitrary archive paths, links, excessive expansion, checksum/member disagreement, missing/unreferenced objects and inconsistent result/base fields. Limits are finite: 20,000 members, 2 GiB expanded total and 512 MiB per member. Exceeding them is an explicit failure, not a complete return.

## Operations and privacy

- ADD and UPDATE carry exact returned object bytes and relevant mode bits.
- DELETE is a proposal only; application requires explicit selection after preview.
- DATABASE_SNAPSHOT is a separate SQLite backup made through the database backup API and verified with integrity_check. Active laboratory jobs block capture. It is never an ordinary file/text merge.
- EXCLUDED_WITH_REASON accounts for detected secrets, credential stores, installed environment entries and ephemeral runtime/log material. Originals are not edited.

New destination verification/adaptation/handoff records under `_relay/` are preserved as separate additions under `_relay-returned/RETURN_ID/`; source historical knowledge/environment/Git inputs are not redundantly rewritten as current destination knowledge. The return includes a readable engineering letter summarizing observed changes without inventing undocumented intent.

Private credentials, API/key patterns, source/destination application access files and environment packages are omitted. Required secret injection remains destination-local. Capsules can still contain private research and must not be uploaded publicly. Exclusions and unimplemented database reconciliation are visible rather than silently labelled complete.

## Three-way preview

`preview_return(return_zip, current_project)` compares:

1. Adaptation/common-base hash and original source-base hash.
2. Independent current recipient bytes.
3. Returned result bytes.

The preview labels APPLICABLE, ALREADY_PRESENT, CONFLICT, DELETE_REQUIRES_SELECTION, PLATFORM_ADAPTATION_REVIEW, GUIDANCE_REVIEW_REQUIRED, DATABASE_RECONCILIATION_REQUIRED, EXCLUDED or ALREADY_PROCESSED.

If independent source bytes changed, the return never overwrites them automatically. A platform-adapted baseline is not treated as the same Linux source base. AGENTS changes require guidance review. Databases require logical migrations/record-level reconciliation using stable IDs; the first implementation deliberately records that prerequisite rather than inventing a generic database merge. This is hash-based three-way comparison and explicit conflict handling, not an automatic textual merge engine.

## Selected application and rollback

`apply_return(plan, selected=[...])` re-verifies the archive and the previewed current bytes before writing. Only selected safe ADD/UPDATE changes or explicitly selected proposed deletions are allowed. No capsule-provided program is executed. Existing symlink ancestors and containment escapes are refused. No newer independent changes are overwritten.

An owned `.relay-return-history/RETURN_ID/` stores before-bytes, their hashes/modes and an atomic application journal. Each file replacement is atomic; the collection is **not** a single multi-file transaction. An in-progress marker covers the gap between one file change and journal completion. A failed/interrupted application is retained for reviewed rollback rather than silently rerun as a new import.

`rollback_return(receipt)` restores only files still matching the applied return. If the recipient edited a file after import, rollback reports ROLLBACK_CONFLICT and preserves that work. Duplicate apply/receipt is idempotent; a processed return is never applied again automatically, even after rollback. A new return identity is needed for a new proposed application.

## Real commands

PowerShell, using the separately trusted receiver distribution:

```powershell
pwsh -File .\windows\Receive-Relay.ps1 -Operation Return -Python $Python `
  -Receipt $Receipt -Output 'E:\GENESIS-RELAY\outgoing\return.zip' -Apply

pwsh -File .\windows\Receive-Relay.ps1 -Operation ReturnPreview -Python $Python `
  -ReturnCapsule 'E:\GENESIS-RELAY\incoming\return.zip' `
  -Project 'E:\GENESIS-RELAY\projects\review-copy' -Output 'E:\GENESIS-RELAY\receipts\return-plan.json'

pwsh -File .\windows\Receive-Relay.ps1 -Operation ReturnApply -Python $Python `
  -Plan 'E:\GENESIS-RELAY\receipts\return-plan.json' -Selected 'README.md' -Apply

pwsh -File .\windows\Receive-Relay.ps1 -Operation ReturnRollback -Python $Python `
  -Receipt 'ACTUAL-APPLY-RECEIPT-PATH' -Apply
```

The portable APIs live in `genesis_relay.returns`. The Linux CLI exposes equivalent operations where documented by `relay --help`. Use exact paths returned by your receipt/preview; the examples do not invent a destination connection.

Synthetic tests demonstrate harmless application, deliberate conflict, stale preview, explicit deletion policy, private credential exclusion, separate SQLite snapshots, duplicate import, interrupted-journal rollback and preservation of edits made after import. A relocated Linux demonstration is not a Windows return acceptance claim.

## Version 1 boundaries

Return comparison and application cover regular files. New symlinks, symlinked directories and empty-directory topology are not reconciled. Preserve these in a new full continuation capsule or review them separately. Platform adaptations and source guidance require explicit review; conflicts do not trigger automatic text merging.

Create a return while the destination is idle or under a project-specific checkpoint. SQLite backup integrity does not by itself establish a transaction across concurrently changing database records and result files. The real demonstration briefly quiesced only the owned relocated laboratory before return capture. The original full capsule has a separate, stronger verified snapshot checkpoint.

Application uses per-file replacement, backups and a journal. It is not one atomic transaction across all selected files. An interrupted application requires inspection and reviewed rollback; reimporting an already rolled-back return remains a duplicate no-op. Rollback refuses to destroy newer work. Source byte evidence remains intact, but working restoration does not reconstruct ACLs, extended attributes, hardlink relationships or all directory permission/timestamp semantics.
