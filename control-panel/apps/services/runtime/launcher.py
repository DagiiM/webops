"""Launch a trusted application using an argv and a restricted environment."""
import json
import os
import sys
from pathlib import Path

def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    os.chdir(spec["cwd"])
    if spec.get("sandbox"):
        from sandbox import restrict
        restrict(spec["sandbox"])
    os.execvpe(spec["argv"][0], spec["argv"], spec["env"])

if __name__ == "__main__":
    main()
