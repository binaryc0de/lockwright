# "Escape room meets Hack The Box": challenge infrastructure research (as of 2026-10-01)

> Research report produced by a sub-agent during planning. The platform/orchestrator team and CTF room authors should read this.

## 1. How established platforms do it

**CTFd.** Challenge types are plugin classes subclassing `BaseChallenge` (create/read/update/delete/attempt/solve/fail); flag types subclass `BaseFlag` with a `compare(flag, submission)` method, registered in a global `FLAG_CLASSES` dict. Built-ins: static (optional case-insensitive) and regex. Wrong-flag submissions are hard rate-limited to 10/min (since 3.8.2 they are logged as a distinct "ratelimited" submission type). Per-team instances come from plugins: **CTFd-whale** (Docker Swarm + frp reverse proxy; each instance gets a unique auto-generated flag and a subdomain or port; players start/renew/destroy with one click; per-user container caps; Redis state), **CTFd-Docker-Challenges**, **ctfd-k8s-challenge**, and **ctfer.io chall-manager** (Pulumi-based, tech-agnostic, janitor for timeouts).

**rCTF (redpwn/OtterSec).** Flag entries use pluggable "flag validation providers" (static default); a challenge solves when any entry validates. The **instancer** integration gives each team an isolated copy on Docker (FastAPI + Traefik + Redis) or Kubernetes (Go operator + Traefik); challenges declare `timeoutMilliseconds`, `extendable`, and an `expose` array (http/https/tcp-ssl), with states stopped/starting/running/stopping/errored. Docs warn: treat challenge images as hostile, set resource limits, run unprivileged, don't mount host paths. **rCDS** `challenge.yaml` is a good packaging model: `flag` (string | file | regex), `containers` (image/build, ports, env, resources), `expose` (tcp port or http subdomain), `provide` (downloadable files).

**klodd (TJCSec)** - per-team instance runner where each challenge is a Kubernetes CRD; instances only exist on demand. **kCTF (Google)** - every TCP connection is forked into a fresh **nsjail** sandbox (user namespaces), with healthcheck containers and an optional proof-of-work wrapper; the stated goal is hosting untrusted vulnerable apps safely. **picoCTF cmgr** - a challenge is a *template*; each instance is generated with its own flag (and sometimes different parameters, e.g. buffer size) so one team's solution doesn't transfer.

**TryHackMe** already uses "rooms": a room = ordered tasks, each with questions/answers (max ~15) and at most one attached VM or downloadable file; players reach VMs (10.x.x.x) via split-tunnel OpenVPN or via the browser-based AttackBox. **Hack The Box** spawns a dedicated machine per user (all users since late 2025), reached via OpenVPN or the browser-based Pwnbox (Parrot); flags are static text files but HTB *rotates* machine flags on reset, and staff explicitly rejected per-instance random flags because they break multi-session play and can't be embedded in binaries/forensic artifacts. **OverTheWire** uses SSH levels where the next level's password *is* the flag. **Root-Me** offers ~140 on-demand VM environments plus 430+ challenges.

## 2. Reference architecture (LAN host)

```
Player PCs (game client + real tools)            Linux host
 +---------------+   HTTPS/WebSocket   +------------------------------------------+
 | 3D game client|<------------------->| Game server  (world state, doors, teams) |
 | nmap/burp/... |                     |   +- Flag/Progress API (rate-limited)    |
 +------+--------+                     |   +- Room Orchestrator ("instancer")     |
        | LAN or per-room WireGuard    |        +- reads room.yaml package        |
        v                              |        +- docker compose -p room-<id>    |
 +---------------+    reverse proxy    |        +- injects FLAG_* env/secrets     |
 | 10.42.<room>.x|<---(Traefik/frp)----+        +- TTL/janitor, extend, reset     |
 | challenge nets|                     |        +- healthchecks                   |
 +---------------+                     | Flag store (per team/instance, hashed)   |
                                       | Static artifact server (provide/ files)  |
                                       | ttyd/wetty per team (optional terminal)  |
                                       +------------------------------------------+
```
Data flow: player opens a prop -> client asks `/rooms/{id}/props/{prop}` -> server returns a *handle* (download URL, host:port, or terminal WS token) and, on first use, asks the orchestrator to start the instance. Player finds flag with real tools -> submits in-game (`POST /flags {team, challenge, value}`) -> server validates against the per-instance flag record -> emits a world event (`door.unlock`, `light.on`) over the existing game transport. Scoring/progress persists for 24/48h rooms; instance TTL is separate from room duration (idle instances are torn down and recreated with the *same* stored flags so multi-session play works, avoiding HTB's objection).

**Room package (rcds/cmgr-inspired `room.yaml`):** metadata + prop list; each prop references a challenge with `kind: file|service|terminal|vm`, `flag: {static|regex|per-instance|checker}`, `provide:` files, `containers:` + `expose:` + `resources:`, `healthcheck:`, `hints:`, `unlocks:` (world effect). This makes rooms authorable by third parties and AI agents and testable with `docker compose` outside the game.

## 3. Challenge category -> in-world prop mapping

| Category | In-room prop / surfacing | Infra | Tier |
|---|---|---|---|
| Crypto / ciphers | Wall writing, safe dial, note in drawer, ciphered radio message | None (static) | Easy-Hard |
| Steganography | Framed painting, poster, cassette/vinyl player, photo on fridge -> downloadable PNG/WAV | File download | Easy-Med |
| Forensics | USB stick, old phone, hard-drive caddy -> disk image, memory dump, .docx, PDF | File download | Med-Hard |
| OSINT (fictional) | Business card, badge, sticky note with handle -> fake intranet/social site hosted in room | HTTP service | Easy-Med |
| Web exploitation | Laptop/kiosk/smart-TV prop -> opens real browser URL on LAN | Container + reverse proxy (per team) | Easy-Hard |
| Reverse engineering | Firmware chip, keypad lock, "legacy app" on a PC -> binary download | File download | Med-Hard |
| Pwn | Server rack / terminal panel -> `nc host port` (nsjail per connection) | Container (nsjail/redpwn jail) | Hard |
| Networking / pcap | Wi-Fi router, network tap, security camera -> pcap download or live service | File or TCP service | Easy-Med |
| Password cracking | Login screen, safe, phone lock -> hash file / shadow dump | File (+ optional service to try password) | Easy-Med |
| Hardware / badge | RFID reader, Arduino, badge printer -> firmware dump, logic-analyzer CSV, serial console via in-game terminal | File or terminal | Med |
| Full box (HTB-style) | Door to "server room" -> VM/large container reachable via WireGuard | Full VM/container network | Hard, 24/48h rooms |

## 4. Flag validation recommendations

- Support four validators (rCTF-style providers): **static**, **regex**, **per-instance** (orchestrator generates `FLAG{...}` with an HMAC of team+challenge+secret and injects via env/secret file at instance start), and **checker script** (room-supplied container that receives submission + team context and returns ok/fail; use for stateful proofs like "the service is patched").
- Use per-instance flags for anything that lives in a container (web/pwn/net); use static flags for binaries, stego and forensic artifacts (HTB's reason). Optionally per-team *artifact generation* (cmgr templating) for file-based challenges when authors provide a generator.
- Store flag hashes (sha256+salt) per team/instance; compare constant-time; keep flags stable across instance restarts within one room session.
- Anti-brute-force: per-team sliding window (e.g. 10 wrong/min like CTFd, with escalating cooldown), log all submissions, soft lockout rather than ban, tie attempts to the authenticated game session, and make in-game feedback binary (correct/incorrect) with no partial matching. Proof-of-work only matters for public cloud later.
- Door unlock is a server-side state transition, never trusted from the client.

## 5. Security isolation recommendations

- One host, two tiers: **rootless Docker** (or Podman) for all challenge containers; `cap_drop: ALL`, `no-new-privileges`, read-only rootfs, pids/memory/CPU limits, no host mounts. Add **gVisor (runsc)** as the runtime for pwn/RCE-by-design challenges (note: runsc + rootless has open issues; test, or run those on a dedicated non-rootless daemon). Use **nsjail/redpwn jail** inside pwn images for per-connection forking. Reserve Firecracker/Kata or full VMs for "full box" rooms that need a real kernel or kernel exploitation.
- Networking: one user-defined bridge network per room instance (`--internal` for backend containers), `icc=false` on the default bridge, only the reverse proxy (Traefik/frp) publishes ports; for the LAN, allocate a port range per room (e.g. 20000+room*100) or subdomains via local DNS. For later cloud and for "full box" rooms, issue per-team **WireGuard** configs (wg-easy or plain wg with AllowedIPs limited to that team's 10.42.x.0/24), mirroring HTB/THM split-tunnel VPN.
- Egress: deny outbound internet from challenge networks (iptables/nftables on the host) so a compromised challenge can't phone out; allow only to the orchestrator healthcheck.
- Janitor: TTL per instance (60-min rooms = room length; 24/48h rooms = idle timeout + extend button), cleanup on room end, cap instances per team and per host.
- In-game terminal: for light challenges embed **xterm.js** in the client UI (or an engine-native terminal panel) talking WebSocket to **ttyd** (C, TLS/basic-auth, origin checking, max clients) or **wetty** (Node, ssh or local shell) spawned per team inside a throwaway container; mint one-time WS tokens from the game server, never expose ttyd directly. A pure fake shell (Hacknet style) is fine for narrative/tutorial props but should not gate real flags.

## 6. Prior art and lessons

- **Hacknet / Uplink / Grey Hack / Bitburner**: Hacknet and Grey Hack get praise for teaching real CLI habits (Grey Hack = persistent MMO with a real-Linux-like desktop); Uplink is the "Hollywood" polished one; Bitburner teaches JS scripting. Lesson: the in-game terminal should feel real, but the differentiator is that the targets *are* real.
- **NSA Codebreaker**: strictly sequential, tiered tasks that unlock one another and mirror a real investigation; sequential gating maps directly to escape-room door progression.
- **Living Security CyberEscape / SANS cyber escape rooms / CMU & ISC2 events**: physical/online awareness escape rooms where "each puzzle represents a vulnerability"; strong on narrative and teamwork, weak on real tooling; several academic Unity-based "Cyber Escape Room" prototypes sit on a cyber range ("Threat Realm") - the closest to this concept, and a Godot XR RSA escape room jam exists.
- **HTB Business CTF 2023 "The Great Escape"** and Cyber Apocalypse show themed storylines over standard challenge categories work at scale.
- Nobody found combines a 3D multiplayer room, props mapped to real services, and player-side real tools; the open-source pieces (rcds packaging, rCTF instancer, kCTF nsjail, ttyd) are all there to assemble.

## Sources
- CTFd flag types: https://docs.ctfd.io/docs/plugins/flag-types/ ; challenge types: https://docs.ctfd.io/docs/plugins/challenge-types/ ; rate limit issue: https://github.com/CTFd/CTFd/issues/2014 ; changelog: https://github.com/CTFd/CTFd/blob/master/CHANGELOG.md
- CTFd-whale: https://github.com/frankli0324/ctfd-whale ; CTFd-Docker-Challenges: https://github.com/offsecginger/CTFd-Docker-Challenges ; ctfd-k8s-challenge: https://github.com/astr0n8t/ctfd-k8s-challenge
- rCTF instancer: https://rctf.osec.io/integrations/instancer/ ; rCDS challenge spec: https://rcds.redpwn.net/en/latest/challenge/
- klodd: https://github.com/TJCSec/klodd ; kube-ctf: https://github.com/DownUnderCTF/kube-ctf ; chall-manager: https://ctfer.io/docs/chall-manager/design/the-need/
- kCTF: https://google.github.io/kctf/introduction.html ; redpwn/jail: https://github.com/redpwn/jail
- picoCTF cmgr: https://github.com/picoCTF/cmgr ; https://docs.picoctf.com/specs/challenge.py.html
- TryHackMe: https://help.tryhackme.com/en/articles/6721845-the-attackbox-explained ; https://help.tryhackme.com/en/articles/8991552-networks-explained-vpn-attackbox-and-security-tips ; https://help.tryhackme.com/en/articles/6495805-room-creation-overview
- Hack The Box: https://help.hackthebox.com/en/articles/5185338-how-to-play-machines-on-hack-the-box ; https://forum.hackthebox.com/t/randomize-flags-per-challenge-instance/297905 ; https://www.hackthebox.com/blog/business-ctf-2023-the-great-escape-recap
- OverTheWire Bandit: https://www.justus.pw/wiki/OverTheWire_Bandit_walkthrough ; Root-Me: https://www.root-me.org/?page=ctf_alltheday&id_salle=29&lang=en
- Isolation: https://www.sitepoint.com/isolate-untrusted-code-rootless-docker-gvisor/ ; https://gvisor.dev/docs/user_guide/networking/ ; https://github.com/google/gvisor/issues/12575 ; https://dev.to/hexshift/securing-docker-networking-limiting-exposure-and-enhancing-isolation-216p ; CTF-as-a-Service paper: https://arxiv.org/pdf/2603.22511
- VPN: https://dev.to/moksh/self-hosted-vpn-in-2026-wireguard-headscale-netbird-and-more-compared-5fln
- Terminals: https://tsl0922.github.io/ttyd/ ; https://github.com/butlerx/wetty
- Games/prior art: https://steamcommunity.com/app/605230/discussions/1/676200171205306668/ ; https://nsa-codebreaker.org/challenge ; https://www.livingsecurity.com/products/cybersecurity-escape-games ; https://federalnewsnetwork.com/reporters-notebook-jason-miller/2019/03/are-escape-rooms-for-cyber-education-a-new-trend-in-government/ ; https://library.iated.org/view/PAPPAS2020CYB ; https://doi.org/10.3390/educsci16010133 ; https://github.com/Umungia/Godot_XR_Jam_2026__Classroom-Escape-Room ; https://opencyberrange.com/
