# Synthetic laboratory architecture

experiment.py computes an arithmetic mean from a UTF-8 CSV using the Python standard library. private/observations.sqlite3 records observations with stable sample IDs and immutable source-run metadata. results/source-run/report.json and report.md are historical outputs. Destination acceptance records a fresh run, capsule digest, actual platform/runtime and a separate report.

No original application installation, Sentinel, paid model API or foreign binaries are needed. Relay inspection and restoration do not execute experiment.py. Trusted demonstration acceptance verifies the delivered script against Relay's bundled known script and computes with the same trusted implementation. An explicit Python invocation can independently execute the restored standalone script.
