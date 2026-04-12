# Access Log Endpoint

The `/health/agent` endpoint allows the upmon agent to query the app's access log database remotely.

## Architecture

```
Upmon Backend --SSH--> GET /health/agent?q=<base64> --subprocess--> upmon-agent query --> SQLite
```

The endpoint receives a base64-encoded JSON query param, shells out to the `upmon-agent` script, and returns its JSON output.

## Implementation

The endpoint accepts a single `q` query param containing a base64-encoded JSON payload. It shells out to the upmon-agent script and returns its JSON output.

The agent always exits 0 and writes all output (including errors) to stdout as JSON `{"error": ..., "result": ...}` — never to stderr. The endpoint should always return this same JSON shape, even if the process itself fails to run (e.g. python3 not installed, file not found, timeout).

The agent path comes from an env var / config.

### Example (FastAPI)

```python
import json
import os
import subprocess

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/health")


@router.get("")
def health():
    return {"status": "UP"}


@router.get("/agent")
def health_agent(q: str = Query()):
    agent_path = os.environ.get("UPMON_AGENT_PATH")
    if not agent_path:
        raise HTTPException(500, "UPMON_AGENT_PATH not configured")

    args = json.dumps({"q": q})
    try:
        result = subprocess.run(
            ["python3", agent_path, args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as e:
        return {"error": str(e), "result": None}

    if result.stdout:
        return json.loads(result.stdout)
    return {"error": result.stderr.strip() or "Agent process failed with no output", "result": None}
```

## Environment Variable

Set `UPMON_AGENT_PATH` to the absolute path of the upmon-agent `main.py` on the server. Default deployment path is `~/app/upmon-agent/main.py`.
