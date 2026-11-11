"""Bind all CLI standard handles to the worker pseudoconsole, not inherited pipes."""
import json
import subprocess
import sys


def main():
    with open(sys.argv[1],encoding='utf-8') as stream:
        spec=json.load(stream)
    with open('CONIN$','rb',buffering=0) as input, open('CONOUT$','wb',buffering=0) as output:
        process=subprocess.Popen(spec['args'],cwd=spec['cwd'],env=spec['env'],
                                 stdin=input,stdout=output,stderr=output)
        return process.wait()


if __name__=='__main__':
    raise SystemExit(main())
