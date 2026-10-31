# Your private project continuation interface

Relay is a local product for preserving a project and its documented story. Its capsule contains source evidence and may include private research. Its software distribution is a separate deliverable. No browser control publishes either one.

## Open the sender interface

In the current source checkout:

```bash
PYTHONPATH=/root/GENESIS-RELAY/src /root/GENESIS-SCIENCE-LAB/.venv/bin/python -m genesis_relay.ui start --state-dir /root/GENESIS-RELAY/private/state --source /root/GENESIS-SCIENCE-LAB --sentinel-root /root/GENESIS-SENTINEL
PYTHONPATH=/root/GENESIS-RELAY/src /root/GENESIS-SCIENCE-LAB/.venv/bin/python -m genesis_relay.ui access --state-dir /root/GENESIS-RELAY/private/state
```

The first command prints the actual local URL. The second requires an operator terminal and displays the destination-local Relay login. Credentials are not written to ordinary reports. Open the printed URL in the Vivo browser, sign in, and keep the Arch/Termux environment available. The current owned instance uses `http://127.0.0.1:8120/`; startup tries the requested port and its next 19 candidates without stopping an occupant.

The installed Python package provides the same UI module. On another machine, select that machine's private state and actual restored project paths; the phone's paths above are examples for this deployment, not installation requirements. A receiving UI can inspect its retained `capsules/<id>/capsule.zip` without the source machine or sender login.

## Explore the eight areas

1. **My projects** explains the selected project, its source location and progress. Open links appear only after process-identity and loopback HTTP observations for the original or reconstructed laboratory. Scientific correctness is a separate result.
2. **Send my laboratory** runs read-only discovery and planning before construction. The default is full continuation. **Create private capsule** is an explicit confirmed action using the trusted startup source; a browser cannot supply a different server filesystem root.
3. **What is inside this capsule?** shows archive identity, size, hash, completeness qualification, preserved run counts, dependency requirements and a searchable per-entry list. Exact files, transformed snapshots, dependency references, exclusions and unresolved entries remain distinct. A verified hash is not automatically a completeness pass or offline qualification.
4. **Receive and continue** inspects and plans without executing project code. An explicit restore action writes a new Relay-owned working directory under the configured receiving root and keeps immutable evidence separately. It does not install scientific dependencies or mark acceptance passed.
5. **Engineering letter** displays delivered purpose, intent, architecture, decisions, current state, problems and next steps as readable text. Claims remain tied to evidence in the capsule; hidden model thoughts are not claimed.
6. **Verification results** separates source integrity, persisted restoration state, new destination experiment reports and Windows status. An observed Linux result never promotes native Windows or WSL status. Failed and skipped checks remain visible.
7. **Return improvements** can create a private return capsule from the known receiver receipt and adaptation baseline, then download it. Preview, selected application and rollback are explicit receiver operations. Database snapshots never enter ordinary text merge. The browser does not accept arbitrary return destinations or deletion commands.
8. **Transfer history** shows actual local actions and destination receipts separately. Download observations record HTTP byte ranges and counts, not a destination receipt or successful continuation.

## Download privately and check what arrived

Click **Inspect and verify** on a known capsule, then **Download privately**. The route requires the Relay session. The server streams bytes in bounded chunks, supports resumable byte ranges, and rechecks the retained archive digest before sending. A changed archive must be verified again. A completed HTTP response is not a claim that a separate Windows workstation received or restored it.

Use the external checksum alongside the archive at the destination, then the trusted receiver's Inspect and Plan operations. Do not execute capsule-provided scripts or activate its source AGENTS file merely by inspecting it. The UI's receiver plan and restore buttons use a fixed owned destination root and never overwrite an unrelated project.

The Windows receiver and software artifacts are available through authenticated download buttons once those trusted distribution files exist. Take the trusted Relay distribution separately from a private capsule. Native Windows and WSL remain distinct routes. This deployment's browser tests do not claim native Windows or physical touchscreen execution.

## Return without overwriting newer work

Create a return only after reviewing its destination adaptation baseline and saved work. On the receiving machine the explicit PowerShell operation is:

```powershell
./Receive-Relay.ps1 -Operation Return -Receipt RECEIPT_PATH -Output RETURN_CAPSULE_PATH -Apply
./Receive-Relay.ps1 -Operation ReturnPreview -ReturnCapsule RETURN_CAPSULE_PATH -Project OWNED_SENDER_WORKING_COPY
```

Review conflicts before any selected apply operation. The implemented return protocol retains a journal and rollback material; duplicate imports do not reapply work. Keep database reconciliation separate. See RETURN-PROTOCOL.md for exact command arguments, expected decisions and limitations.

## Lifecycle and evidence

Use the same module with `status`, `stop` or `restart`. Stop checks the owned process command/start identity and refuses while a UI management job is active. No public listener, service tunnel, automatic boot survival or unrelated application control is created. Root/source choices come only from trusted terminal startup.

Isolated HTTP tests are in `tests/test_ui.py`. They cover authentication, Host/Origin/CSRF, private-path rejection, fixed dispatch, escaping, streaming ranges, tamper detection and logout. The explicit `--browser` mode uses an existing Firefox/geckodriver and tests the actual eight pages at a real 360-pixel viewport, with screenshots and a full authenticated download digest. It inspects an already-created capsule; it does not run a new source export automatically. Local screenshots and raw evidence are private operational outputs under `evidence/` and are not part of the public-ready Relay source distribution.
