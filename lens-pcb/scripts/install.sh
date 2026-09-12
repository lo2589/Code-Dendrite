#!/bin/bash
# Install dsh-cdd-lens-pcb into the DeepSeek Harness `web` profile and restart it.
#
# `link:`, not `file:`. pnpm treats `file:` as a HARD COPY: the profile gets a
# snapshot of this directory at install time, every later edit here is invisible
# to the running harness, and a restart faithfully reloads the stale copy. That
# reads exactly like "my change had no effect" and is unfalsifiable from the
# page. `link:` symlinks the working tree, so edit → restart → live.
#
# /health echoes the resolved path back, which is how you confirm the running
# harness is serving THIS checkout and not another one.
set -euo pipefail

DSH_REPO="${DSH_REPO:-/Users/a1/Workspace/WORKSPACE/deepseek-harness}"
PROFILE="${PROFILE:-web}"
PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${DSH_PORT:-3080}"

export PATH="$HOME/Workspace/node-v22.18.0-darwin-arm64/bin:$PATH"

echo "==> plugin root: $PLUGIN_ROOT"
cd "$DSH_REPO"

# Remove first so a re-run replaces rather than duplicates the entry. A missing
# entry is the normal case on a first install, so its failure is not an error.
node --import tsx/esm apps/cli/src/bin.ts plugin --profile "$PROFILE" remove dsh-cdd-lens-pcb >/dev/null 2>&1 || true
node --import tsx/esm apps/cli/src/bin.ts plugin --profile "$PROFILE" add "link:$PLUGIN_ROOT"

echo "==> restarting harness"
"$HOME/Workspace/WORKSPACE/harness/deepseek.sh" restart

echo "==> waiting for /health"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/plugins/cdd-lens-pcb/health" 2>/dev/null; then
    echo
    echo "==> ok — open http://127.0.0.1:$PORT and look bottom-right"
    exit 0
  fi
  sleep 1
done

echo "!! /health never answered. The host half did not mount, or the route did not register." >&2
echo "   logs: deepseek logs" >&2
exit 1
