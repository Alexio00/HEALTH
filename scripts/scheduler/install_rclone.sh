#!/usr/bin/env bash
set -euo pipefail

: "${HEALTH_RCLONE_VERSION:?HEALTH_RCLONE_VERSION is required}"
cd "$RUNNER_TEMP"
archive="rclone-v${HEALTH_RCLONE_VERSION}-linux-amd64.zip"
base="https://downloads.rclone.org/v${HEALTH_RCLONE_VERSION}"

curl -fsSLo "$archive" "$base/$archive"
curl -fsSLo SHA256SUMS "$base/SHA256SUMS"
grep -E "^[0-9a-fA-F]{64}  ${archive}$" SHA256SUMS > rclone.expected
test -s rclone.expected
sha256sum -c rclone.expected

rm -rf rclone-extract
mkdir -p rclone-extract "$RUNNER_TEMP/bin"
python3 -m zipfile -e "$archive" rclone-extract
install -m 0755 "rclone-extract/rclone-v${HEALTH_RCLONE_VERSION}-linux-amd64/rclone" "$RUNNER_TEMP/bin/rclone"
echo "$RUNNER_TEMP/bin" >> "$GITHUB_PATH"
"$RUNNER_TEMP/bin/rclone" version
