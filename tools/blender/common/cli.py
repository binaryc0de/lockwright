"""Headless CLI runner with reliable exit status, including Blender teardown.

This host/sandbox stalls in Blender's native shutdown after the Python task
has finished (even with -noaudio). All Blender export/render operators are
synchronous. Flush after they return, then bypass native teardown; failures
print their traceback and return nonzero. Imported build() remains normal.
"""
import argparse
import os
from pathlib import Path
import sys
import traceback

import bpy


def run_cli(build, description):
    if not bpy.app.background:
        raise RuntimeError('The asset CLI requires Blender -b')
    status = 0
    try:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
        parser = argparse.ArgumentParser(description=description)
        parser.add_argument('--out', type=Path, required=True)
        args = parser.parse_args(argv)
        build(args.out)
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else 1
    except BaseException:
        traceback.print_exc()
        status = 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
    os._exit(status)
