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
Create markers within authorized setup or migration work; a read-only task can use the existing context and provide this guidance without converting the directory.

To migrate, take these steps:

1. Add an empty `.ascent.toml` at the workspace root.
1. Do the same for subworkspaces used as direct session entry points.
1. For a directory installed through a symbolic link, place the marker in the actual workspace directory so it is visible through the entry path.
   This does not require changes to the installation manager.

The transition leaves the following unchanged:

- **Records**: Keep existing README descriptions and project records; no fixed declaration wording is needed.
- **Hook recognition**: The hook recognizes only the marker and performs no README fallback or automatic migration.
- **Hook state**: Saved hook state remains usable when the resolved workspace path and state directory are unchanged; adding the marker does not reset counters.

## Check the transition

These checks validate the entry path and workflow separately from hook delivery or refinement quality.
Use them to confirm the transition:

- **Marked workspace**: Start a fresh session in an existing marked workspace and give it an ordinary task involving one linked target.
  No global Ascent routing rule should supply the entry path.
  Check that it reads the skill and relevant workspace records before target work and follows target guidance.
  Check that it reassesses applicable guidance, including what global instructions direct, after recovering the context and again when the work changes kind.
  Check that it keeps implementation and project coordination in their respective owners.
- **README-declared workspace**: Check an existing README-declared workspace without the marker.
  The skill should load, point to the transition procedure, and use the existing context while the hook remains inactive.
- **Ordinary directory**: An ordinary directory whose README only describes Ascent or quotes an example declaration should not select this workflow on that basis.
- **Record updates**: For an authorized task that produces a meaningful new result, check the records.
  They should capture the result and its validation limits without an unnecessary report.
- **Read-only task**: For a read-only task, check that the routing does not authorize document edits.

Enable the optional hook only when desired, following [its registration and verification guide](hooks.md).
Verify a matching event pair and selected-document changes in the installed host before treating its cadence as active.
A successful script test does not establish that a host invoked it or that the resulting refinement was useful.
