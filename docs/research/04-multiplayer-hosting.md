# Multiplayer architecture and hosting research (as of 2026-10-01)

> Research report produced by a sub-agent during planning. Cloud prices and free tiers change; re-verify before committing money.

## Recommended architecture

```
                     +------------------------ Platform (web backend) ------------------------+
  PC client --HTTPS-->  REST: auth, teams, room catalog, bookings, times, hints log, leaderboards |
  (Godot)             |  WS:   lobby presence, "session ready", team chat/notifications          |
      |               |  Postgres (truth)   Redis (presence, ephemeral)   Session Manager         |
      |               +---------------+-------------------------------------------------------+
      |                               | spawns / allocates / tears down
      |                               v
      |        +--------- Game server fleet (one headless process per session) ---------+
      +-UDP/ENet-->  room package loaded as content; authoritative puzzle state machine   |
   (or WebSocket)  |  periodic snapshot -> Postgres (JSONB) + event log; restore on start  |
                   +----------------------------------------------------------------------+
  Voice: Discord (phase 1-2) -> optional in-game Opus later
```

## 1) Multiplayer architecture

**Pick an authoritative dedicated server from day one**, even on the LAN. Co-op puzzle genre peers mostly use P2P/listen-server over Steam relay (Escape Simulator offers "Steam as VPN" relayed hosting vs legacy direct P2P; We Were Here is 2-player P2P), but they have no 24-48h persistent sessions. Long rooms are the deciding factor: the session must outlive any single player's PC, so the "host" must be a headless process you control. Host-migration is the thing you most want to avoid writing; a dedicated server makes it unnecessary. Relay services (Steam Datagram Relay) only apply if you ship on Steam.

**Shortcuts that are fine for slow-paced co-op** (no prediction, no rollback, no lag compensation):
- Server tick 10-20 Hz; player transforms replicated unreliably, interpolated on clients. Players locally move their own avatar immediately (client-authoritative movement, server sanity-checks only). Nobody cares about 100 ms of avatar lag in an escape room.
- **All puzzle state is a set of server-side state machines** (lock: `closed->open`, dial values, lever positions, inventory). Clients send *intents* via reliable RPC ("I pull lever 3", "I pick up key K"); the server validates, mutates, and broadcasts the new state as replicated properties. Never let clients write puzzle state directly.
- **Pickup conflicts**: first reliable RPC to arrive wins; server replies accept/deny; losers see a short "already taken" feedback. Same pattern for shared inventory (a server-owned list; "give to player" is an intent).
- **Late joiners / rejoin**: on connect, the server sends a full state snapshot (the serialized state-machine table + inventory + positions), then the client subscribes to deltas. This is exactly the same serialization you use for DB persistence, so build it once. Godot 4's `MultiplayerSynchronizer` handles primitives; for the puzzle table, hand-serialize to a dictionary/JSON (Rivet's writeup notes this gap).
- Engine choice: Godot 4.6+ high-level multiplayer (ENet over UDP, dedicated-server export mode strips rendering, runs `--headless`) is "entirely adequate" for 2-32 player co-op. Rooms-as-packages map well to Godot PCK packs loaded at runtime.
- **Voice**: Phase 1-2 just say "use Discord" (zero cost, zero moderation burden). If you want in-game later: Vivox (free up to 5,000 PCU, Unity-first but has a C SDK), Photon Voice, or a DIY Opus-over-your-own-UDP channel. Avoid WebRTC complexity until you have users.

## 2) Platform layer and session management

- **Backend**: Go (single static binary, trivial to run on a LAN box and in a container) or Node/TypeScript. Postgres is the only source of truth; Redis optional until phase 3 (use Postgres `LISTEN/NOTIFY` or in-process pub/sub first).
- **Client talks to**: REST (login -> JWT, catalog, book/start, history) + one WebSocket (lobby presence, "your session is ready at host:port + join token") + the game transport (ENet/UDP) to the session server. The session server validates the join token against the backend (one HTTP call).
- **Session Manager** is a small component: on "start", it spawns `escape-server --room=pkg --session=id --port=N` (process or container), registers host:port in Postgres, and tears it down on completion/idle. This is the seam you later replace with Agones/Edgegap.
- **Persistence for 24/48h rooms**: the server writes a snapshot (JSONB) every N seconds *and* on every puzzle-state change (they're rare, so just write them all), plus an append-only `session_events` table (who did what, hint requests). On restart/restore, load the latest snapshot and resume. The process can be killed freely; "the session" is a DB row. **Idle sessions should not run**: when no players are connected for ~5 min, stop the process; the backend restarts it on the next join (cold start of a headless Godot server is a couple of seconds). This is what makes 48h rooms cost nothing while nobody is playing and lets teammates progress asynchronously. Keep a 60-min room's timer in the DB too (start timestamp, pause accounting), never only in process memory.
- Nakama (Apache-2, self-host) gives you accounts, leaderboards, groups, and match state in one box if you prefer not to write the platform layer; Heroic Cloud managed starts around $600/mo, so self-host only.

## 3) LAN phase

- **Discovery**: just type an IP first; then add a UDP broadcast "who's hosting?" on game-port+1 (10 lines of code, works on every home router), optionally mDNS (`_escape._udp.local`) via Avahi. Both fail across VLANs, which is fine.
- **Running**: systemd unit (`Restart=always`, `DynamicUser`) for backend + one `escape-server@.service` template instance per session, or docker-compose (backend + postgres + a `server` image the manager spawns via the Docker socket). Compose is closer to the cloud phase, so prefer it.
- **Client distribution**: backend serves `/download/` with the client zip + a `version.json`; a tiny launcher (or the client itself) checks the version. Caddy in front gives you this plus TLS.
- **TLS on LAN**: plain HTTP is acceptable for phase 1; if you want HTTPS, `mkcert` with the root CA installed on each LAN PC, or Caddy's internal CA. The game transport (ENet) is unencrypted; fine on LAN, acceptable inside a Tailscale tunnel (WireGuard-encrypted).
- **Ports**: 443/80 backend, 7777/udp + one port per concurrent session (e.g. 7777-7800/udp); backend WS shares 443.

## 4) Cloud phase: 2026 reality check

| Option | 2026 status | Fit |
|---|---|---|
| **Oracle Always Free** | ARM cut to **2 OCPU / 12 GB** (enforced Aug 18 2026; over-limit instances terminated). Still free, but "out of host capacity" errors are chronic unless you upgrade to PAYG. | Best free option if you can grab capacity; 2/12 runs backend+Postgres+several sessions. |
| **GCP e2-micro** | Always free (2 shared vCPU, 1 GB, US regions) | Backend only; too small for game servers. |
| **AWS / Azure** | AWS moved to credit model (Jul 2025), Azure B1s is 12 months | Not long-term free. |
| **Hetzner** | Prices up Jun 15 2026: CX23 (2 vCPU/4 GB) **EUR 5.49/mo**, CAX11 ARM EUR 5.99, CX33 EUR 8.49 (EU; US entry is $20.49) | Best value once paying; one CX33 handles dozens of idle-stoppable sessions. |
| **Fly.io** | No free tier for new signups (trial credit only); pay-per-second | Nice DX, UDP supported, but dearer than Hetzner. |
| **Railway / Render** | Railway: $5 one-time trial then $5/mo Hobby; Render free web services spin down | OK for the backend only; no UDP. |
| **Cloudflare Tunnel** | Public hostnames = HTTP/HTTPS/WebSocket only; TCP needs `cloudflared` on every client; **UDP not supported publicly** (open issue since 2022; Spectrum UDP is Enterprise) | Great for the web backend; **not** for the ENet game port unless you switch the transport to WebSocket. |
| **Cloudflare Workers / DO / D1** | Free: 100k req/day, DO on SQLite, D1 5 GB | Tempting for the platform layer (a Durable Object per session is a natural fit), but adds a second runtime; defer. |
| **Tailscale** | Personal plan free: **6 users, unlimited devices**, node sharing, UDP works | Perfect for "friends-only" intermediate step. |
| **Edgegap** | Free: 1 app, 1.5 vCPU/3 GB, 1 concurrent deployment, **60-min cap**; PAYG $0.00115/vCPU-min, no charge when idle | Good later for 60-min rooms; the 60-min cap and single deployment make the free tier a demo only. |
| **Hathora** | **Shut down May 5 2026** (acquired by Fireworks AI) | Dead; avoid. |
| **Agones** | Free software, but needs a k8s cluster (3 nodes recommended) + ops time | Overkill until many concurrent sessions. |
| **PlayFab** | Multiplayer Servers have a small free allowance but Azure-only, Windows-centric | Poor fit. |

**Intermediate step recommendation: keep hosting at home.** Expose the *web backend* via Cloudflare Tunnel (free TLS, no open ports). For the *game transport*, either (a) have every player install Tailscale and share the server node (free, UDP works, zero port forwarding; friends need a Tailscale account; quarantined-by-default sharing is safe), or (b) make the game transport WebSocket-capable (Godot has `WebSocketMultiplayerPeer`; at 10-20 Hz for a puzzle game, TCP head-of-line blocking is irrelevant) so it also rides the Cloudflare Tunnel. Option (b) is the better investment because it removes the "install Tailscale" friction and the same build works on any cloud. Keep ENet for LAN, WebSocket for remote; both plug into the same `MultiplayerAPI`.

## 5) Progression (simplest -> scalable)

1. **LAN**: docker-compose on the Linux box; Session Manager spawns server processes/containers; Postgres snapshots.
2. **Tunnel**: same box + Cloudflare Tunnel for HTTPS/WSS + Tailscale or WS transport for game traffic. Cost: EUR 0.
3. **Single VPS**: Hetzner CX33 (~EUR 8.49) or Oracle 2/12 if obtainable; identical compose file; sessions are still containers on one host. With idle-stop, one box serves far more than it looks.
4. **Fleet**: when CPU is the limit, swap the Session Manager's backend for Edgegap PAYG (only 60-min rooms; long rooms stay on your VPS with idle-stop) or Agones on a small k3s/Hetzner cluster. Only then.

## Pitfalls
- Oracle free capacity scraping and the Aug 2026 cut: don't plan on 4/24 any more.
- Cloudflare Tunnel will not carry UDP; decide ENet-vs-WebSocket early (support both).
- Hetzner's US regions are 3-4x the EU price; pick Falkenstein/Helsinki if latency allows.
- Don't keep long-room timers/state only in RAM; design the server to be killable from day one.
- Fly.io per-machine prices came from a confusing calculator parse; verify on the pricing page before relying on them.

## Sources
- https://news.ycombinator.com/item?id=49183750 (Oracle free-tier cut)
- https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- https://edgegap.com/resources/pricing
- https://gameye.com/gameye-vs-hathora/ and https://www.thegamer.com/stormgate-going-offline-server-provider-bought-out-ai/ (Hathora shutdown)
- https://tailscale.com/pricing and https://tailscale.com/docs/use-cases/personal-or-at-home-use/share-private-game-server
- https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/routing-to-tunnel/protocols/ and https://github.com/cloudflare/cloudflared/issues/964
- https://developers.cloudflare.com/durable-objects/platform/pricing
- https://docs.fly.io/about/pricing
- https://github.com/emmanuelakwasi/cloud-free-tier-2026 (AWS/GCP/Azure comparison)
- https://rivet.dev/blog/godot-multiplayer-compared-to-unity/
- https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html
- https://partner.steamgames.com/doc/features/multiplayer/steamdatagramrelay and https://steamcommunity.com/app/1435790/discussions/0/596268535200665589 (Escape Simulator hosting modes)
- https://heroiclabs.com/blog/which-multiplayer-architecture-live-game/index.html and https://crux.supercraft.host/blog/nakama-open-source-vs-managed-backend/
- https://unity.com/products/vivox
- https://dev.to/whetlan/building-zero-config-lan-discovery-in-nodejs-mdns-udp-broadcast-44go
- https://edgegap.com/blog/does-using-kubernetes-agones-does-not-make-economic-sense
