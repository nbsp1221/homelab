#!/bin/sh
set -eu
umask 077

target=$1 stage=$2 requires_env=$3 caddy=$4
env_changed=false

# Use one Compose input path for validation, apply, and reload.
compose_with_env() (
    file=$1 env_file=$2
    shift 2
    if [ ! -f "$env_file" ]; then
        env_file=/dev/null
    fi
    keys=$(awk '
        $0 == "# BEGIN HOMELAB HOST VALUES" { managed = 1; next }
        $0 == "# END HOMELAB HOST VALUES" { managed = 0; next }
        managed && match($0, /^[A-Z_][A-Z0-9_]*=/) { print substr($0, 1, RLENGTH - 1) }
    ' "$env_file")
    for key in $keys; do
        unset "$key"
    done
    if [ -n "$override" ]; then
        set -- -f "$override" "$@"
    fi
    docker compose --project-directory "$target" --env-file "$env_file" \
        -f "$file" "$@"
)

active() {
    compose_with_env "$target/compose.yaml" "$target/.env" "$@"
}

candidate() {
    compose_with_env "$stage/compose.yaml" "$stage/.env" "$@"
}

reload_caddy() {
    [ "$caddy" = yes ] || return 0
    for attempt in 1 2 3; do
        if active exec -T caddy caddy reload --config /etc/caddy/Caddyfile; then
            return 0
        fi
        [ "$attempt" = 3 ] || sleep 2
    done
    return 1
}

# Each run uploads into a private directory before acquiring the project lock.
# Validate its shape before registering cleanup.
case "$stage" in
    "$target"/.deploy-*) [ "$(dirname -- "$stage")" = "$target" ] || exit 1 ;;
    *) exit 1 ;;
esac
test -d "$stage"
trap 'rm -rf -- "$stage"' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
exec 9>"$target/.deploy.lock"
if ! flock -n 9; then
    printf 'Another Compose deploy is already running for %s\n' "$target" >&2
    exit 1
fi

override=
for filename in compose.override.yml compose.override.yaml docker-compose.override.yml docker-compose.override.yaml; do
    if [ -f "$target/$filename" ]; then
        override=$target/$filename
        break
    fi
done

env_source=/dev/null
if [ -e "$target/.env" ] || [ -L "$target/.env" ]; then
    test -f "$target/.env" && test ! -L "$target/.env"
    env_source=$target/.env
elif [ -f "$stage/seed.env" ]; then
    env_source=$stage/seed.env
    if grep -Fxq '# BEGIN HOMELAB HOST VALUES' "$env_source"; then
        printf 'Seed from a secret-only file without a host-values block.\n' >&2
        exit 1
    fi
elif [ "$requires_env" = yes ]; then
    printf 'Missing required environment file: %s/.env\n' "$target" >&2
    exit 1
fi

# Preserve untouched lines and reject ambiguous or partial marker blocks.
if ! awk '
    $0 == "# BEGIN HOMELAB HOST VALUES" {
        if (in_block || found) exit 1
        in_block = found = 1
        next
    }
    $0 == "# END HOMELAB HOST VALUES" {
        if (!in_block) exit 1
        in_block = 0
        next
    }
    !in_block { print }
    END { if (in_block) exit 1 }
' "$env_source" > "$stage/.env"; then
    printf 'Invalid managed block in the stack environment file.\n' >&2
    exit 1
fi
if [ -s "$stage/managed.env" ]; then
    cat "$stage/managed.env" >> "$stage/.env"
fi
if [ -f "$target/.env" ]; then
    chown --reference="$target/.env" "$stage/.env"
    if ! cmp -s "$target/.env" "$stage/.env" || [ "$(stat -c %a "$target/.env")" != 600 ]; then
        env_changed=true
    fi
elif [ "$env_source" != /dev/null ] || [ -s "$stage/.env" ]; then
    env_changed=true
    chown --reference="$stage" "$stage/.env"
fi
chmod 600 "$stage/.env"

# Ask Compose for the effective project after interpolation and overrides. Inspect
# Docker directly so a missing previous environment cannot block an initial seed.
model=$(candidate config --format json)
project=$(printf '%s\n' "$model" |
    sed -n 's/^  "name": "\([a-z0-9][a-z0-9_-]*\)",\{0,1\}$/\1/p')
unset model
case "$project" in
    ""|[!a-z0-9]*|*[!a-z0-9_-]*)
        printf 'Could not identify the validated Compose project.\n' >&2
        exit 1
        ;;
esac
canonical_target=$(realpath -e -- "$target")
containers=$(docker ps -a --filter "label=com.docker.compose.project=$project" \
    --format '{{.ID}}|{{.Label "com.docker.compose.project.working_dir"}}|{{.Label "com.docker.compose.oneoff"}}')
while IFS='|' read -r id directory oneoff; do
    [ -n "$id" ] || continue
    case "$oneoff" in True|true) continue ;; esac
    if [ "$directory" != "$target" ] &&
        [ "$(realpath -e -- "$directory" 2>/dev/null || :)" != "$canonical_target" ]; then
        printf 'Compose project %s is already managed from another directory.\n' "$project" >&2
        exit 1
    fi
done <<EOF
$containers
EOF
if [ "$caddy" = yes ]; then
    candidate run --rm --no-deps --volume "$stage/config:/etc/caddy:ro" \
        caddy caddy validate --config /etc/caddy/Caddyfile
    test ! -L "$target/config"
    if [ ! -d "$target/config" ]; then
        install -d -m 0700 -o "$(stat -c %u -- "$target")" \
            -g "$(stat -c %g -- "$target")" -- "$target/config"
    fi
fi

if [ "$env_changed" = true ]; then
    mv -fT -- "$stage/.env" "$target/.env"
fi
if [ "$caddy" = yes ]; then
    mv -fT -- "$stage/config/Caddyfile" "$target/config/Caddyfile"
fi
mv -fT -- "$stage/compose.yaml" "$target/compose.yaml"
if ! active up -d --wait --wait-timeout 120 || ! reload_caddy; then
    printf 'Compose apply failed after updating %s. Inspect the project before retrying.\n' "$target" >&2
    exit 1
fi
