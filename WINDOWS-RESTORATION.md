# Windows receiver and restoration routes

The receiver is functioning software, but this sender has no authorized connected Windows workstation. **WINDOWS_EXECUTION_NOT_RUN** is the current qualification. PowerShell 7 parsing and an actual Inspect operation have been tested on Linux; that is not native-Windows or WSL acceptance.

## Trusted receiver, private capsule

Use the separately delivered Relay software distribution. `windows/Receive-Relay.ps1` is trusted receiver code; restoration scripts or AGENTS.md found inside a capsule are project inputs and do not grant execution authority. The source distribution places `windows/` beside `src/`. A verified installed Relay wheel can also supply the Python module when no adjacent trusted source exists.

The wrapper uses Python isolated mode. When the trusted source tree is present, it inserts only that explicit source directory before importing Relay. This prevents a malicious `genesis_relay` package in the current capsule/project directory from executing during Inspect. No shell-profile, Codex authentication, global configuration or model setting is changed.

Choose an existing compatible Python and verify its executable/version locally. Relay uses the standard library; scientific dependencies are a separate project-scoped reconstruction step. Do not copy ARM64 Linux site-packages into Windows.

```powershell
Get-Command pwsh, python, codex -ErrorAction SilentlyContinue
$PSVersionTable
# Set this from a discovered existing executable, not from an assumed path:
$Python = (Get-Command python -CommandType Application).Source
& $Python --version
```

The preferred root is `E:\GENESIS-RELAY` only when E: exists. If it does not, explicitly supply another root. The receiver does not silently relocate an existing project. Use an authorized private file transfer, removable storage or the sender's authenticated local download route to place the capsule in `incoming\`. A download on the sender is not a Windows receipt.

Verify the archive's external SHA-256 against a retained sender reference:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\GENESIS-RELAY\incoming\CAPSULE.zip'
```

Hashes prove agreement with that reference; they do not authenticate the person who supplied both files.

## Inspect and plan

Run these commands from the intact trusted Relay distribution:

```powershell
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Inspect `
  -Python $Python -Capsule 'E:\GENESIS-RELAY\incoming\CAPSULE.zip'

pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Plan `
  -Python $Python -Capsule 'E:\GENESIS-RELAY\incoming\CAPSULE.zip' `
  -Root 'E:\GENESIS-RELAY' -Route NATIVE_WINDOWS_X64
```

Inspect verifies the versioned capsule, member set, sizes and hashes and reports content/completeness. It does not run project code, launch Codex, start services or install dependencies. Plan reports the selected route, new workspace, destination tool observations, storage requirements, source dependency references, filename mappings and blocked prerequisites. A source package version is not a current Windows observation. Alternative selected interpreter versions remain unverified until explicitly probed.

## Native Windows x64

```powershell
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Restore `
  -Python $Python -Capsule 'E:\GENESIS-RELAY\incoming\CAPSULE.zip' `
  -Root 'E:\GENESIS-RELAY' -Route NATIVE_WINDOWS_X64 -Apply
```

This materializes a new working copy on an actual Windows x64 process. The immutable capsule copy remains separate. `RESTORED` proves materialization, not an installed scientific environment or a working laboratory. The generic receiver never executes capsule scripts automatically.

The current Science Lab source uses `fcntl`, `resource`, POSIX process groups, shell launchers and Linux service assumptions. The trusted laboratory adapter deliberately blocks a native-Windows scientific-success claim until a focused native service/worker adapter is implemented and actually tested. Scientific dependency recipes and archived source numerical tolerances are inputs to that work. Do not mark native Windows READY from Linux-only tests or WSL.

Windows-incompatible logical filenames, case collisions, reserved names, alternate-data-stream forms, trailing dots/spaces and long paths are visible in the plan. Their exact bytes remain in the immutable object store; the working copy uses inert hashed mappings rather than silently discarding or interpreting those names. Symlinks remain descriptors rather than automatically active links. Original logical paths remain in FILE-MANIFEST and PATH-MAPPING.

## WSL Linux x64

WSL is a separate route and must already exist. The wrapper does not install a distribution. Choose an actual existing distribution explicitly and ensure it has a compatible Python:

```powershell
wsl --list --verbose
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Plan `
  -Capsule 'E:\GENESIS-RELAY\incoming\CAPSULE.zip' `
  -Root 'E:\GENESIS-RELAY' -Route WSL_LINUX_X64 -WslDistribution 'EXISTING-DISTRIBUTION'
```

The wrapper converts explicit Windows paths using that distribution's `wslpath`, then invokes the portable receiver inside WSL. It uses the trusted Relay source tree through an explicit isolated bootstrap, or an existing installed Relay module. Linux x64 and a Microsoft WSL kernel are checked independently. If Relay/Python/dependencies are missing, receipt/plan prerequisites remain blocked; there is no silent installation or native-success substitution.

After reviewing the plan, repeat with `-Operation Restore -Apply`. Reconstruct scientific dependencies using the selected WSL environment, then invoke the explicit trusted scientific adapter and acceptance suite. The current sender has not executed this route. A future WSL pass must remain `WINDOWS_WSL_VERIFIED`, not `WINDOWS_NATIVE_VERIFIED`.

## Layout and receipts

The receiver uses:

```text
ROOT/incoming/                     operator-managed transport inputs
ROOT/capsules/CAPSULE_ID/           immutable ZIP and source metadata
ROOT/projects/PROJECT/CAPSULE_ID/   mutable destination working copy
ROOT/receipts/CAPSULE_ID.json       checkpointed receipt and failures
ROOT/outgoing/                     explicitly generated return capsules
```

Interrupted matching transfers resume only after checking the existing prefix. Reconstruction resumes only from Relay-owned markers. A matching duplicate receipt never overwrites subsequent work. Unrelated existing project directories are refused. The destination's source-evidence copy is never adapted; project-local credentials are regenerated by the explicit application adapter.

Inside the working copy, `AGENTS.md` is newly generated destination guidance, `_relay/source-guidance/` retains source instructions without activating them. `AGENTS.source.md` is a convenience copy only when that name was free; an existing source file with that name is preserved unchanged. Knowledge, source environment records and Git bundles are copied inertly under `_relay/`. Existing global guidance and overrides still apply. Imported source guidance does not override them.

## Verify, open and explicitly launch the installed Codex

Use the actual receipt path returned by Restore:

```powershell
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Verify -Python $Python -Receipt $Receipt
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Open -Python $Python -Receipt $Receipt
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation LaunchCodex -Python $Python -Receipt $Receipt -Apply
```

Verify checks receipt/capsule integrity, the adaptation baseline and SQLite integrity. It does not certify scientific computations. Open uses the native folder opener. LaunchCodex is explicit, locates the already installed CLI and invokes it in the restored workspace with an argument array. It does not install/update Codex, replace authentication or modify unrelated MCP/global settings. No actual Windows Codex session has been run during this sender mission.

The first receiving Codex should read delivered START-HERE and destination guidance, identify its actual interpreter and one supported experiment, execute a bounded acceptance task and write a new handoff with evidence. See WINDOWS-NEXT-STEPS.md for a concrete scope.

## Receiver-owned names

Source entries named `_relay`, `.relay-return-history`, `.relay-reconstruction.json` or receiver temporary-object suffixes are retained under an explicit inert source-tree mapping. Source AGENTS/override files and an original root START-HERE are archived as source guidance before destination guidance is generated. Existing AGENTS.source.md user content is never replaced. Original file bytes remain in the immutable capsule and at the mapped working-copy location. Windows and WSL plans conservatively apply Windows-compatible filename/case handling; mappings may require focused project adaptation.

## Receiver human interface

After trusted Relay installation, the same local interface can operate from the retained receiver files without a phone connection. Use the actual `project_path` returned in the receipt; do not invent a source path. From the trusted receiver environment:

```powershell
& $Python -I -m genesis_relay.ui start --state-dir 'E:\GENESIS-RELAY' --source $ReceiptProjectPath
& $Python -I -m genesis_relay.ui access --state-dir 'E:\GENESIS-RELAY'
```

Run the access helper in an operator terminal. Startup prints the actual unused loopback URL; no fixed port or successful Windows browser session is presumed. The interface reads retained `capsules/CAPSULE_ID/capsule.zip` and `receipts/` under that state root. It distinguishes received, restored, tested and ready; a historical READY milestone with a later failed check is not current readiness. Native Windows execution/browser acceptance remains NOT_RUN until performed on the receiving workstation.
