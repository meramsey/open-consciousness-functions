# Independent continuous production supervision

Long production work must not be a tool child in an OpenCode location/service.
The Linux deployment templates in `deploy/systemd/` run the existing worker in
its own systemd user cgroup. They do not introduce another rendering engine.
The standalone entry point is `scripts/production_supervisor.py`.
Its private JSON configuration selects the existing worker and reconciler as
argument arrays, not shell commands. Private paths/assets/configurations are
not committed. Systemd unit names must be explicitly scoped `ocf-*.service`.

The owner emits a separate machine heartbeat every 10 seconds, including exact
controller/worker PID, start ticks, boot identity, command digest and cgroup.
The existing batch status remains the sole queue/progress authority. A heartbeat
is independent of function completion. Process IO and receipt/log changes are
progress evidence; CPU utilization alone is never health proof.

An independently supervised oneshot watchdog runs nominally every 20 seconds.
Its unit permits twelve starts per minute, so the ordinary timer cadence and
bounded five-second watchdog-process restarts do not trip the unit start limit.
This scheduling headroom does not increase production recovery budgets.
The default heartbeat deadline is 75 seconds, long-job diagnosis begins from
actual progress receipts, and no-progress timeout is 90 minutes. Reconciliation
has its own 10-minute deadline; systemd transitions are bounded separately.
These thresholds distinguish a dead process from slow but legitimate work.
Before the first heartbeat, a live owner in the configured cgroup receives a
durable, identity-bound startup grace of 75 seconds. Timer checks do not reset its
deadline; expiry uses ordinary bounded recovery. This prevents an immediately
firing calendar timer from killing a newly started interpreter while preserving
dead-process, wrong-cgroup and frozen-input protections.
No `WatchdogSec` is configured: this implementation does not claim sd_notify.

Systemd restarts failures after 30 seconds and cleans the entire dedicated
cgroup before restart. The watchdog also detects successful owner exit with an
unfinished queue. Recovery is bounded to three attempts per job and ten per day.
An exclusive controller lease, watchdog lease and the existing worker's output
reservations prevent duplicate owners/publication. PID reuse does not authorize
signalling an unrelated process.

The configured reconciler must verify final receipts, hashes and frozen input
identity before returning `safe_to_run`. Missing/corrupt finals block dispatch.
Partial stages are retained. Verified finals are reused, never regenerated.
Incomplete operations resume only after stale ownership is disproved. Native
speech-cache entries remain subject to the existing hash/identity checks.

Disk reserves stop dispatch; recovery can continue after capacity returns.
An explicit operator pause is persistent and is not overridden by the timer.
Use `pause --config FILE` for an emergency stop and `resume --config FILE` for
safe restart. `systemctl stop` alone is not a durable pause: an unfinished,
authorized job is eligible for watchdog recovery. `status --config FILE` reads
health records without starting work.

Engineering escalation uses a configured authenticated local bridge, one
write-ahead event reservation per failure identity and bounded recovery budget.
Ambiguous/denied delivery is recorded, never blindly resent. Acceptance is not
execution: a real acknowledgement/checkpoint must prove agent re-entry. If no
verified API/channel exists, machine recovery remains operational and the
limitation must be reported. Notifications are for persistent failures, integrity
issues, exhausted budgets and terminal completion, not routine cache/progress.

With user linger enabled, the dedicated service can survive interactive logout
independently of OpenCode. Linger is not protection against power loss/reboot,
and an explicit safe pause/shutdown still matters. Validate generated units with
`systemd-analyze --user verify`; exercise crashes only with disposable synthetic
workers. Never kill a real render to demonstrate resilience.
