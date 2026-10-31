# Project Continuation Capsule format 1.0

Container: ZIP, conventional Deflate or stored members, ZIP64 permitted. No ZIP member is an executable link or directory. Payload names are portable fixed ASCII names: metadata, knowledge, environment/history records, and `objects/<64 lowercase SHA-256 hex>`. The manifest retains original root-relative Unicode paths, modes, timestamps, link targets and dispositions. A Windows-incompatible name therefore does not require lossy renaming in source evidence; the receiver records a separate working-copy mapping.

## Required members

- CAPSULE.json: format `genesis-relay`, version `1.0`, capsule/project IDs, roots, platform/architecture, UTC interval, parent capsule, dependencies, source checkpoint, payload names/digests/sizes and explicit route limitations.
- FILE-MANIFEST.json: schema version and every selected-root entry, including hidden files/directories and exclusions. Included regular files reference hashed object members. SQLite backups are INCLUDED_TRANSFORMED with source and snapshot metadata; originals are not rewritten.
- COMPLETENESS.json: counts/bytes, full vs lightweight, unresolved entries, database/artifact proof, Git/history completeness, and explicitly false offline-ready unless independently established.
- START-HERE.md plus knowledge/: readable engineering letter and EVIDENCE-INDEX.json.
- environments/: exact source metadata, destination-oriented requested requirements and recipes; no foreign installed environment is a destination installation.
- history/: verified Git bundle/patches when available, otherwise versioned manifest history; shallow/missing objects and submodule/LFS gaps remain visible.
- SHA256SUMS.txt: one `lowercasehex`, two spaces, portable ZIP name per line.

## Canonical JSON and digest coverage

Generated JSON is UTF-8 with `ensure_ascii=True`, keys sorted, separators comma/colon without optional spaces, finite values only, and one final LF. Paths are JSON strings; source file bytes, Unicode text and line endings are not normalized. The receiver must not reinterpret a logical filename as execution authority.

CAPSULE.payloads contains SHA-256 and byte size for every member except CAPSULE.json and SHA256SUMS.txt. SHA256SUMS.txt covers every other ZIP member, including CAPSULE.json, and excludes itself. A final archive SHA-256 is written outside the archive as `<archive>.sha256`; no circular archive self-hash is claimed. Return capsules use a separately named `genesis-relay-return` protocol with parent/base hashes.

## Validation before extraction

The reader rejects unsupported major versions, invalid JSON/duplicate keys, missing required members, duplicate/case-colliding/NFC-colliding ZIP names, traversal, drive/UNC/ADS names, reserved Windows ZIP names, trailing dot/space, unsafe links/special members, encryption/unsupported compression, count/size/expansion violations, checksum disagreement, payload set disagreement, invalid logical root/type/disposition and missing file objects. Expanded bytes are hashed by streaming; no project code executes. Defaults: 100,000 entries, 8 GiB expanded bytes, 32 MiB individual metadata and a finite compression-ratio guard. These are bounded v1 defaults, not proof of operation on arbitrarily large projects.

Original logical project paths may contain names that Windows cannot materialize, but cannot contain absolute/traversal paths. The receiver records case/reserved-name/Unicode mappings and preserves original object bytes in the unchanged capsule. It materializes only into a new Relay-owned directory, preserves original source guidance inertly, and creates explicit destination guidance.

## Privacy and consistency

Every selected entry receives INCLUDED_EXACT, INCLUDED_TRANSFORMED, DEPENDENCY_REFERENCE, EXCLUDED_WITH_REASON or UNREADABLE_OR_MISSING. Exact means source bytes in immutable evidence, not a promise that a working copy must retain foreign path assumptions. Credentials are explicit exclusions with destination-local injection points. Secret matches in otherwise required source qualify completeness and are visible; missing required entries prevent an unqualified full claim.

SQLite uses its backup API and integrity checks. The Science Lab adapter coordinates capture through verified-idle, identity-checked temporary service quiescence, validates all succeeded-job artifact references and stable run IDs, then restores prior service state. Source evidence describes capture-time state; the sender's post-capture receipt records actual restart. Files are copied/hash-checked with bounded retry and entry-set comparison. Generic multi-file consistency has narrower limits than this known application checkpoint.

Partial outputs are retained under partial/staging names. Final rename occurs only after strict verification. Export never overwrites a valid existing archive. Archive digest and receipt IDs support duplicate detection; an actual destination receipt, not a download link, establishes transport scope.

Integrity is not authenticity. An attacker able to replace both a capsule and its digest can fabricate an internally consistent capsule. Existing GPG detached signatures are optional and require a separately trusted key; no new cryptography is invented.
