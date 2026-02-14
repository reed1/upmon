push SERVER *TARGETS:
    #!/usr/bin/env bash
    set -euo pipefail
    git push
    ./ansible/push.py {{SERVER}} {{TARGETS}}
