#!/bin/bash
# start_tunnels.sh — starts both zrok tunnels (backend + frontend) and
# automatically writes the new URLs into every config file that needs them:
#   backend/.env            (PUBLIC_BASE_URL, CORS_ALLOWED_ORIGINS)
#   frontend/.env           (VITE_API_BASE_URL)
#   frontend/vite.config.ts (allowedHosts)
#
# What this does NOT do:
#   - Does not start/restart the backend or frontend dev servers themselves.
#     Start those FIRST (see the manual at the bottom of this repo's chat,
#     or just: backend -> uvicorn, frontend -> npm run dev), THEN run this.
#   - Does not make the URLs permanent. zrok's free tier gives a new random
#     subdomain every time a tunnel restarts -- this script just removes the
#     manual copy-paste-into-3-files step, it can't remove that rotation.
#   - After this script finishes, you still need to restart the backend AND
#     frontend dev servers so they actually read the new .env/config values.
#
# Usage:
#   bash start_tunnels.sh
#
# Requires: backend already running on 127.0.0.1:8000, frontend on
# 127.0.0.1:5173, before you run this (it tunnels to whatever's there).

set -e

ZROK="/c/Users/Gulabaji/zrok/zrok2.exe"
BACKEND_LOG="/tmp/zrok_backend.log"
FRONTEND_LOG="/tmp/zrok_frontend.log"
BACKEND_ENV="backend/.env"
FRONTEND_ENV="frontend/.env"
VITE_CONFIG="frontend/vite.config.ts"

if [ ! -f "$ZROK" ]; then
  echo "ERROR: zrok2.exe not found at $ZROK"
  echo "If you moved/reinstalled it, update the ZROK path at the top of this script."
  exit 1
fi

echo "Stopping any previous zrok tunnels..."
taskkill //F //IM zrok2.exe > /dev/null 2>&1 || true
sleep 1

echo "Starting backend tunnel (127.0.0.1:8000)..."
rm -f "$BACKEND_LOG"
nohup "$ZROK" share public http://127.0.0.1:8000 > "$BACKEND_LOG" 2>&1 &

echo "Starting frontend tunnel (127.0.0.1:5173)..."
rm -f "$FRONTEND_LOG"
nohup "$ZROK" share public http://127.0.0.1:5173 > "$FRONTEND_LOG" 2>&1 &

echo "Waiting for zrok to print tunnel URLs..."

# Extract the first *.shares.zrok.io hostname from each log, stripping ANSI
# escape codes and the TUI's box-drawing characters first (zrok's share
# command prints an interactive-looking box even when output is redirected
# to a file, not a plain URL line).
extract_url() {
  local log_file="$1"
  sed -E 's/\x1b\[[0-9;?]*[a-zA-Z]//g' "$log_file" \
    | grep -oE '[a-z0-9]+\.shares\.zrok\.io' \
    | head -1
}

# Poll instead of a single fixed sleep: how long zrok takes to establish a
# tunnel and print its URL varies run-to-run (auth handshake, network, how
# fast the just-killed previous zrok2.exe process actually released the
# port) -- a flat `sleep 5` was observed to sometimes fire the extraction
# before either log had anything in it yet, even though the tunnel came up
# fine a couple seconds later. Retries every 1s for up to 20s before giving
# up for real.
BACKEND_HOST=""
FRONTEND_HOST=""
for i in $(seq 1 20); do
  [ -z "$BACKEND_HOST" ] && BACKEND_HOST=$(extract_url "$BACKEND_LOG")
  [ -z "$FRONTEND_HOST" ] && FRONTEND_HOST=$(extract_url "$FRONTEND_LOG")
  if [ -n "$BACKEND_HOST" ] && [ -n "$FRONTEND_HOST" ]; then
    break
  fi
  sleep 1
done

if [ -z "$BACKEND_HOST" ]; then
  echo "ERROR: Could not find backend tunnel URL in $BACKEND_LOG after 20s."
  echo "Check that file manually, or that your backend is actually running on port 8000."
  exit 1
fi
if [ -z "$FRONTEND_HOST" ]; then
  echo "ERROR: Could not find frontend tunnel URL in $FRONTEND_LOG after 20s."
  echo "Check that file manually, or that your frontend is actually running on port 5173."
  exit 1
fi

BACKEND_URL="https://${BACKEND_HOST}"
FRONTEND_URL="https://${FRONTEND_HOST}"

echo ""
echo "Backend tunnel:  $BACKEND_URL"
echo "Frontend tunnel: $FRONTEND_URL"
echo ""

# --- Update backend/.env ---
sed -i -E "s#^PUBLIC_BASE_URL=.*#PUBLIC_BASE_URL=${FRONTEND_URL}#" "$BACKEND_ENV"
sed -i -E "s#^CORS_ALLOWED_ORIGINS=.*#CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,${FRONTEND_URL}#" "$BACKEND_ENV"
echo "Updated $BACKEND_ENV"

# --- Update frontend/.env ---
sed -i -E "s#^VITE_API_BASE_URL=.*#VITE_API_BASE_URL=${BACKEND_URL}#" "$FRONTEND_ENV"
echo "Updated $FRONTEND_ENV"

# --- Update frontend/vite.config.ts allowedHosts ---
sed -i -E "s#allowedHosts: \[.*\]#allowedHosts: ['${FRONTEND_HOST}']#" "$VITE_CONFIG"
echo "Updated $VITE_CONFIG"

echo ""
echo "Done. Now restart BOTH the backend and frontend dev servers so they"
echo "pick up these new values -- Ctrl+C each one, then start it again."
echo ""
echo "Phone/officer link to share once both are restarted:"
echo "  $FRONTEND_URL"
