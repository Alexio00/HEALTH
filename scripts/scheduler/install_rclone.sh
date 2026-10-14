#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${HEALTH_RCLONE_VERSION:?HEALTH_RCLONE_VERSION is required}"
: "${HEALTH_RCLONE_ARCHIVE_SHA256:?Approved archive SHA-256 is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_PATH:?GITHUB_PATH is required}"

# The version only selects a URL. A checksum downloaded from the same origin
# would not be an independent trust anchor.
if [[ ! "$HEALTH_RCLONE_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid rclone version" >&2
  exit 2
fi
if [[ ! "$HEALTH_RCLONE_ARCHIVE_SHA256" =~ ^[a-f0-9]{64}$ ]]; then
  echo "Missing or invalid independent rclone archive pin" >&2
  exit 2
fi

cd "$RUNNER_TEMP"
archive="rclone-v${HEALTH_RCLONE_VERSION}-linux-amd64.zip"
base="https://downloads.rclone.org/v${HEALTH_RCLONE_VERSION}"

curl -fsSLo "$archive" "$base/$archive"
printf '%s  %s\n' "$HEALTH_RCLONE_ARCHIVE_SHA256" "$archive" | sha256sum -c -

rm -rf rclone-extract
mkdir -p rclone-extract "$RUNNER_TEMP/bin"
python3 -m zipfile -e "$archive" rclone-extract
install -m 0755 "rclone-extract/rclone-v${HEALTH_RCLONE_VERSION}-linux-amd64/rclone" "$RUNNER_TEMP/bin/rclone"
echo "$RUNNER_TEMP/bin" >> "$GITHUB_PATH"
"$RUNNER_TEMP/bin/rclone" version
