# Integrate the workspace workflow

Read this when moving an existing workspace policy into the installed Ascent skill.
The workflow and optional document-refinement hook can be adopted separately.

## Make the skill the entry path

Install the skill through the environment's existing skill manager and confirm that a fresh agent session can locate and read it.
The skill's own discovery description covers ordinary work from a marked workspace, explicit workspace requests, and the supplemental README entry path for existing unmarked workspaces.
Verify those entry paths before retiring the old workflow; editing a discovery description alone does not establish that a host selects the skill.
After that verification, remove duplicated Ascent principles and entry rules from global instructions so the skill owns its activation and workflow.
Personal instructions may retain additional preferences and environment-specific usage without repeating the reusable Ascent workflow.
If the skill is unavailable or ordinary work does not select it, report that unresolved installation or discovery problem before declaring the transfer complete.

## Preserve the right responsibilities

Keep reusable workspace concepts and record-maintenance principles in the Ascent skill.
Keep instruction precedence, domain-specific guidance selection, personal workspace-location and installation preferences, and machine bindings in their existing personal or environment sources.
Keep project-specific scope and target relationships in the workspace, and target-owned guidance in each target.
Replace duplicated general workflow prose only after the installed skill and its entry path are available; do not discard unique local requirements during that consolidation.
Existing project records remain in place and do not need a new template or directory layout.

## Transition from README declarations

When the skill enters an existing workspace without `.ascent.toml`, explain the missing marker and point the user to this procedure.
An explicit README declaration remains a supplemental agent entry path; it does not activate the programmatic hook.
To migrate, add an empty `.ascent.toml` at the workspace root and do the same for subworkspaces used as direct session entry points.
Create markers within authorized setup or migration work; a read-only task can use the existing context and provide this guidance without converting the directory.
The hook recognizes only the marker and performs no README fallback or automatic migration.
Keep existing README descriptions and project records; no fixed declaration wording is needed.
For a directory installed through a symbolic link, place the marker in the actual workspace directory so it is visible through the entry path.
This does not require changes to the installation manager.
Saved hook state remains usable when the resolved workspace path and state directory are unchanged; adding the marker does not reset counters.

## Check the transition

Start a fresh session in an existing marked workspace and give it an ordinary task involving one linked target, with no global Ascent routing rule supplying the entry path.
Check that it reads the skill and relevant workspace records before target work, follows target guidance, and keeps implementation and project coordination in their respective owners.
Also check an existing README-declared workspace without the marker: the skill should load, point to the transition procedure, and use the existing context while the hook remains inactive.
An ordinary directory whose README only describes Ascent or quotes an example declaration should not select this workflow on that basis.
For an authorized task that produces a meaningful new result, check that the records capture the result and its validation limits without an unnecessary report.
For a read-only task, check that the routing does not authorize document edits.
These observations validate the entry path and workflow separately from hook delivery or refinement quality.

Enable the optional hook only when desired, following [its registration and verification guide](hooks.md).
Verify a matching event pair and selected-document changes in the installed host before treating its cadence as active.
A successful script test does not establish that a host invoked it or that the resulting refinement was useful.
