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
        (self.workspace / 'README.md').write_text('# Sample\n\nThis directory is an Ascent workspace.\n', encoding='utf-8')
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

    def state(self, root=None):
        states = [json.loads(p.read_text()) for p in self.state_dir.glob('*/state.json')]
        root = str((root or self.workspace).resolve())
        return next(s for s in states if s['workspace'] == root)

    def change(self, name='knowledge.md', text='new knowledge'):
        p = self.workspace / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p

    def test_non_ascent_and_quoted_examples_do_not_create_state(self):
        for content in ['# A project about Ascent\n', '> This directory is an Ascent workspace.\n',
                        '```md\nThis directory is an Ascent workspace.\n```\n']:
            (self.workspace/'README.md').write_text(content)
            self.assertIsNone(self.call('UserPromptSubmit'))
            self.assertIsNone(self.call('Stop'))
        self.assertFalse(self.state_dir.exists())

    def test_declaration_must_be_near_beginning(self):
        (self.workspace/'README.md').write_text('\n'*40 + 'This directory is an Ascent workspace.\n')
        self.assertIsNone(self.call('UserPromptSubmit'))
        self.assertFalse(self.state_dir.exists())

    def test_korean_declaration(self):
        (self.workspace/'README.md').write_text('# 프로젝트\n\n이 디렉터리는 Ascent 워크스페이스입니다.\n', encoding='utf-8')
        self.call('UserPromptSubmit')
        self.change()
        self.assertEqual(self.call('Stop', interval=1)['decision'], 'block')

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
        (other/'README.md').write_text('This directory is an Ascent workspace.\n')
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
