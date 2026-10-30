"""Helpers for durable JSON reports from local probe scripts."""
import json
import os
from pathlib import Path
import secrets


def write_json_report(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A plain exclusive open keeps the umask-derived mode of a direct write.
    # Include an unpredictable suffix so a stale file from a reused PID cannot
    # block a later publication.
    for _ in range(100):
        staged = path.with_name(
            "." + path.name + "." + str(os.getpid()) + "." + secrets.token_hex(8)
        )
        try:
            stream = open(staged, "x", encoding="utf-8", newline="\n")
        except FileExistsError:
            continue
        break
    else:
        raise FileExistsError("could not create a unique probe report staging file")
    try:
        with stream:
            stream.write(json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise