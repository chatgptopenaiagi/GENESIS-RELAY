# Open Relay and try a complete small project

The bundled demonstration contains invented observations (2, 4 and 6), a Python script, a small SQLite database, saved results, acceptance checks and continuation instructions. It needs no account, AI API or scientific packages. Its expected mean is 4.

1. Extract the release for your operating system and architecture. Windows x64 supplies `Genesis-Relay.exe` with its runtime. Linux x86_64 supplies `Genesis-Relay`; the ARM64 archive supplies a Python launcher named `relay` and requires an existing Python 3.10 or newer. Keep each extracted folder intact.
2. In an operator terminal run `Genesis-Relay.exe ui start` and `Genesis-Relay.exe ui access` on Windows, or `./relay ui start` and `./relay ui access` with the Linux launcher. Open the actual local URL printed by startup and sign in with the terminal-only login.
3. In **Send my laboratory**, review scope and create a full capsule. In **Receive and continue**, inspect it, plan reconstruction, restore a separate copy, then run demo acceptance. Read **Engineering letter**, **Verification results** and **History** to see what those stages prove. In **Return improvements**, the explicit demo improvement action adds a harmless documented note and creates a return capsule.

Startup creates the owned demo only when no source is configured. It does not scan the device, install project dependencies or open public ports. Select your own project explicitly with `ui start --source /absolute/project`. Use a separate `--state-dir` for independent projects. Stop the current owned UI first before switching its source.

## The same demonstration from a terminal

Replace `relay` below with your extracted executable or installed console command. Choose new directories you own, outside each source root.

```text
relay --state-dir STATE demo create --root SOURCE
relay --state-dir STATE demo export --root SOURCE --output DEMO.zip
relay inspect DEMO.zip --summary
relay demo restore DEMO.zip --destination RECEIVER
relay demo accept ACTUAL_RECEIPT_PATH
relay demo return ACTUAL_RECEIPT_PATH --output RETURN.zip
relay demo reconcile RETURN.zip --project SOURCE
```

Restore prints its actual receipt path. The trusted demo acceptance checks the known demo rather than granting arbitrary capsule code execution. The reconcile demo exercises selected application, duplicate protection, conflict detection and rollback; read its result rather than assuming every returned file was merged.

The unchanged capsule, source manifest, destination receipt, new acceptance result and return letter have separate identities. They travel without this chat or the sender's credentials. A fresh receiving engineer should read effective AGENTS and START-HERE, identify the actual runtime, repeat one bounded calculation and write a new handoff.

Read INSTALL-WINDOWS.md, INSTALL-LINUX.md and KNOWN-LIMITATIONS.md before applying Relay to real projects. Relay installation can work without an online package download while reconstruction of another project may still require destination dependencies.
