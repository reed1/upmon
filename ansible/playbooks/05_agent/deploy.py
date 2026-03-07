#!/usr/bin/env python3
"""Deploy upmon-agent to target servers.

Replaces the Ansible playbook (main.yaml) with a straightforward script.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENRICHED_FILE = Path.home() / ".cache/rlocal/rofi-vscode/upmon_agents.enriched.json"
AGENT_SCRIPT = REPO_ROOT / "backend/scripts/upmon-agent/main.py"
DEFAULT_RETENTION_DAYS = 360
MANUAL_DEPLOY_DIR = Path("/tmp/upmon-agents")

CLEANUP_SERVICE = """\
[Unit]
Description=Upmon agent — clean up old access log entries

[Service]
Type=oneshot
ExecStart=python3 {agent_path}/main.py cleanup
"""

CLEANUP_TIMER = """\
[Unit]
Description=Daily cleanup of old access log entries

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=3600

[Install]
WantedBy=timers.target
"""


def step(msg: str):
    print(f"\n=> {msg}", flush=True)


def sync_agent_keys():
    step("Syncing agent API keys")
    subprocess.run(
        ["python3", str(REPO_ROOT / "ansible/scripts/sync_agent_keys.py")],
        check=True,
    )


def load_sites_by_dest(project_id: str | None, site_key: str | None) -> dict[str, list[dict]]:
    data = json.loads(ENRICHED_FILE.read_text())
    sites = data["sites"]
    if project_id:
        sites = [s for s in sites if s["project_id"] == project_id]
    if site_key:
        sites = [s for s in sites if s["site_key"] == site_key]
    if not sites:
        raise SystemExit("No matching sites found.")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for site in sites:
        grouped[site["ssh_dest"]].append(site)
    return grouped


def generate_config(sites: list[dict]) -> str:
    config = {
        "sites": [
            {
                "api_key": s["agent_api_key"],
                "db_path": s["db_path"],
                "retention_days": s.get("retention_days", DEFAULT_RETENTION_DAYS),
            }
            for s in sites
        ]
    }
    return json.dumps(config)


def deploy_to_host(ssh_host: str, agent_path: str, tmpdir: Path):
    config_file = tmpdir / f"{ssh_host}.json"
    service_file = tmpdir / f"{ssh_host}.upmon-agent-cleanup.service"
    timer_file = tmpdir / f"{ssh_host}.upmon-agent-cleanup.timer"

    systemd_path = agent_path.replace("~/", "%h/", 1) if agent_path.startswith("~") else agent_path
    service_file.write_text(CLEANUP_SERVICE.format(agent_path=systemd_path))
    timer_file.write_text(CLEANUP_TIMER)

    systemd_dir = "~/.config/systemd/user"
    step(f"  Creating directories on {ssh_host}")
    subprocess.run(
        ["ssh", ssh_host, f"mkdir -p {agent_path} {systemd_dir}"],
        check=True,
    )
    step(f"  Copying agent script + config to {ssh_host}")
    subprocess.run(
        [
            "scp",
            str(AGENT_SCRIPT),
            f"{ssh_host}:{agent_path}/main.py",
        ],
        check=True,
    )
    subprocess.run(
        ["scp", str(config_file), f"{ssh_host}:{agent_path}/config.json"],
        check=True,
    )
    subprocess.run(
        ["scp", str(service_file), f"{ssh_host}:{systemd_dir}/upmon-agent-cleanup.service"],
        check=True,
    )
    subprocess.run(
        ["scp", str(timer_file), f"{ssh_host}:{systemd_dir}/upmon-agent-cleanup.timer"],
        check=True,
    )
    step(f"  Enabling systemd timer on {ssh_host}")
    subprocess.run(
        [
            "ssh",
            ssh_host,
            "systemctl --user daemon-reload && systemctl --user enable --now upmon-agent-cleanup.timer",
        ],
        check=True,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy upmon-agent to target servers.")
    parser.add_argument("project_id", nargs="?", help="Filter by project ID")
    parser.add_argument("site_key", nargs="?", help="Filter by site key (e.g. dev, prod)")
    return parser.parse_args()


def main():
    args = parse_args()
    sync_agent_keys()

    sites_by_dest = load_sites_by_dest(args.project_id, args.site_key)
    manual_hosts = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for ssh_dest, sites in sites_by_dest.items():
            ssh_host = sites[0]["ssh_host"]
            agent_path = sites[0].get("agent_path")
            config_json = generate_config(sites)

            if not agent_path:
                manual_hosts.append((ssh_host, config_json))
                continue

            config_file = tmpdir / f"{ssh_host}.json"
            config_file.write_text(config_json)

            step(f"Deploying to {ssh_dest}")
            deploy_to_host(ssh_host, agent_path, tmpdir)

    if manual_hosts:
        if MANUAL_DEPLOY_DIR.exists():
            shutil.rmtree(MANUAL_DEPLOY_DIR)
        step("Preparing manual deploy files")
        for ssh_host, config_json in manual_hosts:
            host_dir = MANUAL_DEPLOY_DIR / ssh_host
            host_dir.mkdir(parents=True)
            shutil.copy2(AGENT_SCRIPT, host_dir / "main.py")
            (host_dir / "config.json").write_text(config_json)
            print(f"  {host_dir}/", flush=True)


if __name__ == "__main__":
    main()
