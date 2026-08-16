#!/usr/bin/env bash
#
# Deploy Document Zero to doczero.epstein-data.com.
#
# THE HOST IS LIVE. epstein-data.com serves roughly 15,000 people a day from
# this box. Every step below is either read-only or confined to paths this
# project owns, and the script refuses to touch anything else.
#
# What it will never do:
#   - write anywhere under /opt/datasette-data or /mnt/HC_Volume_*
#   - edit /etc/nginx/sites-enabled/datasette or contribute-epstein-data
#   - restart nginx, or restart or stop any other service
#   - install packages, or start a new long-running process
#
# Usage:
#   scripts/deploy.sh check     read-only: what is there now, what would change
#   scripts/deploy.sh files     rsync the static site only (no nginx changes)
#   scripts/deploy.sh nginx     install the vhost, validate, and RELOAD nginx
#   scripts/deploy.sh           check + files  (the safe default)
#
set -euo pipefail

HOST="${DZ_HOST:-root@178.156.220.163}"
REMOTE_ROOT="/opt/doczero/site"
VHOST_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/doczero.nginx"
LOCAL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN="doczero.epstein-data.com"

# Exactly what the site is. Everything else in the repo — the ledger, the
# pipeline, the tests, the git history — stays off the public server.
PAYLOAD=(index.html data.js llms.txt newsdesk.db fonts api)

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ssh_() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" "$@"; }

guard() {
  case "$REMOTE_ROOT" in
    /opt/datasette-data*|/mnt/HC_Volume_*|/etc/*|/var/www/*|/|/root*)
      echo "REFUSING: $REMOTE_ROOT is not a path this project owns." >&2; exit 1;;
  esac
}

cmd_check() {
  say "DNS"
  if getent hosts "$DOMAIN" >/dev/null 2>&1; then
    echo "  $DOMAIN resolves: $(getent hosts "$DOMAIN" | awk '{print $1}' | tr '\n' ' ')"
  else
    echo "  $DOMAIN does NOT resolve yet."
    echo "  Add a PROXIED record for 'doczero' in the epstein-data.com zone at"
    echo "  Cloudflare, pointing at the same origin as epstein-data.com."
    echo "  Nothing else here depends on it; files and vhost can go up first."
  fi

  say "Host"
  ssh_ '
    echo "  free:   $(free -m | awk "/Mem:/{print \$7\" MB available of \"\$2\" MB\"}")"
    echo "  disk:   $(df -h / | awk "NR==2{print \$4\" free\"}")"
    echo "  nginx:  $(nginx -v 2>&1)"
    echo "  vhosts: $(ls /etc/nginx/sites-enabled/ | tr "\n" " ")"
    echo "  cert:   $(openssl x509 -in /etc/ssl/cloudflare-origin.pem -noout -ext subjectAltName 2>/dev/null | tail -1 | tr -s " ")"
    printf "  site:   "; [ -d '"$REMOTE_ROOT"' ] && du -sh '"$REMOTE_ROOT"' || echo "not deployed yet"
    printf "  vhost:  "; [ -e /etc/nginx/sites-enabled/doczero ] && echo "installed" || echo "not installed"
  '

  say "Payload"
  ( cd "$LOCAL" && du -ch "${PAYLOAD[@]}" 2>/dev/null | tail -1 | sed 's/^/  /' )

  say "Dry run (what would change)"
  ( cd "$LOCAL" && rsync -az --delete --dry-run --itemize-changes \
      "${PAYLOAD[@]}" "$HOST:$REMOTE_ROOT/" 2>&1 | sed 's/^/  /' | head -30 ) || true
}

cmd_files() {
  guard
  say "Creating $REMOTE_ROOT (owned by this project, nothing else lives there)"
  ssh_ "mkdir -p '$REMOTE_ROOT'"

  say "Syncing $(printf '%s ' "${PAYLOAD[@]}")"
  ( cd "$LOCAL" && rsync -az --delete --itemize-changes \
      "${PAYLOAD[@]}" "$HOST:$REMOTE_ROOT/" | sed 's/^/  /' )

  ssh_ "chown -R www-data:www-data '$REMOTE_ROOT' && chmod -R a+rX '$REMOTE_ROOT'"
  say "Deployed"
  ssh_ "du -sh '$REMOTE_ROOT'; find '$REMOTE_ROOT' -type f | wc -l | xargs echo '  files:'"
}

cmd_nginx() {
  guard
  [ -f "$VHOST_SRC" ] || { echo "missing $VHOST_SRC" >&2; exit 1; }

  say "Installing vhost as a NEW file (existing configs untouched)"
  ssh_ "test ! -e /etc/nginx/sites-available/datasette.dz-backup || true"
  scp -q "$VHOST_SRC" "$HOST:/etc/nginx/sites-available/doczero"
  ssh_ "ln -sfn /etc/nginx/sites-available/doczero /etc/nginx/sites-enabled/doczero"

  say "Validating (read-only; this is where a mistake gets caught)"
  if ! ssh_ "nginx -t"; then
    say "INVALID — removing the symlink and leaving nginx exactly as it was"
    ssh_ "rm -f /etc/nginx/sites-enabled/doczero"
    ssh_ "nginx -t" && echo "  confirmed: config is valid again, nothing was reloaded"
    exit 1
  fi

  say "Reloading (SIGHUP — workers finish in-flight requests; NOT a restart)"
  ssh_ "systemctl reload nginx && sleep 1 && systemctl is-active nginx"

  say "Verifying the LIVE SITE is unaffected"
  ssh_ 'curl -sS -o /dev/null -w "  epstein-data.com -> HTTP %{http_code} in %{time_total}s\n" \
        --resolve epstein-data.com:443:127.0.0.1 https://epstein-data.com/ 2>/dev/null \
        || curl -sS -o /dev/null -w "  epstein-data.com (via CF) -> HTTP %{http_code}\n" https://epstein-data.com/'

  say "Verifying the new host"
  ssh_ "curl -sS -o /dev/null -w '  $DOMAIN -> HTTP %{http_code}\n' https://$DOMAIN/ || \
        echo '  not yet reachable — expected until the Cloudflare DNS record exists'"
}

case "${1:-default}" in
  check)   cmd_check ;;
  files)   cmd_check; cmd_files ;;
  nginx)   cmd_nginx ;;
  default) cmd_check; cmd_files
           say "Not touching nginx. Run 'scripts/deploy.sh nginx' to install the"
           echo "vhost and reload — that is the only step that affects the live server." ;;
  *) echo "usage: $0 [check|files|nginx]" >&2; exit 2 ;;
esac
