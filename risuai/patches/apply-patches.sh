#!/bin/sh
set -eu

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

  if git apply --check "$patch_file"; then
    echo "Applying patch: $patch_name"
    git apply "$patch_file"
    return
  fi

  if git apply --reverse --check "$patch_file"; then
    echo "Patch already applied: $patch_name"
    return
  fi

  echo "Patch cannot be applied cleanly: $patch_name" >&2
  git apply --check "$patch_file"
}

while IFS= read -r patch_name || [ -n "$patch_name" ]; do
  patch_name="${patch_name%%#*}"
  patch_name="$(printf '%s' "$patch_name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

  if [ -z "$patch_name" ]; then
    continue
  fi

  apply_patch "$patch_name"
done < "$SERIES_FILE"

git diff --check
echo "Patch series applied successfully."
