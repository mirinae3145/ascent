# Ascent

Ascent is a workspace workflow for maintaining knowledge, decisions, and coordination toward a shared objective across independently managed repositories and other work targets.
A workspace is a project context, not a replacement for its targets' own contents or history.

Ascent is designed around workspaces that are ordinary directories by default.
Project coordination records generally have less need for version control than code, so this default favors fast iteration with an agent.
Connect codebases as independently versioned targets.
A workspace may itself be a repository when its purpose calls for versioned records or collaboration through Git.

## Start

Install [the Ascent skill](skills/ascent/SKILL.md) with your agent's skill installer, or place that directory in its supported skill location.
The skill is self-contained and does not require AEM, a particular agent product, or a research workflow.
Ask the agent to create an Ascent workspace for an objective, resume an existing workspace, or reconcile its project documents.
The skill also applies to ordinary work started in a directory containing `.ascent.toml`, including work confined to one linked target.
An existing workspace explicitly identified in its README remains a supplemental agent entry path; if its marker is missing, the skill points to the transition procedure.
When replacing an existing workspace policy, follow [the integration guide](skills/ascent/references/integration.md) to preserve its entry path and environment-specific requirements.

An existing folder becomes an Ascent workspace by adding an empty `.ascent.toml` file at its root.
The file is the explicit workspace marker and reserves a TOML configuration location for future settings; no setting keys are interpreted yet.
See the skill's [workspace policy](skills/ascent/SKILL.md#establish-the-workspace) for identity, links, and configuration rules.

Keep the objective, target relationships, and links to current work records reachable from the README.
Marker-based identification does not depend on its wording or formatting.
Use the existing layout; a small workspace can keep current state, history, and consequential decisions in separate sections of one file.
The skill defines their responsibilities and how they connect without requiring a fixed folder template.

## Optional document refinement hook

[The Codex and Claude Code hook](skills/ascent/references/hooks.md) detects changes to selected project documents and requests one focused refinement pass every N changed turns.
The default is five; it is configurable.
It uses the same model already working on the task and preserves existing permissions.
No additional model, service, or network dependency is required.

The hook recognizes `.ascent.toml` in the event's current directory and validates its TOML before observation.
It supports a symbolic workspace entry, skips independent targets and symbolic document links, and stores file hashes and a workspace counter outside the workspace.
It never edits project documents itself.
Read the hook guide for document scope, registration, native trust, and limitations before enabling it.
An [AEM catalog fragment](examples/aem.toml) is provided as an optional integration; AEM is not part of the Ascent definition.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and implementation boundaries.
The implementation uses Python 3.11 or later and the standard library.
This repository was created with AI assistance; review the skill and hook before using them.
