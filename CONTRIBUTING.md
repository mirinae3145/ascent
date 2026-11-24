# Contributing

Keep Ascent's reusable workspace concepts independent of personal instruction hierarchies, machine paths, installation managers, and domain-specific research or development policies.
The canonical workflow is `skills/ascent/SKILL.md`; optional hook mechanics belong in its linked hook guide.
Keep the skill self-contained when installed independently of this repository.

The hook only observes bounded, selected project documents and returns host-compatible continuation requests.
It must not write workspace documents, follow target links, call a model service, modify trust settings, or infer task completion from an event.
Changes to counters and pending file sets must remain safe under concurrent sessions and repeated events.
Retain the distinction between requesting refinement and verifying that it was performed.

Run the behavioral checks from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Also run the available skill validator when changing the skill.
Test both supported event payloads and failure behavior; non-Ascent, malformed input, unsupported events, and read-only plan mode must not produce continuation requests.
Run native Windows checks when available before claiming Windows execution was verified.
Keep generated indexes, caches, runtime state, and installation-specific records out of tracked source.

Keep every tracked file covered by an annotation in `REUSE.toml`.
Scripts and tests are MIT, documentation is CC BY 4.0, and repository configuration and examples are CC0.
Place a new file under a covered path, or add it to the matching annotation.
Running `uvx reuse@6.3.0 lint` from the [REUSE tool](https://reuse.software/) confirms that every file is covered.
