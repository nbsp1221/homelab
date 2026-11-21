# Monitoring

Prometheus-based monitoring stack for host, container, and log visibility.

## Overview

This stack provides:

- Prometheus for metrics scraping and storage
- node-exporter for host-level metrics (CPU, memory, disk, filesystem, processes, systemd)
- cAdvisor for container-level metrics
- smartctl-exporter for disk health metrics (SMART / SSD wear / temperature)
- dcgm-exporter for NVIDIA GPU metrics (utilization, temperature, clocks, power, memory)
- blackbox-exporter for HTTP probing
- Loki for log storage and querying
- Alloy for log collection (Docker) and log sanitization
- Grafana for dashboards and visualization

## Architecture

- All core services run on `monitoring-network`
- `grafana` and `blackbox-exporter` also join external `caddy-network`
- Prometheus scrapes exporters, Loki, and Alloy metrics
- Alloy forwards logs to Loki
- Prometheus, Grafana, Loki, and Alloy use named volumes for persistence

## Directory Layout

- `compose.yaml`: stack definition
- `.env.example`: environment variables for Grafana
- `prometheus/prometheus.yml`: scrape config
- `loki/config.yml`: Loki local storage + retention config
- `alloy/config.alloy`: Docker log collection and masking pipeline
- `grafana/provisioning/`: datasource and dashboard provisioning
- `grafana/dashboards/`: dashboard JSON files loaded at startup

## Prerequisites

- Docker Engine
- Docker Compose v2 (`docker compose`)
- External reverse proxy network `caddy-network`
- NVIDIA driver installed and working on host (`nvidia-smi`)
- NVIDIA Container Toolkit configured for Docker (`--gpus` support)

For SMART collection, `smartctl-exporter` runs as `root` in a privileged container.

Create the external network once if needed:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cd monitoring
cp .env.example .env
# edit .env before first run

docker compose up -d
docker compose ps
```

## Access

Grafana is intentionally exposed only through your reverse proxy.

- Upstream service: `grafana:3000` on `caddy-network`
- Default login user: `admin`
- Default login password: value of `GRAFANA_ADMIN_PASSWORD` in `.env`

## Verification

Prometheus target health (`up`):

```bash
docker compose exec -T prometheus wget -qO- \
  'http://127.0.0.1:9090/api/v1/query?query=up' | jq .
```

Prometheus config validation:

```bash
docker compose exec -T prometheus promtool check config /etc/prometheus/prometheus.yml
```

Loki readiness:

```bash
docker compose exec -T loki wget -qO- http://127.0.0.1:3100/ready
```

Alloy readiness:

```bash
docker compose exec -T alloy wget -qO- http://127.0.0.1:12345/-/ready
```

Grafana health:

```bash
docker compose exec -T grafana wget -qO- http://127.0.0.1:3000/api/health
```

## Default Dashboards

Provisioned at startup from `grafana/dashboards/`:

- `node-exporter-full.json`
- `cadvisor-dashboard.json`
- `nvidia-dcgm-exporter-dashboard.json`
- SMART disk health dashboard
- `blackbox-exporter-http-prober-dashboard.json`

Home dashboard path is controlled by `GRAFANA_HOME_DASHBOARD_PATH` in `.env`.

## Persistence

Named volumes:

- `prometheus-data` (`/prometheus`)
- `grafana-data` (`/var/lib/grafana`)
- `loki-data` (`/loki`)
- `alloy-data` (`/var/lib/alloy/data`)

Inspect volume locations on host:

```bash
docker volume inspect prometheus-data
docker volume inspect grafana-data
docker volume inspect loki-data
docker volume inspect alloy-data
```

## Operations

```bash
docker compose pull
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

Destructive reset (removes all monitoring history and Grafana/Loki/Alloy state):

```bash
docker compose down -v
```
