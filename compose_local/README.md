# Local Infrastructure — compose_local

**Date:** 2026-07-30
**Branch:** `feature/integration`

Two separate compose files live here for two different local setups. Pick one — don't run both at the same time (they define containers with colliding fixed names/subnets, see below).

| File | What it starts | Use when |
|---|---|---|
| `docker-composes-local.yml` | Redis Sentinel cluster (1 master + 2 replicas, mTLS) + 3 Sentinels + RedisInsight + Elasticsearch | You're running `manage.py runserver` / Celery directly on the host and just need infra (documented in the root `CLAUDE.md`) |
| `docker-compose.local.yml` | Full stack: `api` + `celery` + `celery-beat` + Postgres + Redis (plain) + Elasticsearch + RedisInsight | You want the whole app containerized, including the database |

## Quick start (`docker-composes-local.yml`)

```bash
cd compose_local
HOST_IP=<your-machine-LAN-IP> REDIS_PASSWORD=<pick-a-value> SENTINEL_PASSWORD=<pick-a-value> \
  docker compose -f docker-composes-local.yml up -d
```

Find your LAN IP with `ipconfig getifaddr en0` (Mac) — do **not** use `127.0.0.1`; see below for why.

### Env vars this file needs that aren't in `.env`/`.env.example`

None of these three are documented anywhere else in the repo today. All three must be set or the stack will not come up correctly:

- **`HOST_IP`** — used as both the Sentinel `monitor`/`announce-ip` target and the replicas' `--replica-announce-ip`. Must be an address reachable from *inside* the containers (via the host's real NIC) — using `127.0.0.1` breaks it, since that resolves to "this container" independently inside each container's own network namespace, not the host.
- **`REDIS_PASSWORD`** — used for `--requirepass`/`--masterauth` on redis-master/replicas and for Sentinel's `sentinel auth-pass mymaster $REDIS_PASSWORD` line.
- **`SENTINEL_PASSWORD`** — used for Sentinel's own `requirepass` line.

**Why these are required, not optional:** the Sentinel containers build their config by shelling out `echo "requirepass $SENTINEL_PASSWORD" >> /etc/sentinel.conf` etc. If the var is empty, the generated config line has no argument (e.g. just `requirepass` with nothing after it), and Redis 8.x's config parser hard-fails on that with `*** FATAL CONFIG FILE ERROR *** wrong number of arguments` / `Unrecognized sentinel configuration statement` — the container crash-loops instead of starting. Older Redis versions may have silently tolerated an empty value; this one doesn't.

## Known issue: containers name-collide with other WDG-boilerplate services

`docker-composes-local.yml` hardcodes `container_name:` for every service (`redis-master`, `redis-slave-1`, `redis-slave-2`, `sentinel-1`, `sentinel-2`, `sentinel-3`, `elasticsearch`, `redisinsight`) rather than letting Compose namespace them by project. Any other local microservice built on the same WDG Micro Skeleton boilerplate (e.g. `file_storage_service` in this same `microservices/` folder) defines the **identical** container names and a fixed subnet (`172.21.0.0/16` for the `redis-net` network) — so only one of these projects' Sentinel stacks can exist on a given machine's Docker daemon at a time. Bringing this one up while a sibling project's stack (even stopped) still exists will fail with:

```
failed to create network compose_local_redis-net: ... Pool overlaps with other one on this address space
Container redis-master ... Conflict. The container name "/redis-master" is already in use ...
```

**Fix:** `docker network rm <the-other-project's-network>` and `docker rm` the sibling project's stopped containers with the colliding names before starting this one. That sibling project's own compose file will recreate its network/containers next time it's brought up — no data loss for named volumes (bind-mounted data under its own `./data/` directory is untouched either way).

## Known issue: Sentinel reports the master as down even though replication works

After bringing the stack up with `HOST_IP` set to the host's real LAN IP, `redis-master`'s own replication to `redis-slave-1`/`redis-slave-2` succeeds (visible in `docker logs redis-master`), but `docker logs sentinel-1` sticks on:

```
+monitor master mymaster <HOST_IP> 6379 quorum 2
+sdown master mymaster <HOST_IP> 6379
```

...and never recovers. This looks like a Docker-Desktop-for-Mac hairpin-NAT/TLS quirk specific to the Sentinel→master health-check connection (container → host LAN IP → back into another container's published port), separate from the master→replica data path, which routes the same way and does work. Not yet root-caused. Since the app's `.env` currently has `REDIS_USE_SENTINEL=False`, this doesn't block normal local development — it only matters if you're specifically testing Sentinel failover.

## Verifying the stack

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
docker logs redis-master --tail 20
docker logs sentinel-1 --tail 20
curl -i http://localhost:9200        # Elasticsearch (401 with default security is expected)
curl -i http://localhost:5540        # RedisInsight UI
```

Ports: `6379` (redis-master), `6380`/`6381` (replicas), `26379`/`26380`/`26381` (sentinels), `9200`/`9300` (Elasticsearch), `5540` (RedisInsight).
