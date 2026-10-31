# Synthetic continuation example

This small project contains invented data only. It has no credentials, scientific installation or connection to the operator's real laboratory.

From a trusted Relay installation, choose new private paths for state and output:

```bash
relay --state-dir /absolute/private/example-state plan ./examples/sample-project
relay --state-dir /absolute/private/example-state export ./examples/sample-project --output /absolute/private/synthetic.zip --no-quiesce
relay verify /absolute/private/synthetic.zip --summary
relay restore /absolute/private/synthetic.zip --destination /absolute/new/example-receiver --route LOCAL_LINUX
```

The final command plans without applying. On an actual Windows workstation use the trusted PowerShell receiver and an explicit Windows route. A successful archive inspection does not certify a scientific capability or start this project's code.
