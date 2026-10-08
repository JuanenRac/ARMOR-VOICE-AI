# Changelog

All notable changes to this project are documented here.

## [0.2.2] - What used to go unsaid is now in the log

- **Audit file:** when a decision's line cannot be written, a warning says so (on stderr: stdout is the protocol of the gateway).
- **Confirmation secret:** when `ARMOR_VOICE_CONFIRM_SECRET` is not set and a random one is used, a warning says that the pending confirmations are lost when the process stops.


## [0.2.1]

- A GitHub Actions CI baseline (`.github/workflows/ci.yml`): validates the manifest, the version, CHANGELOG.md's heading, the seven README translations' structure and its own local Markdown links, then runs this project's real build/test through `tools/armor_project_tool.py build-test .` (vendored from ARMOR-COMMON, alongside `tools/armor_ci_validate.py` and `tools/_armor_readme_parity.py`, which do the manifest/docs checking).

## [0.2.0]

- Closed intent allow-list, service-signed single-use confirmation for arm and disarm, and a hash-only audit.
- 20 tests.
