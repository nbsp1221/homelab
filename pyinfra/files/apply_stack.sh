#!/bin/sh
set -eu
umask 077

target=$1 stage=$2 requires_env=$3 caddy=$4
backup=$stage/previous
promoted=false had_project=false running='' env_changed=false

active() {
    docker compose --project-directory "$target" -f "$target/compose.yaml" "$@"
}

candidate() {
    docker compose --project-directory "$stage" --env-file "$stage/.env" \
        -f "$stage/compose.yaml" "$@"
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

save_file() {
    if [ -e "$target/$1" ] || [ -L "$target/$1" ]; then
        cp -a -- "$target/$1" "$backup/$2"
    fi
}

restore_file() {
    if [ -e "$backup/$2" ] || [ -L "$backup/$2" ]; then
        cp -a -- "$backup/$2" "$stage/restore-$2" &&
            mv -fT -- "$stage/restore-$2" "$target/$1"
    else
        rm -f -- "$target/$1"
    fi
}

finish() {
    status=$?
    trap - EXIT HUP INT TERM
    if [ "$status" -ne 0 ] && [ "$promoted" = true ]; then
        recovered=true
        # An initially stopped project must not stay running after a failed apply.
        if [ -z "$running" ] && [ "$apply_started" = true ]; then
            active stop || recovered=false
        fi
        restore_file compose.yaml compose || recovered=false
        if [ "$caddy" = yes ]; then
            restore_file config/Caddyfile caddy || recovered=false
        fi
        if [ "$env_changed" = true ]; then
            restore_file .env env || recovered=false
        fi
        if [ "$recovered" = true ] && [ "$had_project" = true ] && [ -n "$running" ]; then
            { active up -d --wait --wait-timeout 120 && reload_caddy; } || recovered=false
        fi
        if [ "$recovered" = false ]; then
            printf 'Compose rollback failed. Inspect recovery files in %s\n' "$stage" >&2
            exit "$status"
        fi
        printf 'Compose apply failed. Previous files and running state restored.\n' >&2
    fi
    rm -rf -- "$stage"
    exit "$status"
}

# Each run uploads into a private directory before acquiring the project lock.
# Validate its shape before registering cleanup.
case "$stage" in
    "$target"/.deploy-*) [ "$(dirname -- "$stage")" = "$target" ] || exit 1 ;;
    *) exit 1 ;;
esac
test -d "$stage"
apply_started=false
trap finish EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
exec 9>"$target/.deploy.lock"
if ! flock -n 9; then
    printf 'Another Compose deploy is already running for %s\n' "$target" >&2
    exit 1
fi

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

if [ -f "$target/compose.yaml" ]; then
    had_project=true
    running=$(active ps --status running --quiet)
fi
candidate config --quiet
if [ "$caddy" = yes ]; then
    candidate run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile
    mkdir -p -- "$target/config"
fi

mkdir -- "$backup"
save_file compose.yaml compose
if [ "$caddy" = yes ]; then
    save_file config/Caddyfile caddy
fi
if [ "$env_changed" = true ]; then
    save_file .env env
fi

promoted=true
if [ "$env_changed" = true ]; then
    mv -fT -- "$stage/.env" "$target/.env"
fi
if [ "$caddy" = yes ]; then
    mv -fT -- "$stage/config/Caddyfile" "$target/config/Caddyfile"
fi
mv -fT -- "$stage/compose.yaml" "$target/compose.yaml"
apply_started=true
active up -d --wait --wait-timeout 120
reload_caddy
