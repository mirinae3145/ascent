# Document refinement hook

Read this when installing, configuring, or troubleshooting the optional hook.
The implementation is [scripts/ascent_hook.py](../scripts/ascent_hook.py), requiring Python 3.11+ with no third-party packages.
It accepts the command-hook contracts of [Codex](https://learn.chatgpt.com/docs/hooks) and [Claude Code](https://code.claude.com/docs/en/hooks).

## Behavior and scope

Register the script for both `UserPromptSubmit` and `Stop`.
It reads one event JSON object from stdin; valid continuations are JSON on stdout.
Both events must carry the same non-empty session and per-turn identifiers: `session_id` with `turn_id` for Codex or `prompt_id` for Claude Code.
When both turn fields are supplied, a non-empty `turn_id` takes precedence.
A missing or invalid identifier skips observation rather than guessing a turn from the transcript.
Other events, malformed input, unavailable files, invalid state, lock timeouts, and plan mode fail open without requesting continuation.
Diagnostics go to stderr without copying the prompt, transcript, or file contents.

The event's `cwd` must itself contain `README.md` with a standalone declaration near the beginning:

- `This directory is an Ascent workspace.` (case-insensitive)
- `이 디렉터리는 Ascent 워크스페이스입니다.` (existing Korean workspaces)

The check ignores quoted examples and fenced code.
It does not search parent folders or infer ownership from a `targets/` name.
Start the session in its declared workspace; a session started directly in an independent target is outside scope.
Paths are resolved for workspace identity so different symbolic entry paths share one counter.
The scope is coordination, not authentication or a sandbox boundary.

On `UserPromptSubmit`, snapshot selected Markdown documents.
On `Stop`, compare hashes, including added and removed files, and count one changed turn.
Repeated events for the same turn are deduplicated; `stop_hook_active` skips the refinement continuation.
A workspace's counter and pending paths are shared across sessions under an OS file lock.
When the count reaches `--interval N` (default `5`), return one focused refinement request for the accumulated paths and reset the count.
The last dispatched request remains identifiable in state; dispatch does not prove the model performed refinement.
No separate model is invoked, and the script never edits project documents.
The continuation preserves the original task's scope and permissions and does not require a wrap-up or a separate refinement report.

## Selected documents and state

Default include patterns are `*.md`, `docs/**/*.md`, `records/**/*.md`, and `decisions/**/*.md`, relative to the workspace root.
A single `*` stays within a path segment; `**` spans zero or more directories.
Repeat `--include PATTERN` to replace those defaults for a particular registration.
Patterns must be relative and cannot contain parent traversal.
Hidden directories, `targets`, dependency directories, symbolic links, and agent instruction files (`AGENTS.md`, `CLAUDE.md`) are skipped regardless of patterns.
The hook maintains project knowledge, not agent instruction policy.
These defaults deliberately omit other document locations; select additional locations when needed.
Document edits are an observation signal, not proof of which actor made them or whether useful knowledge exists.
Read-only research with no document edits does not advance the counter.

Only path names and SHA-256 hashes are retained, together with counters, turn/session identifiers, and request metadata.
There is no transcript collection, network call, or stored document content.
State defaults to `$XDG_STATE_HOME/ascent` or `~/.local/state/ascent` on POSIX, and `%LOCALAPPDATA%/Ascent/state` on Windows.
`--state-dir PATH` overrides it and must remain outside the workspace.
Workspaces have separate state files keyed by their canonical paths.
Session snapshots older than 30 days and excess inactive entries are pruned; the workspace counter and pending set persist.
The observer refuses oversized snapshots (2 MiB per file, 16 MiB total, 2,000 selected files) rather than comparing a partial snapshot.

## Registration

Use two command registrations pointing to the same script in the selected host's hook configuration, for example:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}]
  }
}
```

Merge with existing registrations rather than replacing the user's hook file.
Use an interpreter and quoted paths appropriate to the platform; `python3` is only an example.
Codex requires native review/trust for new command definitions; registration does not grant it.
For AEM, the repository's `examples/aem.toml` shows optional Codex declarations using a Git source; AEM skills do not accept external folder sources.
Bind the `ascent-python` runtime to the selected interpreter and explicitly apply the skill and both hook resources.
AEM owns installation instead of the skill editing native files itself.
Change the interval and include arguments consistently on both events, then reapply the definitions and review changed commands.

## Checks and limitations

Tests exercise the script with isolated workspaces and event payloads, including count persistence, repeated events, target exclusion, concurrent sessions, and malformed state.
These establish script behavior, not live host callback delivery or the quality of the model's resulting document edits.
Verify delivery of a matching `UserPromptSubmit` and `Stop` pair in the installed host before relying on the cadence.
An interrupted or failed turn that never emits `Stop` is not counted; the next prompt takes a new baseline.
The hook observes changes to existing project records, so it cannot recover knowledge that was never written down.
Native Windows behavior requires Windows execution checks; the implementation uses platform-specific standard-library locks.
A new or untrusted command can be skipped by the host, so verify both registrations before relying on the cadence.
