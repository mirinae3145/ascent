# Publish Git workspace records

The [publisher](../scripts/publish.py) previews outgoing commits, publishes an authorized revision, and runs the workspace's checks in CI.
Run it from the marked root of a Git worktree.
Use the workspace's contributor contract to find its destination, publication points, review route, and required approvals.

## Configure the workspace

Commit the settings through the workspace's review route before using the publisher.
The tracked `.ascent.toml` supplies two inputs for direct publication.

- **Eligible paths** use workspace-relative patterns with `/` separators.
  A single `*` matches within one segment and `**` matches zero or more segments.
  Direct publication requires a nonempty allowance.
  Changes to the marker itself go through review, even if a pattern covers it.
- **Repository checks** run as a command and separate arguments from the workspace root without shell expansion.
  Put all checks required for publication in this entry point, including any comparison with an external original that the repository maintains.
  Configure CI to run the publisher's `check` action on the checked-out revision.

For example, this workspace allows direct publication of records and decisions.

```toml
[publish]
allow = ["records/**", "decisions/**"]
check = ["python3", "tools/check_all.py"]
```

## Preview and publish

Give each concurrent writer its own worktree and commit the intended changes there.
Preview and push require a clean index and worktree, including nonignored untracked files in that worktree.
Use the installed script path and the destination named by the contract for both steps.

1. Run `python3 /path/to/ascent/scripts/publish.py preview origin main` to inspect the proposed publication.
   The preview fetches the destination and lists the outgoing commits and their touched paths.
   It checks each commit against its parents, including deletions, both names of a rename and changes that later commits undo.
   If histories have diverged, integrate the fetched revision according to the workspace contract and preview again.
1. When publication is authorized, run `python3 /path/to/ascent/scripts/publish.py push origin main`.
   The publisher repeats the preview, runs the configured check, and verifies the worktree is still clean at the checked revision.
   It advances the destination from the fetched revision to that exact descendant.
   If the check fails or another writer moves the destination, inspect the result and retry with the current history.

In CI, run `python3 /path/to/ascent/scripts/publish.py check` from the same checkout root.
This action reads the committed check command and returns failure if it fails, without contacting a remote.

## Refinement across sessions

The [document hook](hooks.md) tracks records within each worktree and shares the pending paths among sessions using that directory.
An integration during an observed turn can add changed records to the receiving worktree's queue.
An integration completed before the first snapshot forms part of the baseline.
The workspace can exclude generated documents from refinement while still allowing publication of those documents.
