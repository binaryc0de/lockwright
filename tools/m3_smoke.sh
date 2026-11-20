#!/usr/bin/env bash
# M3 end-to-end smoke test (ADR-0018), all on this machine:
#   1. the platform starts (it spawns game servers itself)
#   2. a session is created over HTTP; Alice joins with the join code and
#      plays solution steps 0-8 (the server checks her single-use join ticket)
#   3. the flag is captured: with Docker, by attacking the real intranet
#      container with curl (login + IDOR); without Docker, computed from the
#      platform secret (flag checking is still real)
#   4. the game server is killed; the platform restarts it from its snapshot
#   5. Bob joins with the code and finishes the room with the captured flag;
#      the platform records the win
#   6. a wrong join code is refused
# Exit 0 only if every step behaves. Usage: tools/m3_smoke.sh
set -uo pipefail
cd "$(dirname "$0")/.."
GODOT="${GODOT:-godot}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/escapebox-m3-XXXXXX")"
HTTP=$((18100 + RANDOM % 800))
GP=$((27800 + RANDOM % 150))
CP=$((23000 + RANDOM % 900))
URL="http://127.0.0.1:$HTTP"
FAIL=0
PIDS=()
say() { printf '== %s\n' "$*"; }
bad() { printf 'FAIL: %s\n' "$*"; FAIL=1; }
cleanup() { for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null; done; wait 2>/dev/null; }
trap cleanup EXIT

say "workdir $WORK"
go build -o "$WORK/platform" ./platform/cmd/platform || exit 1
"$WORK/platform" -addr "127.0.0.1:$HTTP" -data "$WORK/data" -rooms game/rooms -game game -godot "$GODOT" \
	-advertise 127.0.0.1 -public-url "http://127.0.0.1:$HTTP" -game-ports "$GP-$((GP + 10))" -challenge-ports "$CP-$((CP + 20))" \
	-test-trust-positions > "$WORK/platform.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 40); do curl -fs "$URL/healthz" >/dev/null && break; sleep 0.25; done
curl -fs "$URL/healthz" >/dev/null || { bad "platform did not start (see $WORK/platform.log)"; exit 1; }
DOCKER=0; grep -q '"challenges":true\|challenges=true' "$WORK/platform.log" && DOCKER=1
say "platform up on $URL (docker challenges: $DOCKER)"

S=$(curl -fs -X POST -H 'Content-Type: application/json' "$URL/api/sessions" -d '{"room_id":"night_shift"}') || { bad "create session"; exit 1; }
SID=$(jq -r .session_id <<<"$S"); CODE=$(jq -r .invite_code <<<"$S")
say "session $SID, join code $CODE"

bot() { # $1 log, $2 name, then extra args
	local log=$1 name=$2; shift 2
	"$GODOT" --headless --path game -- --join "$URL" --code "$CODE" --name "$name" --bot "$@" > "$WORK/$log" 2>&1
}

say "Alice plays steps 0-8"
bot alice.log Alice --bot-steps 0-8; rc=$?
[ $rc -eq 0 ] || bad "Alice exited $rc"

say "capture the flag"
CARD=$(grep -o 'BOT: challenge intranet url=[^ ]*' "$WORK/alice.log" | tail -1 | sed 's/.*url=//')
if [ $DOCKER -eq 1 ] && [ -z "$CARD" ]; then
	say "waiting for the challenge container (a first run builds the image)"
	bot watcher.log Watcher --bot-steps 1-0 --bot-wait-card
	PLAYERS=3  # the watcher joined too
	CARD=$(grep -o 'BOT: challenge intranet url=[^ ]*' "$WORK/watcher.log" | tail -1 | sed 's/.*url=//')
fi
if [ $DOCKER -eq 1 ] && [ -n "$CARD" ]; then
	case "$CARD" in */ctf/*) ;; *) bad "the card does not go through the platform's /ctf/ proxy: $CARD";; esac
	say "attacking $CARD with curl (login + IDOR, through the platform proxy)"
	curl -fs -c "$WORK/jar" -b "$WORK/jar" -o /dev/null -X POST --data-urlencode "username=mreyes" --data-urlencode 'password=Kestrel#2019' "${CARD}login" || bad "intranet login failed"
	curl -fs -b "$WORK/jar" "${CARD}tickets/view?id=1042" | grep -q "FLAG{" && bad "flag on mreyes's own ticket"
	FLAG=$(curl -fs -b "$WORK/jar" "${CARD}tickets/view?id=1040" | grep -o 'FLAG{[0-9a-f]*}' | head -1)
else
	[ $DOCKER -eq 1 ] && bad "Docker is up but Alice never saw a connection card"
	say "no Docker: computing the flag from the platform secret"
	FLAG=$(go run ./platform/cmd/flagcalc -secret "$WORK/data/secret.key" -session "$SID" -challenge intranet)
fi
[ -n "$FLAG" ] || bad "no flag captured"

if [ $DOCKER -eq 1 ]; then
	say "check the live container's hardening"
	CID=$(docker ps -q --filter "label=escapebox.session=$SID" | head -1)
	if [ -z "$CID" ]; then
		bad "no running challenge container for session $SID"
	else
		docker inspect "$CID" > "$WORK/container.json"
		jq -e '.[0].HostConfig | (.CapDrop == ["ALL"]) and (.SecurityOpt | index("no-new-privileges:true") != null) and .ReadonlyRootfs and (.Privileged | not) and (.Memory == 268435456) and (.NanoCpus == 500000000) and (.PidsLimit == 128) and ((.PortBindings // {}) | length == 0)' "$WORK/container.json" >/dev/null || bad "container hardening not as specified: $(jq -c '.[0].HostConfig | {CapDrop,SecurityOpt,ReadonlyRootfs,Privileged,Memory,NanoCpus,PidsLimit,PortBindings}' "$WORK/container.json")"
		[ "$(jq -r '.[0].Config.User' "$WORK/container.json")" = "65534:65534" ] || bad "container does not run as uid 65534"
		NET=$(jq -r '.[0].HostConfig.NetworkMode' "$WORK/container.json")
		[ "$(docker network inspect -f '{{.Internal}}' "$NET")" = "true" ] || bad "session network $NET is not internal (egress possible)"
		jq -r '.[0].Config.Env[]' "$WORK/container.json" | grep -q "^FLAG=" || bad "flag not injected"
		docker image inspect "$(jq -r '.[0].Config.Image' "$WORK/container.json")" | grep -q "FLAG{" && bad "a flag is baked into the image"
	fi
fi

say "kill the game server; the platform restarts it from the snapshot"
GPID=$(pgrep -f -- "--session $SID" | head -1)
if [ -n "$GPID" ]; then
	kill -9 "$GPID"
	for _ in $(seq 1 60); do grep -q "restarting from the last snapshot" "$WORK/platform.log" && break; sleep 0.25; done
	grep -q "restarting from the last snapshot" "$WORK/platform.log" || bad "platform did not restart the game server"
	for _ in $(seq 1 60); do [ "$(grep -c 'escapebox server: restored snapshot' "$WORK/platform.log")" -ge 1 ] && break; sleep 0.25; done
	grep -q "escapebox server: restored snapshot" "$WORK/platform.log" || bad "restarted server did not restore the snapshot"
else
	bad "no game server process found for session $SID"
fi

say "Bob finishes with the captured flag"
bot bob.log Bob --bot-steps 9-end --bot-flag "$FLAG" --bot-wait-win; rc=$?
[ $rc -eq 0 ] || bad "Bob exited $rc"
for _ in $(seq 1 20); do curl -fs "$URL/api/sessions/$SID" | jq -e '.won == true and .status == "finished"' >/dev/null && break; sleep 0.25; done
curl -fs "$URL/api/sessions/$SID" | jq -e '.won == true and .status == "finished" and (.players | length) == '"${PLAYERS:-2}" >/dev/null || bad "platform did not record the win: $(curl -fs "$URL/api/sessions/$SID")"
grep -q "flag attempt.*accepted=true" "$WORK/platform.log" || bad "no accepted flag attempt logged"
grep -qF -- "$FLAG" "$WORK/platform.log" && bad "the flag value appears in the platform log"

say "a wrong join code is refused"
"$GODOT" --headless --path game -- --join "$URL" --code ZZZZZZ --name Mallory --bot > "$WORK/mallory.log" 2>&1; rc=$?
[ $rc -eq 3 ] || bad "Mallory exited $rc, want 3"

if [ $DOCKER -eq 1 ]; then
	say "challenge torn down after the win"
	for _ in $(seq 1 40); do [ -z "$(docker ps -aq --filter "label=escapebox.session=$SID")" ] && break; sleep 0.25; done
	[ -z "$(docker ps -aq --filter "label=escapebox.session=$SID")" ] || bad "challenge container still exists after the win"
	[ -z "$(docker network ls -q --filter "label=escapebox.session=$SID")" ] || bad "session network still exists after the win"
fi

if [ $FAIL -eq 0 ]; then say "PASS (logs in $WORK)"; else say "FAILED (logs in $WORK)"; fi
exit $FAIL
