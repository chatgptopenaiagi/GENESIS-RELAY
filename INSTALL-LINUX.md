# Install on Linux

Select the archive matching the actual machine architecture. Compare the downloaded file with SHA256SUMS.txt and RELEASE-MANIFEST.json. Use a new directory; do not overwrite another installation.

| Asset | Relay runtime | Qualification |
|---|---|---|
| `GENESIS-RELAY-0.1.0-linux-aarch64.tar.gz` | Python launcher and trusted source; existing Python 3.10+ required | Tested ARM64 scope is recorded in the release evidence. Arch under Android/Termux/proot is not an Android APK. |
| `GENESIS-RELAY-0.1.0-linux-x86_64.tar.gz` | Runtime-inclusive `Genesis-Relay` distribution | Native runner, libc baseline and extracted-artifact checks are recorded in the release evidence. |
| `genesis_relay-0.1.0-py3-none-any.whl` | Existing compatible Python | Scientific dependencies are separate from Relay installation. |

Extract the appropriate archive and keep its folder intact:

```bash
./relay --version
./relay ui start
./relay ui access
```

Where the archive provides `Genesis-Relay`, `./Genesis-Relay` is the equivalent runtime-inclusive entry point. The ARM64 wrapper invokes Python and is not a standalone compiled binary. Set its documented interpreter override when using a non-default existing Python. Read the included package metadata for exact interpreter/libc requirements; an architecture label alone is not a compatibility guarantee.

Startup selects an unused loopback port and prints the actual URL. The access helper displays generated credentials only in an operator terminal. Open that URL in your browser and follow QUICKSTART.md. Without `--source`, Relay prepares an owned synthetic demo; it does not scan the device.

```bash
./relay --state-dir /absolute/private/relay-state ui start --source /absolute/project
./relay --state-dir /absolute/private/relay-state ui status
./relay --state-dir /absolute/private/relay-state ui stop
```

Use separate state for unrelated projects. Stop an owned UI before changing its source. Source and state must be separate; do not export a directory containing Relay's changing state. Keep management loopback-only and private capsules out of public hosting.

## Wheel installation

Use an existing Python with venv/pip support, keeping build/runtime dependencies out of scientific environments:

```bash
python3 -m venv /absolute/new/relay-venv
/absolute/new/relay-venv/bin/python -m pip install --no-index --no-deps /absolute/download/genesis_relay-0.1.0-py3-none-any.whl
/absolute/new/relay-venv/bin/relay --version
/absolute/new/relay-venv/bin/relay ui start
```

The archive core and lightweight demo use the standard library. Installing Relay does not install a project's scientific engines or certify its workflows. Offline Relay installation is different from offline reconstruction of an arbitrary project.

## Source, recovery and removal

The source archive includes theory, tests, UI, scripts and synthetic fixtures. Build commands and actual supported/tested Python versions appear in the release evidence. Run tests from isolated environments; do not point public tests at personal research.

`relay --state-dir STATE recover` previews interrupted source-service restart checkpoints. Review before adding `--apply`; helpers and process ownership are revalidated. Generic multi-file capture has narrower consistency guarantees than a project-specific checkpoint.

Stop the owned UI, then remove only the installation or uninstall the wheel from its isolated venv. State, capsules, projects and receipts remain separate and are not deleted automatically. Never remove a folder merely because its name resembles a previous temporary directory; verify Relay ownership first.
