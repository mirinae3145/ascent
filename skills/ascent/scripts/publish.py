#!/usr/bin/env python3
"""Preview or publish committed Ascent workspace records, or run the CI check."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from ascent_hook import MAX_FILE, WORKSPACE_FILE, matches, pattern_list, workspace_root


def git(*args, data=None):
    return subprocess.run(['git', '--no-replace-objects', *args], input=data, stdout=subprocess.PIPE, check=True).stdout


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


def fetch_destination(remote, branch):
    ref = f'refs/heads/{branch}'
    git('check-ref-format', ref)
    urls = git('remote', 'get-url', '--push', '--all', '--', remote).splitlines()
    if len(urls) != 1:
        raise ValueError('choose a remote with one push destination')
    # Fetch the actual push endpoint. An explicit URL also avoids the remote's
    # configured mirror or additional push refspecs.
    url = os.fsdecode(urls[0])
    git('fetch', '--no-tags', '--no-recurse-submodules', '--refmap=', '--', url, ref)
    base = git('rev-parse', '--verify', 'FETCH_HEAD^{commit}').decode('ascii').strip()
    return url, ref, base


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
    head = git('rev-parse', '--verify', 'HEAD^{commit}').decode('ascii').strip()
    settings = publish_settings(head)
    command = check_command(settings)
    if args.action == 'check':
        subprocess.run(command, cwd=root, check=True)
        return

    allow = pattern_list(settings.get('allow'), 'publish.allow')
    require_clean()
    url, ref, base = fetch_destination(args.remote, args.branch)
    print(f'{args.remote} {ref}: {base} -> {head}', flush=True)
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
    require_clean()
    if git('rev-parse', 'HEAD').decode('ascii').strip() != head:
        raise ValueError('the worktree revision changed during the check; preview again')
    # The ancestry check pins a fast-forward; the explicit lease also refuses
    # deletion, rewind or another writer's update between fetch and push.
    git('push', '--no-follow-tags', '--recurse-submodules=no', f'--force-with-lease={ref}:{base}',
        '--', url, f'{head}:{ref}')
    print(f'Published {head} to {args.remote} {ref}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('check', help='run the committed publish.check command (also for CI)')
    for action in ('preview', 'push'):
        sub = actions.add_parser(action, help=f'{action} changes to an existing remote branch')
        sub.add_argument('remote', help='configured Git remote name')
        sub.add_argument('branch', help='destination branch name')
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
