"""Run the packaged, synthetic Claude credential-isolation check without paid calls."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from armada.engine.claude_isolation import main

if __name__ == '__main__':
    raise SystemExit(main())
