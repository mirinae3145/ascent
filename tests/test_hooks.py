"""Behavioral checks through the hook's public stdin/stdout interface."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ascent/scripts/ascent_hook.py'


class HooksTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()
        (self.workspace / '.ascent.toml').touch()
        (self.workspace / 'README.md').write_text('# Sample\n', encoding='utf-8')
        self.state_dir = self.base / 'state'

    def call(self, kind, turn='t1', session='s1', root=None, interval=5, options=(), **fields):
        event = {'hook_event_name': kind, 'session_id': session, 'turn_id': turn,
                 'cwd': str(root or self.workspace), **fields}
        return self.raw(json.dumps(event), interval, options)

    def raw(self, raw, interval=5, options=()):
        result = subprocess.run([sys.executable, str(SCRIPT), '--state-dir', str(self.state_dir),
                                 '--interval', str(interval), *options], input=raw,
                                capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        if result.stdout:
            return json.loads(result.stdout)
        return None

    def diagnose(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--diagnose', str(self.workspace),
                                 '--state-dir', str(self.state_dir)],
                                input='not an event', capture_output=True, text=True, timeout=8)
        return result, json.loads(result.stdout)

    def state(self, root=None):
        states = [json.loads(p.read_text()) for p in self.state_dir.glob('*/state.json')]
        root = str((root or self.workspace).resolve())
        return next(s for s in states if s['workspace'] == root)

    def change(self, name='knowledge.md', text='new knowledge'):
        p = self.workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def test_readme_declarations_without_marker_do_not_create_state(self):
        (self.workspace / '.ascent.toml').unlink()
        for content in ['# A project about Ascent\n', 'This directory is an Ascent workspace.\n',
                        '이 디렉터리는 Ascent 워크스페이스입니다.\n',
                        '> This directory is an Ascent workspace.\n',
                        '```md\nThis directory is an Ascent workspace.\n```\n',
                        'Create an empty `.ascent.toml` file.\n']:
            (self.workspace/'README.md').write_text(content, encoding='utf-8')
            self.assertIsNone(self.call('UserPromptSubmit'))
            self.assertIsNone(self.call('Stop'))
        self.assertFalse(self.state_dir.exists())

    def test_empty_marker_works_without_readme(self):
        (self.workspace / 'README.md').unlink()
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['selected_paths'], [])
        self.call('UserPromptSubmit')
        self.change()
        self.assertEqual(self.call('Stop', interval=1)['decision'], 'block')

    def test_readme_wording_does_not_control_identity(self):
        for n, content in enumerate(['# 프로젝트\n', '\n'*40 + 'Workspace notes\n',
                                     '> This directory is an Ascent workspace.\n']):
            with self.subTest(content=content):
                (self.workspace / 'README.md').write_text(content, encoding='utf-8')
                self.call('UserPromptSubmit', turn=f't{n}')
                self.change(text=f'change {n}')
                self.assertEqual(self.call('Stop', turn=f't{n}', interval=1)['decision'], 'block')

    def test_valid_toml_keys_do_not_override_hook_options(self):
        (self.workspace / '.ascent.toml').write_text('# Future settings\n[hook]\ninterval = 1\n')
        self.call('UserPromptSubmit')
        self.change()
        self.assertIsNone(self.call('Stop'))
        self.assertEqual(self.state()['count'], 1)

    def test_invalid_workspace_config_fails_open_before_state_creation(self):
        for content in [b'private = [', b'\xff', b'#' + b'x' * (2 * 1024 * 1024)]:
            with self.subTest(size=len(content)):
                (self.workspace / '.ascent.toml').write_bytes(content)
                result, report = self.diagnose()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(report['status'], 'error')
                self.assertEqual(report['stage'], 'config')
                self.assertEqual(report['workspace'], str(self.workspace.resolve()))
                self.assertNotIn('private', result.stdout)
                self.assertIsNone(self.call('UserPromptSubmit'))
                self.assertIsNone(self.call('Stop'))
                self.assertFalse(self.state_dir.exists())

    def test_invalid_config_preserves_state_until_repaired(self):
        self.call('UserPromptSubmit')
        path = next(self.state_dir.glob('*/state.json'))
        before = path.read_bytes()
        self.change()
        marker = self.workspace / '.ascent.toml'
        marker.write_text('broken = [')
        self.assertIsNone(self.call('Stop', interval=1))
        self.assertEqual(path.read_bytes(), before)
        marker.write_text('')
        self.assertEqual(self.call('Stop', interval=1)['decision'], 'block')

    def test_unreadable_config_is_an_error_without_creating_state(self):
        marker = self.workspace / '.ascent.toml'
        original = marker.stat().st_mode & 0o777
        marker.chmod(0)
        self.addCleanup(marker.chmod, original)
        if os.access(marker, os.R_OK):
            self.skipTest('runtime can bypass file permissions')
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report['stage'], 'config')
        self.assertIsNone(self.call('UserPromptSubmit'))
        self.assertFalse(self.state_dir.exists())

    def test_removing_and_restoring_marker_reuses_saved_counter(self):
        self.call('UserPromptSubmit')
        self.change(text='first change')
        self.call('Stop', interval=2)
        path = next(self.state_dir.glob('*/state.json'))
        before = path.read_bytes()
        marker = self.workspace / '.ascent.toml'
        marker.unlink()
        self.assertIsNone(self.call('UserPromptSubmit', turn='t2'))
        self.assertIsNone(self.call('Stop', turn='t2'))
        self.assertEqual(path.read_bytes(), before)
        marker.touch()
        self.call('UserPromptSubmit', turn='t3')
        self.change(text='second change')
        self.assertEqual(self.call('Stop', turn='t3', interval=2)['decision'], 'block')
        self.assertEqual(self.state()['last_request']['changed_turns'], 2)

    def test_marker_must_be_a_regular_file(self):
        marker = self.workspace / '.ascent.toml'
        marker.unlink()
        marker.mkdir()
        self.assertIsNone(self.call('UserPromptSubmit'))
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report['stage'], 'marker')
        self.assertFalse(self.state_dir.exists())

    def test_marker_symlinks_are_errors_including_dangling_links(self):
        marker = self.workspace / '.ascent.toml'
        marker.unlink()
        external = self.base / 'external.toml'
        external.touch()
        try:
            marker.symlink_to(external)
        except OSError:
            self.skipTest('symbolic links unavailable')
        for dangling in [False, True]:
            if dangling:
                external.unlink()
            with self.subTest(dangling=dangling):
                self.assertIsNone(self.call('UserPromptSubmit'))
                result, report = self.diagnose()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(report['stage'], 'marker')
                self.assertFalse(self.state_dir.exists())

    def test_marker_edits_do_not_count_as_document_changes(self):
        self.call('UserPromptSubmit')
        (self.workspace / '.ascent.toml').write_text('# Workspace settings\n')
        self.assertIsNone(self.call('Stop', interval=1))
        self.assertEqual(self.state()['count'], 0)

    def test_relative_or_missing_cwd_is_not_a_workspace(self):
        for root in ['relative/path', self.base / 'missing']:
            self.assertIsNone(self.call('UserPromptSubmit', root=root))
        self.assertFalse(self.state_dir.exists())

    def test_claude_code_prompt_id_is_the_turn_identity(self):
        claude = {'permission_mode': 'default', 'transcript_path': '/x'}
        def event(kind, prompt):
            return json.dumps({'hook_event_name': kind, 'session_id': 's1', 'prompt_id': prompt,
                               'cwd': str(self.workspace), **claude})
        self.raw(event('UserPromptSubmit', 'p1'), interval=1)
        self.change()
        self.assertEqual(self.raw(event('Stop', 'p1'), interval=1)['decision'], 'block')

    def test_missing_turn_identifier_fails_open(self):
        raw = json.dumps({'hook_event_name': 'UserPromptSubmit', 'session_id': 's1', 'cwd': str(self.workspace)})
        self.assertIsNone(self.raw(raw))
        self.assertFalse(self.state_dir.exists())

    def test_diagnostics_without_state_does_not_create_files(self):
        self.change('docs/note.md', 'PRIVATE CONTENT')
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['selected_paths'], ['README.md', 'docs/note.md'])
        self.assertFalse(report['state_exists'])
        self.assertFalse(self.state_dir.exists())
        self.assertNotIn('PRIVATE CONTENT', result.stdout)

    def test_diagnostics_reports_invalid_options(self):
        diagnostic_forms = [
            ['--diagnose', str(self.workspace)],
            ['--diagnose=' + str(self.workspace)],
            ['--diag', str(self.workspace)],
        ]
        invalid_options = [
            ['--interval', '0'], ['--include', '../outside.md'],
            ['--interval', 'not-an-integer'], ['--unknown-option'], ['--include'],
        ]
        for diagnostic in diagnostic_forms:
            for invalid in invalid_options:
                for options in (diagnostic + invalid, invalid + diagnostic):
                    with self.subTest(options=options):
                        result = subprocess.run(
                            [sys.executable, str(SCRIPT), '--state-dir', str(self.state_dir), *options],
                            input='not an event', capture_output=True, text=True, timeout=8)
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertEqual(json.loads(result.stdout), {
                            'status': 'error', 'stage': 'options', 'error': 'ValueError',
                        })
                        self.assertEqual(result.stderr, '')
                        self.assertFalse(self.state_dir.exists())

    def test_diagnostics_reads_counter_without_changing_saved_state(self):
        self.call('UserPromptSubmit')
        self.change()
        self.call('Stop')
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.state_dir.rglob('*') if p.is_file()}
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['changed_turns'], 1)
        self.assertEqual(report['pending_paths'], ['knowledge.md'])
        self.assertEqual(report['sessions'], 1)
        self.assertEqual(report['awaiting_stop'], 0)
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.state_dir.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_diagnostics_distinguishes_non_ascent_and_corrupt_state(self):
        (self.workspace / '.ascent.toml').unlink()
        (self.workspace / 'README.md').write_text('# Ordinary folder')
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report['status'], 'not-ascent')
        self.assertEqual(report['stage'], 'marker')
        self.assertFalse(self.state_dir.exists())
        (self.workspace / '.ascent.toml').touch()
        self.call('UserPromptSubmit')
        path = next(self.state_dir.glob('*/state.json'))
        path.write_text('{broken')
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report['status'], 'error')
        self.assertEqual(report['stage'], 'state')
        self.assertEqual(path.read_text(), '{broken')

    def test_diagnostics_reports_snapshot_failure_without_new_state(self):
        self.change('too-large.md', 'x' * (2 * 1024 * 1024 + 1))
        result, report = self.diagnose()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report['stage'], 'snapshot')
        self.assertEqual(report['error'], 'ValueError')
        self.assertFalse(self.state_dir.exists())

    def test_unchanged_turn_does_not_increment(self):
        self.change(text='pre-existing work')
        self.call('UserPromptSubmit')
        self.assertIsNone(self.call('Stop'))
        self.assertEqual(self.state()['count'], 0)

    def test_every_n_changed_turns_accumulates_paths_and_resets(self):
        for n in range(1, 6):
            turn = f't{n}'
            self.call('UserPromptSubmit', turn)
            self.change(f'part-{n}.md', f'private content {n}')
            output = self.call('Stop', turn)
            if n < 5:
                self.assertIsNone(output)
                self.assertEqual(self.state()['count'], n)
            else:
                self.assertEqual(output['decision'], 'block')
                self.assertIn('part-1.md', output['reason'])
                self.assertIn('part-5.md', output['reason'])
                self.assertNotIn('private content', output['reason'])
        state = self.state()
        self.assertEqual(state['count'], 0)
        self.assertEqual(state['pending'], [])
        self.assertEqual(len(state['last_request']['paths']), 5)

    def test_multiple_edits_are_one_turn_and_stop_is_deduplicated(self):
        self.call('UserPromptSubmit')
        self.change('a.md', 'first')
        self.change('a.md', 'second')
        self.change('b.md')
        self.assertIsNone(self.call('Stop', interval=2))
        self.assertIsNone(self.call('Stop', interval=2))
        self.assertEqual(self.state()['count'], 1)
        self.assertEqual(self.state()['pending'], ['a.md', 'b.md'])

    def test_repeated_start_preserves_original_baseline(self):
        self.call('UserPromptSubmit')
        self.change()
        self.call('UserPromptSubmit')
        self.assertEqual(self.call('Stop', interval=1)['decision'], 'block')

    def test_hook_continuation_is_not_counted(self):
        self.call('UserPromptSubmit')
        self.change()
        self.assertIsNone(self.call('Stop', stop_hook_active=True, interval=1))
        self.assertEqual(self.state()['count'], 0)

    def test_sessions_share_workspace_counter(self):
        for n in range(3):
            sid=f's{n}'
            self.call('UserPromptSubmit', session=sid)
            self.change(f'n-{n}.md')
            output = self.call('Stop', session=sid, interval=3)
            self.assertEqual(output is not None, n == 2)
        self.assertEqual(self.state()['last_request']['changed_turns'], 3)

    def test_workspaces_have_independent_counters(self):
        other=self.base/'other'
        other.mkdir()
        (other/'.ascent.toml').touch()
        for root in [self.workspace, other]:
            self.call('UserPromptSubmit', root=root)
            (root/'note.md').write_text('changed')
            self.assertIsNone(self.call('Stop', root=root, interval=2))
            self.assertEqual(self.state(root)['count'], 1)

    def test_targets_hidden_files_and_symlinks_do_not_expand_scope(self):
        (self.workspace/'targets').mkdir()
        (self.workspace/'.cache').mkdir()
        outside=self.base/'external'
        outside.mkdir()
        (outside/'note.md').write_text('original')
        try:
            (self.workspace/'linked').symlink_to(outside, target_is_directory=True)
            (self.workspace/'alias.md').symlink_to(outside/'note.md')
        except OSError:
            self.skipTest('symbolic links unavailable')
        self.call('UserPromptSubmit', options=['--include', '**/*.md'])
        self.change('targets/note.md')
        self.change('.cache/note.md')
        (outside/'note.md').write_text('changed externally')
        self.assertIsNone(self.call('Stop', options=['--include', '**/*.md']))
        self.assertEqual(self.state()['count'], 0)

    def test_agent_instruction_files_are_not_refinement_documents(self):
        self.call('UserPromptSubmit')
        self.change('AGENTS.md', 'Fixture instruction content')
        self.change('CLAUDE.md', 'Fixture instruction content')
        self.assertIsNone(self.call('Stop', interval=1))
        self.assertEqual(self.state()['count'], 0)

    def test_direct_target_entry_is_not_assigned_to_parent(self):
        child=self.workspace/'targets'/'repository'
        child.mkdir(parents=True)
        (child/'README.md').write_text('# Independent repository\n')
        self.call('UserPromptSubmit', root=child)
        self.assertFalse(self.state_dir.exists())

    def test_default_globs_cover_nested_docs_and_skip_other_artifacts(self):
        self.call('UserPromptSubmit')
        self.change('docs/direct.md')
        self.change('docs/deep/inner.md')
        self.change('draft/presentation.md')
        self.call('Stop')
        self.assertEqual(self.state()['pending'], ['docs/deep/inner.md','docs/direct.md'])

    def test_custom_scope_replaces_defaults(self):
        opts=['--include','knowledge/**/*.md']
        self.call('UserPromptSubmit', options=opts)
        self.change('knowledge/direct.md')
        self.change('knowledge/nested/detail.md')
        self.change('irrelevant.md')
        self.call('Stop', options=opts)
        self.assertEqual(self.state()['pending'], ['knowledge/direct.md','knowledge/nested/detail.md'])

    def test_deleted_document_is_preserved_in_pending_paths(self):
        p=self.change()
        self.call('UserPromptSubmit')
        p.unlink()
        self.call('Stop')
        self.assertEqual(self.state()['pending'], ['knowledge.md'])

    def test_plan_mode_and_unsupported_events_do_not_create_state(self):
        self.call('UserPromptSubmit', permission_mode='plan')
        self.call('Stop', permission_mode='plan')
        self.call('SessionEnd')
        self.assertFalse(self.state_dir.exists())

    def test_malformed_input_and_invalid_options_fail_open(self):
        for raw in ['not-json','[]','{}','null']:
            self.assertIsNone(self.raw(raw))
        for options in [['--interval','0'],['--include','../*.md'],['--unknown']]:
            self.assertIsNone(self.call('UserPromptSubmit', options=options))
        self.assertFalse(self.state_dir.exists())

    def test_state_cannot_live_in_workspace(self):
        self.assertIsNone(self.call('UserPromptSubmit', options=['--state-dir',str(self.workspace/'state')]))
        self.assertFalse((self.workspace/'state').exists())

    def test_corrupt_state_is_not_overwritten_or_treated_as_success(self):
        self.call('UserPromptSubmit')
        path=next(self.state_dir.glob('*/state.json'))
        path.write_text('{broken')
        self.change()
        self.assertIsNone(self.call('Stop'))
        self.assertEqual(path.read_text(), '{broken')

    def test_unreadable_directory_does_not_count_partial_deletion(self):
        self.change('docs/note.md')
        docs = self.workspace / 'docs'
        self.call('UserPromptSubmit')
        original = docs.stat().st_mode & 0o777
        docs.chmod(0)
        try:
            if os.access(docs, os.R_OK):
                self.skipTest('runtime can bypass directory permissions')
            self.assertIsNone(self.call('Stop'))
            self.assertEqual(self.state()['count'], 0)
            self.assertFalse(self.state()['sessions']['s1']['handled'])
        finally:
            docs.chmod(original)

    def test_unselected_unreadable_directory_does_not_disable_observation(self):
        unrelated = self.workspace / 'raw-data'
        unrelated.mkdir()
        unrelated.chmod(0)
        self.addCleanup(unrelated.chmod, 0o700)
        if os.access(unrelated, os.R_OK):
            self.skipTest('runtime can bypass directory permissions')
        self.call('UserPromptSubmit')
        self.change('docs/note.md')
        self.assertEqual(self.call('Stop', interval=1)['decision'], 'block')

    def test_exact_include_skips_unreadable_sibling_directory(self):
        self.change('docs/selected.md', 'before')
        sibling = self.workspace / 'docs' / 'other'
        sibling.mkdir()
        sibling.chmod(0)
        self.addCleanup(sibling.chmod, 0o700)
        if os.access(sibling, os.R_OK):
            self.skipTest('runtime can bypass directory permissions')
        options = ['--include', 'docs/selected.md']
        self.call('UserPromptSubmit', options=options)
        self.change('docs/selected.md', 'after')
        self.assertEqual(self.call('Stop', interval=1, options=options)['decision'], 'block')

    def test_directory_wildcards_keep_matching_descendants(self):
        options = ['--include', 'notes-*/**/entry-?.md']
        self.call('UserPromptSubmit', options=options)
        self.change('notes-a/entry-1.md')
        self.change('notes-b/deep/entry-2.md')
        self.change('other/entry-3.md')
        self.call('Stop', options=options)
        self.assertEqual(self.state()['pending'], ['notes-a/entry-1.md', 'notes-b/deep/entry-2.md'])

    def test_oversized_snapshot_does_not_count_partial_deletion(self):
        self.call('UserPromptSubmit')
        self.change('huge.md', 'x'*(2*1024*1024+1))
        self.assertIsNone(self.call('Stop'))
        self.assertEqual(self.state()['count'],0)
        self.assertFalse(self.state()['sessions']['s1']['handled'])

    def test_state_contains_no_document_or_prompt_content(self):
        self.call('UserPromptSubmit', prompt='PRIVATE PROMPT')
        self.change(text='PRIVATE DOCUMENT')
        self.call('Stop')
        raw=next(self.state_dir.glob('*/state.json')).read_text()
        self.assertNotIn('PRIVATE PROMPT',raw)
        self.assertNotIn('PRIVATE DOCUMENT',raw)

    def test_concurrent_sessions_do_not_lose_counter_updates(self):
        for i in range(8):
            self.call('UserPromptSubmit',session=f's{i}')
        self.change()
        with ThreadPoolExecutor(max_workers=8) as pool:
            outputs=list(pool.map(lambda i:self.call('Stop',session=f's{i}',interval=20),range(8)))
        self.assertTrue(all(o is None for o in outputs))
        self.assertEqual(self.state()['count'],8)

    def test_symbolic_workspace_entry_uses_same_counter(self):
        alias=self.base/'workspace-alias'
        try:
            alias.symlink_to(self.workspace,target_is_directory=True)
        except OSError:
            self.skipTest('symbolic links unavailable')
        self.call('UserPromptSubmit',root=alias)
        self.change()
        self.call('Stop',root=alias)
        self.assertEqual(self.state()['count'],1)
        self.assertEqual(len(list(self.state_dir.glob('*/state.json'))),1)


if __name__ == '__main__':
    unittest.main()
