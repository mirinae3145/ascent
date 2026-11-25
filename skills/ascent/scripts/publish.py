#!/usr/bin/env python3
"""Preview or publish committed Ascent workspace records, or run the CI check."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import uuid

from ascent_hook import MAX_FILE, WORKSPACE_FILE, matches, pattern_list, workspace_root


def git(*args, data=None, config=None):
    options = ['git', '--no-replace-objects']
    env = None
    if config is not None:
        key, value = config
        # URLs and remote names can contain '=' inside the config key.
        options.append(f'--config-env={key}=ASCENT_GIT_CONFIG_VALUE')
        env = {**os.environ, 'ASCENT_GIT_CONFIG_VALUE': value}
    return subprocess.run([*options, *args], input=data, env=env, stdout=subprocess.PIPE, check=True).stdout


def publish_settings(head):
    # Read the tracked policy, including in detached CI checkouts.
    marker = f'{head}:{WORKSPACE_FILE}'
    if int(git('cat-file', '-s', marker)) > MAX_FILE:
        raise ValueError('workspace config exceeds size limit')
    config = tomllib.loads(git('cat-file', 'blob', marker).decode('utf-8'))
    publish = config.get('publish')
    if not isinstance(publish, dict):
        raise ValueError('the committed marker must define [publish]')
    return publish


def check_command(settings):
    command = settings.get('check')
    if (not isinstance(command, list) or not command or not command[0]
            or not all(isinstance(arg, str) and '\0' not in arg for arg in command)):
        raise ValueError('publish.check must be a command and arguments in a string array')
    return command


def require_clean():
    if git('status', '--porcelain=v1', '--untracked-files=normal', '--ignore-submodules=none'):
        raise ValueError('commit or set aside changes in this worktree before publishing (see git status)')


def require_complete_checkout():
    # A clean status can hide omitted files or changes masked by index flags.
    entries = git('ls-files', '-v', '-z', '--cached', '--deleted').split(b'\0')
    if any(entry.startswith((b'S ', b'R ')) or entry[:1].islower() for entry in entries):
        raise ValueError('use a complete checkout with all tracked files present and no '
                         'skip-worktree or assume-unchanged entries')


def push_url(remote):
    urls = git('remote', 'get-url', '--push', '--all', '--', remote).splitlines()
    if len(urls) != 1:
        raise ValueError('choose a remote with one push destination')
    return os.fsdecode(urls[0])


def fetch_destination(url, ref):
    token = uuid.uuid4().hex
    private_ref = f'refs/ascent/publish/{token}'
    # Git expands the alias once, to the already-resolved push endpoint. Passing
    # that endpoint as a new URL would subject it to insteadOf a second time.
    alias = f'ascent-fetch-{token}'
    try:
        git('fetch', '--no-write-fetch-head', '--no-tags', '--no-recurse-submodules', '--refmap=',
            '--', alias, f'{ref}:{private_ref}', config=(f'url.{url}.insteadOf', alias))
        return git('rev-parse', '--verify', f'{private_ref}^{{commit}}').decode('ascii').strip()
    finally:
        git('update-ref', '-d', private_ref)


def outgoing_paths(revisions):
    # Compare every outgoing commit with each parent. Without rename detection
    # both path names are checked, even when later commits undo the change.
    raw = git('diff-tree', '--stdin', '--root', '-r', '-m', '--no-renames',
              '--ignore-submodules=none', '--no-commit-id', '--name-only', '-z', data=revisions)
    return sorted({os.fsdecode(path) for path in raw.split(b'\0') if path})


def run(args):
    root = workspace_root(str(Path.cwd()))
    if root is None:
        raise ValueError('run from a workspace with a regular .ascent.toml marker')
    top = os.fsdecode(git('rev-parse', '--show-toplevel').removesuffix(b'\n'))
    if Path(top).resolve() != root:
        raise ValueError('run from the marked root of a Git worktree')
    require_complete_checkout()
    head = git('rev-parse', '--verify', 'HEAD^{commit}').decode('ascii').strip()
    settings = publish_settings(head)
    command = check_command(settings)
    if args.action == 'check':
        subprocess.run(command, cwd=root, check=True)
        return

    allow = pattern_list(settings.get('allow'), 'publish.allow')
    require_clean()
    ref = f'refs/heads/{args.branch}'
    git('check-ref-format', ref)
    url = push_url(args.remote)
    base = fetch_destination(url, ref)
    print(f'{args.remote} {ref}: {base} -> {head}', flush=True)
    if args.action == 'push' and (base, head) != (args.base, args.head):
        raise ValueError('the destination or worktree revision differs from the approved range; preview again')
    if head == base:
        print('Already at the destination revision.')
        return
    ancestor = subprocess.run(['git', '--no-replace-objects', 'merge-base', '--is-ancestor', base, head], check=False)
    if ancestor.returncode == 1:
        raise ValueError('integrate the fetched destination in your worktree and preview again')
    ancestor.check_returncode()
    outgoing = f'{base}..{head}'
    revisions = git('rev-list', '--reverse', outgoing)
    print('Outgoing commits:')
    for line in os.fsdecode(git('log', '--reverse', '--format=%H %s', outgoing)).splitlines():
        print(' ', repr(line))
    paths = outgoing_paths(revisions)
    print('Touched paths:')
    refused = []
    for path in paths:
        print(' ', repr(path))
        if path == WORKSPACE_FILE or not matches(tuple(path.split('/')), allow):
            refused.append(path)
    if refused:
        raise ValueError('use the workspace review route for ' + ', '.join(map(repr, refused)))
    if args.action == 'preview':
        return

    sys.stdout.flush()
    subprocess.run(command, cwd=root, check=True)
    require_complete_checkout()
    require_clean()
    if git('rev-parse', 'HEAD').decode('ascii').strip() != head:
        raise ValueError('the worktree revision changed during the check; preview again')
    if push_url(args.remote) != url:
        raise ValueError('the push destination changed during the check; preview again')
    # The ancestry check pins a fast-forward; the explicit lease also refuses
    # deletion, rewind or another writer's update between fetch and push.
    git('push', '--no-follow-tags', '--recurse-submodules=no', f'--force-with-lease={ref}:{base}',
        '--', args.remote, f'{head}:{ref}', config=(f'remote.{args.remote}.mirror', 'false'))
    print(f'Published {head} to {args.remote} {ref}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('check', help='run the committed publish.check command (also for CI)')
    for action in ('preview', 'push'):
        sub = actions.add_parser(action, help=f'{action} changes to an existing remote branch')
        sub.add_argument('remote', help='configured Git remote name')
        sub.add_argument('branch', help='destination branch name')
        if action == 'push':
            sub.add_argument('base', help='full destination commit ID from the approved preview')
            sub.add_argument('head', help='full worktree commit ID from the approved preview')
    try:
        run(parser.parse_args())
    except subprocess.CalledProcessError as error:
        print(f'Ascent publisher: command failed (exit {error.returncode}).', file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f'Ascent publisher: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
