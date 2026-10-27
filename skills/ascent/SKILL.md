---
name: ascent
description: >-
  Create, enter, resume, or maintain an Ascent workspace connecting independent
  work targets. Use for ordinary tasks, including work confined to one linked
  target, when the starting or explicitly selected workspace directory contains
  .ascent.toml. Also use when that directory's README explicitly identifies it
  as an Ascent workspace; guide migration if the marker is missing. Explicit
  workspace creation or migration requests apply before a marker exists.
  Mentions in documentation or examples alone do not trigger this skill.
---

# Ascent

An Ascent workspace coordinates work toward a shared objective across independently managed repositories and other targets.
It owns project-level knowledge, consequential decisions and their rationale, cross-target relationships, and coordination state.
Targets keep their own contents, guidance, history, and lifecycle; linking one does not absorb it into the workspace or grant permission to change it.

## Establish the workspace

Apply this workflow to ordinary tasks started in a workspace, including work confined to one linked target, as well as explicit workspace creation, entry, resumption, or maintenance requests.
Identify a workspace by a regular `.ascent.toml` file directly in the selected directory.
An empty file is valid; contents must be UTF-8 TOML within 2 MiB.
No setting keys are interpreted yet; hook options remain command-line arguments.
Resolve the selected directory's symbolic links before checking, so a linked directory and its original path identify the same workspace.
The marker file itself must not be a symbolic link or directory.
Do not search parent directories or infer marker-based identity from directory names, target links, Git, or an installation manager.
An invalid or unreadable configuration is a workspace error, not evidence that the directory is an ordinary non-workspace.

For an existing workspace without `.ascent.toml`, retain its README's explicit identification of the directory as an Ascent workspace as a supplemental entry path.
An explicit request to enter or resume an existing unmarked workspace also uses this path.
Read and point the user to [the transition procedure](references/integration.md#transition-from-readme-declarations), and use the existing README and linked records for the authorized task.
This entry path does not activate the hook or authorize creating the marker during read-only work.
Descriptions of Ascent and declarations quoted as examples do not identify the containing directory as a workspace.

Start from the identified workspace's README.
The README explains the objective and scope, the targets' roles and relationships, and where current knowledge and work records live.
No fixed declaration sentence or Markdown format is required.
A subworkspace used as a direct session entry point also has its own `.ascent.toml` and links to its parent workspace in its README.
Read that parent's README for the shared context when working in the subworkspace.

Use the existing layout.
A common arrangement has a README and `targets/` links to independent work targets, with project records in README sections until separate documents are useful.
Do not create empty folders or impose a fixed record schema.
Create new workspaces as ordinary directories by default; Git initialization is optional.
Project coordination records generally have less need for version control than code, and this default favors fast iteration with an agent.
Connect codebases as independently versioned targets.
A workspace may itself be a repository when its purpose calls for versioned records or collaboration through Git; preserve that choice for existing workspaces.
If the user has a workspace manager, follow its existing discovery and installation conventions; Ascent does not require one.
When migrating an existing workspace policy to this skill, read [the integration guide](references/integration.md) for the entry path and responsibility split.

## Enter or resume work

Read the README and follow the relevant current knowledge and work records before acting, including work confined to one target.
Recover confirmed findings, applicable decisions, open questions, next actions, and source locations from those records rather than relying on an earlier chat.
A recorded proposal or unfinished plan is not evidence of an applied change.
When a missing source or uncertain current condition could change the next action, inspect the necessary original material.

Resolve each target's actual location through the workspace's links and follow the target's applicable guidance.
Keep target-specific commands, code, tests, reusable usage guidance, and source history in the responsible target.
Keep project-wide objectives, cross-target reasoning, and coordination in the workspace, with links to target-owned material.
A broken link is an unresolved location or access issue, not a reason to reconstruct the target from a summary.

## Maintain knowledge and continuity

When authorized work produces knowledge needed later, consequential decisions, or meaningful state changes, update the relevant existing documents before concluding or changing phase.
Keep reusable project knowledge canonical, and distinguish these record roles:

- **Current state** describes presently confirmed facts, active work, unresolved questions, next actions, and material validation limits. Consolidate it as conditions change and link to supporting history and applicable decisions.
- **History** preserves dated work, validation, and observations with the conditions and limitations needed to interpret them. Keep original observations identifiable and make later corrections or follow-up findings explicit. Validation records retain the behaviors checked, results, limitations, and necessary reproduction conditions.
- **Consequential decisions** retain what was chosen and why, with material alternatives or trade-offs, scope, constraints, and reconsideration conditions when relevant. Make the current status and any superseding decision explicit while preserving the earlier rationale.

These roles may be separate sections in one file or separate documents.
Link their canonical locations instead of repeating detailed accounts in each one.
Keep knowledge and necessary evidence, while allowing current-state prose to be rewritten as the current account rather than becoming an append-only changelog.
Preserving history does not require copying full transcripts or keeping all historical detail in current state.
For example, when a later check overturns an earlier result, update current state with the new conclusion and its limits, preserve the earlier observation with its original conditions in history, and link the new evidence.
If a consequential decision depended on that result, mark whether it still applies or has been superseded; do not erase its original rationale.

Keep confirmed findings, assumptions, proposals, and open questions distinguishable.
Retain temporary failures, device paths, installation details, or execution history only where they affect interpretation, reproduction, or continuation; scope such observations to the device and conditions actually checked.
Keep general target requirements in target documentation and project-specific observations in the workspace.
Store maintained implementation and analysis code in the responsible versioned target; result records link to the code revision and retained inputs instead of becoming a parallel source archive.

Keep records reachable from the README so another session can continue without the original conversation.
Update existing content first, adding documents only when their role warrants it.
If the records already capture the relevant knowledge accurately and coherently, finish without rewriting them or adding a maintenance report.
Document maintenance follows the authorized task scope; read-only review does not authorize edits merely because continuity would benefit.

## Temporary departures from a baseline

When later work relies on an explicitly documented or agreed baseline, account for temporary departures that the agent makes or asks the user to make.
At the time of the change, identify its purpose and when it should end; use an established restoration procedure when available.
Before completing that work or handing it off, restore the affected conditions within the authorized scope, or request restoration and confirmation from the person who must perform it.
If subsequent work still needs the departure, agree on its continued use and restoration point instead of silently treating it as the new baseline.
Respect explicit exceptions to restoration and intervening user changes; do not blindly restore an earlier snapshot.

Confirm only the affected conditions, using direct evidence or the responsible person's report as appropriate, and distinguish those evidence sources.
Do not infer restoration from silence or the end of a session.
If restoration remains unconfirmed at closeout, ask about that known departure and retain only the unresolved condition and its implications for continuation.
Once resolved, remove it from current work records; retain history only under the recording criteria above.
This responsibility does not require routine reapproval of an unchanged baseline or speculation about unreported external changes; recheck when a known change, relevant observation, or established procedure warrants it.

## Optional refinement trigger

The workflow does not require automation.
When asked to configure or troubleshoot the bundled Codex and Claude Code document-refinement hook, read [the hook guide](references/hooks.md).
The hook supplies a bounded opportunity to apply the maintenance principles above; it does not grant permissions, conclude a task, or mandate a new report.
