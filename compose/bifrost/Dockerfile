# syntax=docker/dockerfile:1

# Version-pinned Bifrost build: fetch the upstream release tag derived from
# BIFROST_VERSION, apply the numbered local patch, then build the UI and
# transport binary from the same patched tree. The local core module must be
# used by transports; otherwise Go can resolve the unpatched external core
# module instead.
FROM alpine:3.23 AS source-patched
ARG BIFROST_VERSION
WORKDIR /src
RUN apk add --no-cache ca-certificates git
RUN test -n "$BIFROST_VERSION" && \
    git clone \
    --depth 1 \
    --branch "transports/v${BIFROST_VERSION}" \
    https://github.com/maximhq/bifrost.git .
COPY patches/ /tmp/patches/
RUN set -eu; \
    for patch in /tmp/patches/*.patch; do \
        [ -e "$patch" ] || continue; \
        echo "Applying $patch"; \
        git apply "$patch"; \
    done

# Build the patched React + Vite frontend.
FROM node:24-alpine3.23 AS ui-builder
WORKDIR /app
COPY --from=source-patched /src/ui/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY --from=source-patched /src/ui/ ./
RUN npm run build-enterprise

# Build the patched Go transport binary with the patched local core module.
FROM golang:1.26-alpine3.23 AS builder
ARG BIFROST_VERSION
WORKDIR /app
RUN apk add --no-cache \
    binutils \
    binutils-gold \
    gcc \
    musl-dev \
    sqlite-dev
ENV CGO_ENABLED=1 \
    GOOS=linux \
    GOWORK=off
COPY --from=source-patched /src/transports/go.mod ./
COPY --from=source-patched /src/transports/go.sum ./
COPY --from=source-patched /src/core ./core
COPY --from=source-patched /src/transports/ ./
RUN go mod edit \
    -replace=github.com/maximhq/bifrost/core=/app/core
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download
COPY --from=ui-builder /app/out ./bifrost-http/ui
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build \
    -ldflags="-w -s -X main.Version=v${BIFROST_VERSION} -extldflags '-static'" \
    -a \
    -trimpath \
    -tags sqlite_static \
    -o /app/main \
    ./bifrost-http

# Compose owns runtime environment, persistence, networking, and healthchecks.
FROM alpine:3.23
WORKDIR /app
RUN apk add --no-cache \
    ca-certificates \
    libgcc \
    musl \
    zlib
COPY --from=builder /app/main .
COPY --from=builder /app/docker-entrypoint.sh .
RUN mkdir -p /app/data/logs && \
    adduser -D -u 1000 -s /bin/sh appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:0 /app/data && \
    chmod -R g=rwX /app/data && \
    chmod +x /app/docker-entrypoint.sh
USER 1000:0
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/app/main"]
