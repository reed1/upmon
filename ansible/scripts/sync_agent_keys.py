#!/usr/bin/env python3

import json
import os
import subprocess
from pathlib import Path
import yaml

CACHE_DIR = Path.home() / ".cache/rlocal/rofi-vscode"
INPUT_FILE = CACHE_DIR / "upmon_agents.generated.json"
OUTPUT_FILE = CACHE_DIR / "upmon_agents.enriched.json"
INVENTORY_FILE = Path(__file__).resolve().parent.parent / "inventory.yaml"


def rpass_ensure(key: str) -> str:
    result = subprocess.run(["rpass", "ensure", key], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def resolve_ssh_dest(alias: str) -> str:
    env = {**os.environ, "SSH_VPNPREP_SKIP": "1"}
    result = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True, check=True, env=env)
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
    inventory = yaml.safe_load(INVENTORY_FILE.read_text())
    upmon_config = inventory["all"]["vars"]["upmon_config"]
    default_retention_days = upmon_config["agent_defaults"]["retention_days"]

    data = json.loads(INPUT_FILE.read_text())

    enriched_sites = []
    for site in data["sites"]:
        rpass_key = f"personal/upmon/apikey/{site['project_id']}/{site['site_key']}"

        api_key = rpass_ensure(rpass_key)
        ssh_dest = resolve_ssh_dest(site["ssh_host"])
        enriched = {**site, "agent_api_key": api_key, "ssh_dest": ssh_dest}
        if "retention_days" not in enriched:
            enriched["retention_days"] = default_retention_days
        enriched_sites.append(enriched)

    OUTPUT_FILE.write_text(json.dumps({"sites": enriched_sites}))
    print(f"Wrote {len(enriched_sites)} sites to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
