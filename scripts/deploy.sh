#!/usr/bin/env bash
set -euo pipefail
SERVICE_NAME=${1:-unknown}
BRANCH=${2:-main}
echo "Deploying ${SERVICE_NAME} from branch ${BRANCH}"
