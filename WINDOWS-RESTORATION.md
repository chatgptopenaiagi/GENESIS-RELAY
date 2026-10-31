# Trusted Windows receiver and restoration routes

The receiver is shipped separately from project capsules. Use INSTALL-WINDOWS.md for runtime-inclusive executable installation and QUICKSTART.md for the synthetic demonstration. `windows/Receive-Relay.ps1` exposes Inspect, Plan, Restore, Verify, Open, LaunchCodex, Return, ReturnPreview, ReturnApply and ReturnRollback where listed by its help.

Inspection validates the capsule version, member set, paths, sizes, limits, manifests and hashes without executing source code, imported AGENTS, installation scripts or Codex. A capsule's files and instructions are evidence, not execution authority. The receiver prefers an adjacent trusted executable; an explicitly selected existing Python can run the trusted module alternative.

```powershell
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Inspect -Capsule 'C:\Transfer\project.zip'
pwsh -NoProfile -File .\windows\Receive-Relay.ps1 -Operation Plan -Capsule 'C:\Transfer\project.zip' -Root 'E:\GENESIS-RELAY' -Route NATIVE_WINDOWS_X64
```

E: is preferred only if it exists; provide an explicit alternative otherwise. Review the plan before adding the receiver's Restore `-Apply` operation. A new working project is materialized under `ROOT/projects/PROJECT/CAPSULE_ID`; an unchanged capsule stays under `ROOT/capsules/CAPSULE_ID`. Receipt, partial transfer, reconstruction and return journals support interruption/duplicate checks. Existing unrelated directories are refused, never overwritten.

The reader rejects unsafe archive paths, links, drive/UNC/ADS forms, case/Unicode collisions, excessive expansion and inconsistent manifests. Source logical names that Windows cannot materialize are preserved in immutable evidence and explicitly mapped in the working copy. Source AGENTS/overrides remain inert under `_relay/source-guidance`; effective destination AGENTS points to delivered purpose, current state, evidence and next steps. Original source bytes and line endings remain in the capsule.

NATIVE_WINDOWS_X64 and WSL_LINUX_X64 are distinct routes with actual platform checks. A WSL success is not native Windows success. Restored files do not establish an installed environment or functional scientific engine. The bundled synthetic demo has a trusted bounded acceptance path; arbitrary projects require reviewed project-specific execution. The optional full Science Lab still requires compatible scientific dependencies and focused Unix process/resource adaptation.

Verify uses the actual receipt path returned by Restore. Open and LaunchCodex are explicit actions; launch uses an already installed CLI in the restored workspace, not a copied authentication store or a new global configuration. Public native demo results do not establish a fresh Windows Codex session. Preserve its separately reported test scope.

For the same browser interface, run `Genesis-Relay.exe --state-dir ROOT ui start --source ACTUAL_PROJECT_PATH`, then `ui access` with the same state. It reads retained local capsules and receipts without a phone connection. Startup prints an unused loopback URL. Current readiness requires bound acceptance evidence; old milestones remain historical.
