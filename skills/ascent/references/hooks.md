# Document refinement hook

Read this when installing, configuring, or troubleshooting the optional hook.
The implementation is [scripts/ascent_hook.py](../scripts/ascent_hook.py), requiring Python 3.11+ with no third-party packages.
It accepts the command-hook contracts of [Codex](https://learn.chatgpt.com/docs/hooks) and [Claude Code](https://code.claude.com/docs/en/hooks).

## Behavior and scope

The hook reads paired events, recognizes only marked workspaces, and counts turns and subagent runs that changed selected documents.
It requests refinement at a set interval and never edits documents itself.

### Events and failures

Register the script for `UserPromptSubmit` and `Stop`, and for `SubagentStart` and `SubagentStop`.
The subagent events let the hook count edits that a background subagent makes after its parent's turn has ended.
It handles events as follows:

- **Input and output**: It reads one event JSON object from stdin; valid continuations are JSON on stdout.
- **Turn identifiers**: Both turn events must carry the same non-empty session and per-turn identifiers: `session_id` with `turn_id` for Codex or `prompt_id` for Claude Code.
  When both turn fields are supplied, a non-empty `turn_id` takes precedence.
  A missing or invalid identifier skips observation rather than guessing a turn from the transcript.
- **Subagent identifiers**: Both subagent events must carry the parent's `session_id` and the same non-empty `agent_id`.
  Their turn fields differ between hosts and are not used.
- **Failures**: Other events, malformed input, unavailable files, invalid state, lock timeouts, and plan mode fail open without requesting continuation.
  Subagent events never request continuation.
  Diagnostics go to stderr without copying the prompt, transcript, or file contents.

### Workspace recognition

The event's `cwd` must itself contain `.ascent.toml`, following the skill's [workspace policy](../SKILL.md#establish-the-workspace).
Recognition follows these rules:

- **No README fallback**: The hook does not recognize README declarations alone.
  The agent retains them as a supplemental entry path and points to the [transition procedure](integration.md#transition-from-readme-declarations) when the marker is missing.
- **Validation order**: The hook checks the marker, then validates its configuration before reading documents or accessing saved state.
  Invalid TOML, invalid UTF-8, an oversized or unreadable config, or a non-regular marker skips observation without changing saved state.
- **README role**: The hook does not require or read a README to identify the workspace.
  A README is still part of the agent workflow and is observed as a document when selected.
- **Session start**: Start the session in its marked workspace.
  A session started directly in an independent target is outside scope unless that target has its own marker.
- **Symbolic entries**: Different symbolic workspace entry paths share one counter through their resolved path.
- **Boundary**: The scope is coordination, not authentication or a sandbox boundary.

### Counting and requests

Each turn is observed as follows:

1. On `UserPromptSubmit`, snapshot selected Markdown documents.
1. On `Stop`, compare hashes, including added and removed files, and count one changed turn.
   Repeated events for the same turn are deduplicated; `stop_hook_active` skips the refinement continuation.
1. When the count reaches `--interval N` (default `5`), return one focused refinement request for the accumulated paths and reset the count.

A workspace's counter and pending paths are shared across sessions under an OS file lock.
The request treats every accumulated path as in scope, whichever session changed it, because refinement serves the workspace's records.
It lists removed documents separately, so that only the links and summaries still referring to them are checked.
Paths that are no longer selected are omitted.

The last dispatched request remains identifiable in state; dispatch does not prove the model performed refinement.
No separate model is invoked, and the script never edits project documents.
The continuation preserves the original task's scope and permissions and does not require a wrap-up or a separate refinement report.

The request points to the skill's guidance on maintaining knowledge and continuity and first asks to reassess applicable guidance, since refinement is record work.
It also asks the pass to find content that this guidance says not to record, such as readily queryable status, and replace or remove it.

### Subagent runs

A subagent emits `SubagentStart` and `SubagentStop` instead of turn events, and a background subagent can keep editing after its parent's `Stop`.
Without the subagent events, such edits fall into the next turn's baseline and are never counted.
Each subagent run is observed as follows:

1. On `SubagentStart`, snapshot selected documents for that `agent_id`; a repeated start keeps the first snapshot.
1. On the parent's `Stop`, unless its selection changed, a running subagent's snapshot moves to that `Stop`'s snapshot.
   The turn also counts the subagent's edits made before the turn's baseline, so each edit is counted once.
1. On `SubagentStop`, compare with that snapshot and add the changed paths to the pending set.
   If the parent's turn is still open, its `Stop` counts the run once together with that turn.
   Otherwise the run counts as one changed turn.
1. When a run brings the count to the interval, the request waits for the next `Stop` of an observed turn in the workspace.
   That `Stop` returns it even if its turn changed nothing.
   A block decision on `SubagentStop` would keep the subagent running instead of reaching the parent.

A turn handed a run's paths but ending without `Stop`, such as an interrupted one, passes the count on to the session's next turn.
A turn whose own selection changed still counts the runs handed to it.
A `SubagentStop` without a recorded start, a run whose selection changed, and an unchanged run are not counted.

## Selected documents and state

The hook observes a bounded set of documents and keeps only paths, hashes, and counters, outside the workspace.

### Selected documents

Default include patterns are `*.md`, `docs/**/*.md`, `records/**/*.md`, and `decisions/**/*.md`, relative to the workspace root.
These defaults deliberately omit other document locations, so that drafts, raw data, and unrelated folders neither count as changes nor stop observation.
List a workspace's own locations in its `.ascent.toml`, for example to include a folder that holds a root document's subdocuments:

```toml
[hook]
include = ["*.md", "design/**/*.md"]
exclude = ["design/**/facts.md", "design/**/recovered_*.local.md"]
```

Selection follows these rules:

- **Precedence**: A workspace's `hook.include` replaces the defaults and any `--include` options.
  Without it, repeated `--include PATTERN` options replace the defaults for that registration.
  Prefer the workspace list, because a registration applies to every workspace.
- **Patterns**: A single `*` stays within a path segment; `**` spans zero or more directories.
  Patterns must be relative and cannot contain parent traversal.
  Both lists take string patterns with the same syntax.
  An empty include list is invalid.
- **Exclusions**: `hook.exclude` subtracts matching paths from the effective include list before reading or hashing files.
  Omitting it or setting it to `[]` keeps the full include selection.
  Requests also filter previously queued paths, including deleted files, against the current selection.
- **Selection changes**: A turn or subagent run whose selection differs between its two events is not counted, because the snapshots would differ without any edit.
  This covers editing either marker list during a turn and registering the events with different `--include` options.
- **Skipped paths**: Hidden directories, `targets`, dependency directories, symbolic links, and agent instruction files (`AGENTS.md`, `CLAUDE.md`) are skipped regardless of patterns.
  The hook maintains project knowledge, not agent instruction policy.
- **Configuration**: The `.ascent.toml` file is configuration, not a refinement document; changes to it do not advance the counter.
- **Traversal**: Directories that cannot contain a match for the selected patterns are not traversed.
  An unavailable directory within the selected scope still invalidates the snapshot rather than being treated as deleted documents.

Document edits are an observation signal, not proof of which actor made them or whether useful knowledge exists.
Read-only research with no document edits does not advance the counter.

### Choosing a workspace list

A workspace list names the project records whose changes should prompt refinement.
This is a narrower question than which Markdown files the workspace holds or which ones a structure check covers.
Choose the list as follows:

- **Records**: Include the locations of the current state, history, decisions, and knowledge that the workspace maintains.
- **Preserved material**: Leave out folders that the README declares as preserved as received, and archived records kept as they were.
  A refinement request would invite rewriting them.
  Name by its path an index that the workspace maintains inside such a folder.
- **Other material**: Leave out deliverables, test inputs and outputs, and other documents that are not project records, even when they are Markdown.
- **Structure-check exclusions**: A document left out of a structure check is usually outside the list as well.
  The converse does not hold, since archived records can follow a document model yet stay out of refinement.
- **Generated neighbors**: When authored records share a folder with generated Markdown, include the record location and exclude the generated names.
- **Keeping it current**: When work adds a record location to a workspace that lists `hook.include`, add it to the list in the same change.
  Documents in an unlisted location are not observed.

### Saved state

Only path names and SHA-256 hashes are retained, together with counters, turn, session, and subagent identifiers, and request metadata.
There is no transcript collection, network call, or stored document content.
State is stored and limited as follows:

- **Location**: State defaults to `$XDG_STATE_HOME/ascent` or `~/.local/state/ascent` on POSIX, and `%LOCALAPPDATA%/Ascent/state` on Windows.
  `--state-dir PATH` overrides it and must remain outside the workspace.
- **Separation**: Each workspace worktree has its own state keyed by its canonical directory.
  Sessions reusing that directory share its pending paths.
- **Pruning**: Session and subagent snapshots older than 30 days and excess inactive entries are pruned; the workspace counter and pending set persist.
- **Size limits**: The observer refuses oversized snapshots (2 MiB per file, 16 MiB total, 2,000 selected files) rather than comparing a partial snapshot.

## Registration

Use four command registrations pointing to the same script in the selected host's hook configuration, for example:

```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}],
    "Stop": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}],
    "SubagentStart": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}],
    "SubagentStop": [{"hooks": [{"type": "command", "command": "python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --interval 5", "timeout": 10}]}]
  }
}
```

Apply the registrations as follows:

- **Merging**: Merge with existing registrations rather than replacing the user's hook file.
- **Interpreter**: Use an interpreter and quoted paths appropriate to the platform; `python3` is only an example.
- **Trust**: Codex requires native review/trust for new command definitions; registration does not grant it.
- **Subagent events**: The two subagent registrations can be left out, at the cost of missing edits by subagents that outlive their parent's turn.
- **Consistent options**: Change the interval and include arguments consistently on all events, then reapply the definitions and review changed commands.
  Without a workspace list, mismatched include arguments leave every turn uncounted; mismatched intervals are not detected.

When an installation manager registers hooks, declare the events through it and follow its conventions instead of editing the host configuration directly.

## Inspect local observation state

Run a manual diagnosis with the same interpreter, `--state-dir`, `--include`, and `--interval` options as the registered commands:

```bash
python3 /absolute/ascent/skills/ascent/scripts/ascent_hook.py --diagnose /absolute/workspace
```

This mode does not read event input, create state or lock files, change counters, or request continuation.
Its JSON reports whether the workspace marker and configuration are valid, the include and exclude patterns in effect, selected document paths, and the state location.
It also reports the accumulated count and pending paths, session counts, and the last dispatched request.
It includes no document contents, hashes, prompts, or transcript data.

The response's `status` and `stage` fields are read as follows:

- **Success**: `status: "ok"` means local inspection succeeded, including when no saved state exists; it does not prove host registration or callback delivery.
- **No marker**: `status: "not-ascent"` with `stage: "marker"` means the directory has no workspace marker.
- **Invalid marker or configuration**: An invalid marker type reports `status: "error"` with `stage: "marker"`.
  Invalid or unreadable contents report `stage: "config"` and include the resolved workspace path.
- **Inspection failures**: Inspection failures return `status: "error"`, the failing stage and exception type, and exit status 1.
  Ordinary event handling retains its fail-open behavior.
- **Invalid options**: Invalid diagnostic arguments use the same error response with `stage: "options"`, including argument-parsing failures.

`awaiting_stop` counts saved unhandled snapshots and can include interrupted sessions, so it is not a count of currently running agents.
`awaiting_subagent_stop` likewise counts saved subagent snapshots, including those of subagents that never reached `SubagentStop`.
Supply the options actually used by the host: the diagnostic reports the requested settings and does not detect disagreement between two registrations.

## Checks and limitations

Tests exercise the script with isolated workspaces and event payloads, including count persistence, repeated events, target exclusion, concurrent sessions, and malformed state.
These establish script behavior, not live host callback delivery or the quality of the model's resulting document edits.
Verify delivery of a matching `UserPromptSubmit` and `Stop` pair, and of a `SubagentStart` and `SubagentStop` pair when registered, in the installed host before relying on the cadence.
A new or untrusted command can be skipped by the host, so verify every registration before relying on the cadence.

The hook has these further limitations:

- **Interrupted turns**: An interrupted or failed turn that never emits `Stop` is not counted; the next prompt takes a new baseline.
- **Subagent scope**: A subagent run also captures edits that others make while it runs.
  A subagent working in another directory, such as a separate worktree, is outside its parent's workspace.
- **Unrecorded knowledge**: The hook observes changes to existing project records, so it cannot recover knowledge that was never written down.
- **Native Windows**: Native Windows behavior requires Windows execution checks; the implementation uses platform-specific standard-library locks.
