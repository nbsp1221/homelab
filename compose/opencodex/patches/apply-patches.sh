#!/bin/sh
set -eu

# Applies the patch series to the globally installed opencodex npm package.
# The npm package ships its TypeScript source and runs it via the bundled Bun
# runtime, so patching src/*.ts in place is sufficient.
#
# When an upstream release fixes https://github.com/lidge-jun/opencodex/issues/1612,
# remove the entry from `series` instead of letting the build fail.

PKG_DIR="${PKG_DIR:-/usr/local/lib/node_modules/@bitkyc08/opencodex}"
PATCH_DIR="${PATCH_DIR:-/tmp/patches}"
SERIES_FILE="${SERIES_FILE:-$PATCH_DIR/series}"

if [ ! -f "$SERIES_FILE" ]; then
  echo "Patch series file not found: $SERIES_FILE" >&2
  exit 1
fi

apply_patch() {
  patch_name="$1"
  patch_file="$PATCH_DIR/$patch_name"

  if [ ! -f "$patch_file" ]; then
    echo "Patch file listed in series does not exist: $patch_name" >&2
    exit 1
  fi

  if patch -d "$PKG_DIR" -p1 --dry-run --batch --silent < "$patch_file"; then
    echo "Applying patch: $patch_name"
    patch -d "$PKG_DIR" -p1 --batch < "$patch_file"
    return
  fi

  if patch -d "$PKG_DIR" -p1 --dry-run --batch --silent --reverse < "$patch_file"; then
    echo "Patch already applied: $patch_name"
    return
  fi

  echo "Patch does not apply cleanly: $patch_name" >&2
  exit 1
}

while IFS= read -r line; do
  case "$line" in
    ""|\#*) continue ;;
    *) apply_patch "$line" ;;
  esac
done < "$SERIES_FILE"
