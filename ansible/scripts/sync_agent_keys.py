#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path

CACHE_DIR = Path.home() / ".cache/rlocal/rofi-vscode"
INPUT_FILE = CACHE_DIR / "upmon_agents.generated.json"
OUTPUT_FILE = CACHE_DIR / "upmon_agents.enriched.json"


def rpass_ensure(key: str) -> str:
    result = subprocess.run(["rpass", "ensure", key], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def resolve_ssh_dest(alias: str) -> str:
    result = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True, check=True)
    ssh_config = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        ssh_config[key] = value
    ip = subprocess.run(
        ["getent", "hosts", ssh_config["hostname"]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[0]
    return f"{ssh_config['user']}@{ip}"


def main():
    data = json.loads(INPUT_FILE.read_text())

    enriched_sites = []
    for site in data["sites"]:
        rpass_key = f"personal/upmon/apikey/{site['project_id']}/{site['site_key']}"

        api_key = rpass_ensure(rpass_key)
        ssh_dest = resolve_ssh_dest(site["ssh_host"])
        enriched_sites.append({**site, "agent_api_key": api_key, "ssh_dest": ssh_dest})

    OUTPUT_FILE.write_text(json.dumps({"sites": enriched_sites}))
    print(f"Wrote {len(enriched_sites)} sites to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
