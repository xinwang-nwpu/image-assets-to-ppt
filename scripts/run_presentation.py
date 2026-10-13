#!/usr/bin/env python3
"""Launch presentation Node commands with the current bundled runtime environment."""
import argparse
import ctypes
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


def runtime_environment():
    dependencies = Path(sys.executable).resolve().parent.parent
    node = dependencies / 'node' / 'bin' / ('node.exe' if os.name == 'nt' else 'node')
    modules = dependencies / 'node' / 'node_modules'
    if not node.is_file() or not (modules / '@oai' / 'artifact-tool' / 'package.json').is_file():
        raise RuntimeError('Use the bundled Python returned by load_workspace_dependencies; Node/Artifact Tool is missing beside this Python.')
    env = os.environ.copy()
    env.update(RUNTIME_NODE=str(node), RUNTIME_NODE_MODULES=str(modules),
               CODEX_PRIMARY_RUNTIME_NODE_MODULES=str(modules), RUNTIME_PYTHON=sys.executable,
               RUNTIME_BIN_DIR=str(dependencies / 'bin' / 'override'))
    if os.name == 'nt' and (not env.get('SystemRoot') or not env.get('WINDIR')):
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
        if not 0 < length < len(buffer) or not Path(buffer.value).is_dir():
            raise RuntimeError('Cannot determine the Windows directory.')
        for key in ('SystemRoot', 'WINDIR'):
            if not env.get(key):
                env[key] = buffer.value
    return node, env


PROBE = r'''
const {createRequire}=require('node:module');
const {join}=require('node:path');
const {pathToFileURL}=require('node:url');
const req=createRequire(join(process.env.RUNTIME_NODE_MODULES,'.runtime-probe.cjs'));
(async()=>{
  require('node:crypto').randomBytes(8);
  const api=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
  if(typeof api.Presentation?.create!=='function'||!api.PresentationFile)throw Error('Presentation API unavailable');
  req('sharp');
  console.log(JSON.stringify({ok:true,node:process.execPath,modules:process.env.RUNTIME_NODE_MODULES,
    SystemRoot:process.env.SystemRoot,WINDIR:process.env.WINDIR}));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--cwd', type=Path)
    parser.add_argument('node_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        node, env = runtime_environment()
        if args.preflight:
            if args.node_args:
                parser.error('--preflight does not accept a Node command')
            for package in ('PIL', 'lxml'):
                if importlib.util.find_spec(package) is None:
                    raise RuntimeError(f'Bundled Python package missing: {package}')
            return subprocess.run([str(node), '-e', PROBE], env=env, cwd=args.cwd, timeout=60).returncode
        command = args.node_args
        if command[:1] == ['--']:
            command = command[1:]
        if not command:
            parser.error('Provide a Node script/arguments, or --preflight')
        return subprocess.run([str(node), *command], env=env, cwd=args.cwd).returncode
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'Presentation runtime: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
