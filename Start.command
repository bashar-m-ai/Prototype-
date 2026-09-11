#!/bin/zsh
cd -- "$(dirname -- "$0")"
STORIES_NODE='/Users/shabbarsmacbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
if [[ ! -x "$STORIES_NODE" ]]; then STORIES_NODE="$(command -v node)"; fi
if [[ -z "$STORIES_NODE" ]]; then
  echo 'Please install Node.js 24 or newer to run Service Stories.'
  read '?Press Enter to close.'
  exit 1
fi
if /usr/bin/curl --silent --max-time 1 http://127.0.0.1:4188/ >/dev/null; then
  /usr/bin/open http://127.0.0.1:4188
  exit 0
fi
(sleep 1; /usr/bin/open http://127.0.0.1:4188) &
"$STORIES_NODE" server.mjs
