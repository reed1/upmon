#!/bin/bash
set -e

cd "$(dirname "$0")"

SERVER="${1:?Usage: push.sh <server> [targets...]}"
shift

case "$SERVER" in
    prod) LIMIT="sgtent" ;;
    *) echo "Error: Unknown server '$SERVER'. Valid: prod"; exit 1 ;;
esac

TARGETS="${@:-collector backend frontend}"

TAGS="push-all"
for target in $TARGETS; do
    TAGS="$TAGS,push-$target"
done

echo "Deploying to $SERVER ($LIMIT): $TARGETS"
echo "Tags: $TAGS"
echo

ansible-playbook -i inventory.yaml playbooks/*/main.yaml --limit "$LIMIT" --tags "$TAGS"
