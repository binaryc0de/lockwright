#!/usr/bin/env bash
# The public switch (ADR-0029): publishes the escapebox site to the internet
# with Tailscale Funnel while you host, and takes it off again. Only the
# platform's HTTPS site is exposed (lobby, browser game, game connections,
# CTF challenges through /ctf/); nothing else on this machine is.
#   tools/public.sh on       anyone with the link can open the site
#   tools/public.sh off      back to your tailnet only
#   tools/public.sh status
# Needs the always-on service (tools/install-service.sh) on PLATFORM_PORT.
set -euo pipefail
PORT="${PLATFORM_PORT:-8090}"
NAME="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//')"
[ -n "$NAME" ] && [ "$NAME" != "null" ] || { echo "Tailscale is not up: run 'sudo tailscale up' first"; exit 1; }

case "${1:-status}" in
on)
	curl -sf "http://127.0.0.1:$PORT/healthz" >/dev/null || { echo "the escapebox platform is not running on :$PORT (tools/install-service.sh)"; exit 1; }
	if ! tailscale funnel --bg --https=443 "http://127.0.0.1:$PORT"; then
		echo "Funnel could not start. The first time, Tailscale asks you to allow Funnel for this machine: follow the link it printed, then run this again."
		exit 1
	fi
	echo "== PUBLIC: https://$NAME/  (anyone with the link). Turn it off with: tools/public.sh off"
	;;
off)
	tailscale funnel --https=443 off >/dev/null 2>&1 || true
	# Keep the site on the tailnet (HTTPS for your own devices).
	tailscale serve --bg --https=443 "http://127.0.0.1:$PORT" >/dev/null
	echo "== private again: https://$NAME/ works only on your tailnet"
	;;
status)
	if tailscale funnel status 2>/dev/null | grep -qi "funnel on"; then
		echo "PUBLIC: https://$NAME/ (anyone with the link)"
	else
		echo "private: https://$NAME/ (tailnet only). To make it public: $0 on"
	fi
	tailscale funnel status 2>/dev/null || true
	;;
*) echo "usage: $0 on|off|status"; exit 2 ;;
esac
