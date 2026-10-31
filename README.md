# GENESIS RELAY

**Projects and their stories, ready to continue.** GENESIS RELAY packages an engineering project with its documented purpose, source, dependencies, history, verification evidence and continuation instructions. A receiving workspace reconstructs supported projects and exchanges selected improvements through versioned Project Continuation Capsules.

The browser interface shows what will travel, what arrived, which checks ran and what remains unfinished. The archive core needs no AI service, Sentinel installation or scientific stack. The included synthetic laboratory uses Python's standard library and invented data.

## Try it in three steps

1. Download the package for your system from [Releases](https://github.com/chatgptopenaiagi/GENESIS-RELAY/releases). Windows: extract the Windows x64 ZIP. Linux: extract the archive for your architecture. Read [INSTALL-WINDOWS.md](INSTALL-WINDOWS.md) or [INSTALL-LINUX.md](INSTALL-LINUX.md) for exact runtime requirements.
2. Start Relay and show your local login in an operator terminal:

   ```powershell
   # Windows, from the extracted folder
   .\Genesis-Relay.exe ui start
   .\Genesis-Relay.exe ui access
   ```

   ```bash
   # Linux ARM64 launcher; x86_64 also supplies ./Genesis-Relay
   ./relay ui start
   ./relay ui access
   ```

3. Open the URL printed by startup. The default source is an owned synthetic laboratory. Choose **Send my laboratory → Review scope → Create full capsule**, then **Receive and continue → Restore separate copy → Run demo acceptance**. The original source stays separate from the restored copy.

Startup chooses an available loopback port. Management requires a local login, exact Host/Origin checks and CSRF protection. `ui access` prints credentials only to your terminal. Use `ui stop` to stop only the owned Relay interface. To select your own project, use `ui start --source /absolute/project` with an explicit private state directory when appropriate.

[Quickstart](QUICKSTART.md) · [Windows installation](INSTALL-WINDOWS.md) · [Linux installation](INSTALL-LINUX.md) · [Known limitations](KNOWN-LIMITATIONS.md) · [Release verification](VERIFICATION-SUMMARY.json)

## What a capsule preserves

A full capsule records selected source bytes, hidden/uncommitted files, relevant data/results, dependency references, Git history where available, database-aware snapshots and an evidence-indexed engineering letter. Every selected entry receives an explicit disposition. Credentials and installed environments are not silently copied as portable dependencies. Read the completeness report before calling an export complete.

Source evidence remains immutable; adaptations affect a new destination working copy. Downloaded, received, integrity verified, restored, tested and ready are separate milestones. Native Windows, WSL, Linux-local tests, synthetic demonstrations and private scientific results have different scopes. A successful demo does not certify an arbitrary application or the operator's workstation.

Returns compare common source/adaptation bases with current and returned bytes. Review and select safe whole-file changes; conflicts preserve newer work. SQLite returns are separate snapshots requiring manual/logical reconciliation. Relay does not automatically merge databases or text hunks.

## Core commands

```bash
relay --state-dir /absolute/private/state plan /absolute/project
relay --state-dir /absolute/private/state export /absolute/project --output /absolute/private/project.zip --no-quiesce
relay inspect /absolute/private/project.zip --summary
relay verify /absolute/private/project.zip --summary
relay restore /absolute/private/project.zip --destination /absolute/new/receiver --route LOCAL_LINUX
relay restore /absolute/private/project.zip --destination /absolute/new/receiver --route LOCAL_LINUX --apply
relay return /absolute/receiver/receipts/CAPSULE_ID.json --output /absolute/private/return.zip
```

The first restore command plans without applying. Use the receipt path actually returned by restoration. The trusted PowerShell receiver exposes Inspect, Plan, Restore, Verify, Open, LaunchCodex and Return operations. Inspection executes no project code or model calls. Installing Relay is separate from acquiring destination dependencies.

## Engineering knowledge

[THEORY.md](THEORY.md), [ARCHITECTURE.md](ARCHITECTURE.md), [CAPSULE-FORMAT.md](CAPSULE-FORMAT.md), [KNOWLEDGE-HANDOFF.md](KNOWLEDGE-HANDOFF.md) and [RETURN-PROTOCOL.md](RETURN-PROTOCOL.md) explain the implemented algorithms and their limits. Relay preserves documented decisions and observable evidence, not a model's hidden reasoning or internal memory.

The project was originated and directed by the operator of the `chatgptopenaiagi` account, with AI-assisted engineering using Codex. Existing GENESIS Relay contributors attribution and the MIT license are preserved. Established archive, hashing, SQLite, Git, locking and comparison techniques are acknowledged; no universal novelty or priority claim is made.

This experimental 0.1.0 publication continues the existing implementation. Private laboratory capsules, credentials, personal inventories and research are outside the public source and release assets. Consult the release's verification summary for actual OS, architecture, Python, executable and workflow results; building a package alone is not acceptance.
