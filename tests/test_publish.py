"""Exercise the installed publisher CLI against disposable local Git remotes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PUBLISH = Path(__file__).resolve().parents[1] / 'skills/ascent/scripts/publish.py'


class PublishTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.workspace = self.base / 'work'
        self.remote = self.base / 'shared.git'
        self.env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
        self.git('init', '--bare', str(self.remote), cwd=self.base)
        self.git('init', '-b', 'work', str(self.workspace), cwd=self.base)
        self.git('config', 'user.email', 'writer@example.org')
        self.git('config', 'user.name', 'Writer')
        self.git('remote', 'add', 'team', str(self.remote))
        self.configure()
        self.write('check.py', """import os
from pathlib import Path
import subprocess
import sys

assert Path('.ascent.toml').is_file() and sys.argv[1:] == ['one argument', '$HOME']
with Path(os.environ['AUDIT']).open('a') as audit:
    print('checked', file=audit)
effect = os.environ.get('ASCENT_TEST_EFFECT')
if effect == 'fail':
    sys.exit(7)
if effect == 'edit':
    Path('records/note.md').write_text('dirty')
if effect == 'commit':
    subprocess.run(['git', 'commit', '--allow-empty', '-m', 'next'], check=True)
if effect == 'race':
    subprocess.run(['git', 'push', 'team', 'work:refs/heads/shared'], check=True)
""")
        self.write('records/old.md', 'old')
        self.write('outside.md', 'old')
        self.commit('contract')
        self.git('push', 'team', 'HEAD:refs/heads/shared')
        self.start = self.tip()
        self.audit = self.base / 'audit'
        self.env['AUDIT'] = str(self.audit)

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd or self.workspace, env=self.env,
                              check=True, capture_output=True, text=True).stdout.strip()

    def tip(self):
        return self.git('rev-parse', 'refs/heads/shared', cwd=self.remote)

    def write(self, path, contents):
        target = self.workspace / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding='utf-8')

    def configure(self, allow=('records/**',)):
        command = [sys.executable, 'check.py', 'one argument', '$HOME']
        self.write('.ascent.toml', '[publish]\nallow = ' + json.dumps(allow) +
                   '\ncheck = ' + json.dumps(command) + '\n')

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-m', message)

    def publish(self, action='push', *, approved=None, ok=True):
        dest = [] if action == 'check' else ['team', 'shared']
        if action == 'push':
            dest.extend(approved if approved is not None else [self.tip(), self.git('rev-parse', 'HEAD')])
        result = subprocess.run([sys.executable, str(PUBLISH), action, *dest], cwd=self.workspace,
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def preview_range(self):
        first_line = self.publish('preview').stdout.splitlines()[0]
        return first_line.removeprefix('team refs/heads/shared: ').split(' -> ')

    def test_named_remote_pushurl_and_single_ref(self):
        other = self.base / 'other.git'
        self.git('clone', '--bare', str(self.remote), str(other))
        self.git('remote', 'set-url', 'team', str(other))
        self.git('remote', 'set-url', '--push', 'team', str(self.remote))
        self.git('config', f'url.{other}.pushInsteadOf', str(self.remote))
        self.git('config', 'remote.team.mirror', 'true')
        self.git('config', 'remote.team.push', 'work:refs/heads/extra')
        self.git('config', 'push.followTags', 'true')
        self.write('records/record.md', 'ready')
        self.commit('record')
        self.git('tag', '-a', 'tagged', '-m', 'local tag')
        self.publish(approved=self.preview_range())
        self.assertEqual(self.tip(), self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.git('for-each-ref', '--format=%(refname)', cwd=self.remote),
                         'refs/heads/shared')
        self.assertEqual(self.git('rev-parse', 'refs/heads/shared', cwd=other), self.start)

    def test_push_requires_both_previewed_revisions(self):
        self.write('records/note.md', 'allowed')
        self.commit('ready')
        self.publish(ok=False, approved=())
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.tip(), self.start)

    def test_preview_fetches_the_resolved_push_url_once(self):
        target = self.base / 'team=records.git'
        self.git('clone', '--bare', str(self.remote), str(target))
        self.git('config', 'remote.team.pushurl', 'records-destination')
        self.git('config', f'url.{target}.insteadOf', 'records-destination')
        self.git('config', f'url.{self.base / "unavailable"}.insteadOf', str(target))
        self.write('records/new.md', 'ready')
        self.commit('ready')
        self.publish(approved=self.preview_range())
        self.assertEqual(self.git('rev-parse', 'refs/heads/shared', cwd=target), self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.tip(), self.start)

    def test_local_commit_after_preview_needs_new_approval(self):
        self.write('records/one.md', 'ready')
        self.commit('ready')
        approved = self.preview_range()
        self.write('records/two.md', 'later')
        self.commit('later')
        self.assertIn('preview again', self.publish(approved=approved, ok=False).stderr)
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.tip(), self.start)

    def test_rewound_destination_after_preview_needs_new_approval(self):
        self.write('records/old.md', 'published')
        self.commit('already published')
        self.git('push', 'team', 'HEAD:refs/heads/shared')
        self.write('records/new.md', 'ready')
        self.commit('ready')
        approved = self.preview_range()
        self.git('update-ref', 'refs/heads/shared', self.start, cwd=self.remote)
        self.assertIn('preview again', self.publish(approved=approved, ok=False).stderr)
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.tip(), self.start)

    def test_fetch_is_isolated_from_fetch_head(self):
        self.write('records/new.md', 'ready')
        self.commit('ready')
        head = self.git('rev-parse', 'HEAD')
        self.git('fetch', '.', 'work')
        refs = self.git('for-each-ref')
        self.assertEqual(self.preview_range(), [self.start, head])
        self.assertEqual(self.git('rev-parse', 'FETCH_HEAD'), head)
        self.assertEqual(self.git('for-each-ref'), refs)
        self.publish(approved=[self.start, head])
        self.assertEqual(self.tip(), head)

    def test_sparse_checkout_cannot_pass_publication_checks(self):
        self.write('records/new.md', 'ready')
        self.commit('ready')
        approved = self.preview_range()
        self.git('sparse-checkout', 'set', '--cone', 'other')
        self.assertFalse((self.workspace / 'records/new.md').exists())
        self.assertEqual(self.git('status', '--porcelain'), '')
        for action in ('check', 'preview', 'push'):
            with self.subTest(action=action):
                result = self.publish(action, approved=approved, ok=False)
                self.assertIn('complete checkout', result.stderr)
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.tip(), self.start)

    def test_worktree_preview_ci_and_fast_forward(self):
        other = self.base / 'writer'
        self.git('worktree', 'add', '-b', 'writer', str(other))
        self.write('untracked-in-other-worktree', 'local')
        self.workspace = other
        self.git('mv', 'records/old.md', 'records/new name.md')
        self.write('records/sub/author.md', 'details')
        self.commit('publish records')
        preview = self.publish('preview')
        self.assertIn('records/old.md', preview.stdout)
        self.assertIn('records/new name.md', preview.stdout)
        self.assertIn('publish records', preview.stdout)
        self.assertEqual(self.tip(), self.start)
        self.assertFalse(self.audit.exists())
        self.publish('check')
        self.publish()
        self.assertEqual(self.tip(), self.git('rev-parse', 'HEAD'))
        self.publish()
        self.assertEqual(self.audit.read_text().splitlines(), ['checked', 'checked'])

    def test_reverted_change_and_both_sides_of_renames(self):
        self.git('mv', 'outside.md', 'records/in.md')
        self.commit('move into allowance')
        self.assertIn('outside.md', self.publish(ok=False).stderr)
        self.git('mv', 'records/in.md', 'outside.md')
        self.commit('move out again')
        self.assertIn('outside.md', self.publish(ok=False).stderr)
        self.assertEqual(self.tip(), self.start)
        self.assertFalse(self.audit.exists())

    def test_denies_deleted_paths_and_policy_even_if_broadly_allowed(self):
        self.git('rm', 'outside.md')
        self.commit('remove outside record')
        self.assertIn('outside.md', self.publish(ok=False).stderr)
        self.configure(['**'])
        self.commit('change policy')
        self.assertIn('.ascent.toml', self.publish(ok=False).stderr)
        self.assertFalse(self.audit.exists())

    def test_merged_branch_history_is_checked(self):
        self.git('switch', '-c', 'side')
        self.write('side-only.md', 'temporary')
        self.commit('side record')
        self.git('rm', 'side-only.md')
        self.commit('retire side record')
        self.git('switch', 'work')
        self.git('merge', '--no-ff', 'side', '-m', 'merge side records')
        self.assertIn('side-only.md', self.publish(ok=False).stderr)
        self.assertEqual(self.tip(), self.start)

    def test_dirty_index_worktree_and_failing_check_stop_the_push(self):
        self.write('records/note.md', 'v1')
        self.commit('record')
        self.write('notes.tmp', 'local')
        self.assertIn('worktree', self.publish(ok=False).stderr)
        (self.workspace / 'notes.tmp').unlink()
        self.write('records/note.md', 'v2')
        self.git('add', 'records/note.md')
        self.assertIn('worktree', self.publish(ok=False).stderr)
        self.commit('updated record')
        self.assertFalse(self.audit.exists())
        self.env['ASCENT_TEST_EFFECT'] = 'fail'
        self.assertIn('exit 7', self.publish(ok=False).stderr)
        self.assertEqual(self.tip(), self.start)

    def test_changed_head_or_tracked_content_after_check_stops_the_push(self):
        self.write('records/note.md', 'record')
        self.commit('record')
        self.env['ASCENT_TEST_EFFECT'] = 'edit'
        self.assertIn('worktree', self.publish(ok=False).stderr)
        self.commit('updated record')
        self.env['ASCENT_TEST_EFFECT'] = 'commit'
        self.assertIn('revision changed', self.publish(ok=False).stderr)
        self.assertEqual(self.tip(), self.start)

    def test_concurrent_destination_update_and_diverged_history(self):
        self.git('commit', '--allow-empty', '-m', 'competing publication')
        competing = self.git('rev-parse', 'HEAD')
        self.git('switch', '-c', 'second', self.start)
        self.write('records/new.md', 'other record')
        self.commit('other publication')
        self.env['ASCENT_TEST_EFFECT'] = 'race'
        self.publish(ok=False)
        self.assertEqual(self.tip(), competing)
        self.assertIn('integrate', self.publish(ok=False).stderr)
        self.assertEqual(self.audit.read_text().splitlines(), ['checked'])

    def test_missing_invalid_allow_or_command(self):
        for config in ('', '[publish]\nallow=["records/**"]\ncheck="check.py"',
                       '[publish]\nallow=["../**"]\ncheck=["unused"]',
                       '[publish]\ncheck=["unused"]'):
            with self.subTest(config=config):
                self.write('.ascent.toml', config)
                self.commit('invalid configuration')
                self.publish(ok=False)
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.tip(), self.start)
