# Install on Windows x64

Use the experimental Windows asset named `GENESIS-RELAY-0.1.0-windows-x86_64.zip`. Compare its SHA-256 with the separately retained release manifest/checksums. Hash agreement detects differences against that reference; it does not establish authorship.

Extract the ZIP into a new folder you own. Keep `Genesis-Relay.exe`, `_internal`, scripts and documentation together. The executable bundles Relay's own Python runtime; you do not need to install Python merely to open Relay, inspect a capsule or use the trusted synthetic demo. PowerShell 7 is required for the receiver script. Reconstructing another Python project may require a compatible separate Python environment and its dependencies.

```powershell
Set-Location 'C:\Tools\GENESIS-RELAY-0.1.0-windows-x86_64'
.\Genesis-Relay.exe --version
.\Genesis-Relay.exe ui start
.\Genesis-Relay.exe ui access
```

Open the actual loopback URL printed by startup, sign in with the credentials shown in your terminal and follow QUICKSTART.md. The application selects an unused local port. Do not expose its management interface publicly. `ui status`, `ui stop` and `ui restart` apply only to the identity-verified Relay process. `--state-dir 'C:\Private\RelayState'` selects a separate persistent state area; it belongs before the command.

## Receive a project

Use the trusted script shipped beside the executable. Inspect never executes a capsule's code or instructions, installs dependencies or launches Codex.

```powershell
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Inspect -Capsule 'C:\Transfer\project.zip'
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Plan -Capsule 'C:\Transfer\project.zip' -Root 'E:\GENESIS-RELAY' -Route NATIVE_WINDOWS_X64
```

The receiver prefers `E:\GENESIS-RELAY` only if E: exists. Otherwise provide an explicit alternative. Review Plan, then use its documented Restore operation with `-Apply`. Preserve the original ZIP, materialize only into a new working copy and use the actual returned receipt path. Existing unrelated projects are never an overwrite target.

## Routes and evidence

Native Windows and WSL Linux x64 are separate routes. Read the release verification summary for actual runner, architecture, executable and synthetic-demo results. A Windows-hosted demo pass does not establish the full private Science Lab port, your personal workstation, WSL or a Windows Codex session. The optional scientific laboratory profile still needs its destination-specific engines and process compatibility; copied Linux binaries are not Windows installations.

A fresh Windows Codex test requires an already installed, authenticated local CLI and an explicit LaunchCodex operation. Relay never ships authentication or modifies global Codex/MCP configuration. That test may remain NOT_RUN even when the executable and synthetic project have passed.

## Python wheel alternative and removal

With an existing compatible Python, create a new venv and install the downloaded wheel with `python -m pip install --no-index --no-deps PATH_TO_WHEEL`. Use that environment's `relay` command. Do not substitute the bundled Relay executable for a project interpreter.

Stop the owned UI before removing an extracted installation folder. Private state, received capsules, projects and receipts are stored separately and are not automatically deleted. Review them explicitly before any cleanup. Keep backups and retained checksum references independently.
