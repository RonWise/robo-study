#!/bin/bash
set -euo pipefail
: "${DISPLAY:?Run from the graphical desktop}"
: "${XAUTHORITY:?X11 authentication file is required}"
auth_dir=$(mktemp -d /tmp/robo-gpu-xauth.XXXXXX)
trap 'rm -f "$auth_dir/Xauthority"; rmdir "$auth_dir"' EXIT
touch "$auth_dir/Xauthority"
chmod 600 "$auth_dir/Xauthority"
xauth nlist "$DISPLAY" | sed 's/^..../ffff/' | xauth -f "$auth_dir/Xauthority" nmerge -
[[ -s "$auth_dir/Xauthority" ]] || { echo 'No X11 authentication record' >&2; exit 1; }
if (( $# == 0 )); then set -- glxinfo -B; fi
docker run --rm --runtime=nvidia --security-opt label=disable \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display \
  -e DISPLAY -e XAUTHORITY=/tmp/Xauthority \
  -e __NV_PRIME_RENDER_OFFLOAD=1 -e __GLX_VENDOR_LIBRARY_NAME=nvidia \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "$auth_dir/Xauthority:/tmp/Xauthority:ro" \
  robo-gpu-check:ubuntu22.04 "$@"
