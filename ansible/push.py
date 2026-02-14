#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

SERVERS = {
    "prod": "sgtent",
}

TARGETS = ["collector", "backend", "frontend"]


def main():
    parser = argparse.ArgumentParser(description="Deploy components via Ansible")
    parser.add_argument("server", choices=SERVERS.keys())
    parser.add_argument("targets", nargs="*", default=TARGETS, choices=TARGETS)
    args = parser.parse_args()

    limit = SERVERS[args.server]
    tags = ",".join(["push-all"] + [f"push-{t}" for t in args.targets])

    print(f"Deploying to {args.server} ({limit}): {' '.join(args.targets)}")
    print(f"Tags: {tags}")
    print()

    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    subprocess.run(
        [
            "ansible-playbook",
            "-i",
            "inventory.yaml",
            "playbooks/*/main.yaml",
            "--limit",
            limit,
            "--tags",
            tags,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
