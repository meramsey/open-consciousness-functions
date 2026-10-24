# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Report them
privately by opening a GitHub security advisory on the repository, or by
contacting the maintainers listed in `GOVERNANCE.md`.

Include:

- affected file(s) or command(s);
- a minimal reproduction;
- suggested fix if you have one.

You will receive an acknowledgment within 14 days.

## Scope

- `scripts/` Python code and its dependencies.
- CI workflow definitions.
- Generated documents and indexes are derived data; report schema or
  generator flaws through the same channel.

## Safety notice

This project never claims health, medical, psychological, or paranormal
effects. If any material in this repository reads as a medical or emergency
instruction substitute, report it: it is a defect.

## Supported versions

Security fixes are applied to the current `main` branch. There are no LTS
releases yet.

## Dependency review

Pull requests are checked for newly introduced high/critical vulnerabilities in
runtime, development and unknown dependency scopes. The review uses read-only
permissions, immutable action references and no advisory allowlists. It does not
assert license clearance or dismiss existing alerts.

See [dependency security and parser exposure](docs/DEPENDENCY_SECURITY.md).
Private alert inventories belong under ignored `.ocf-work/security/`, not in
public issues. Never paste credentials into a report; existing GitHub CLI
authentication should be used without changing credential storage.
