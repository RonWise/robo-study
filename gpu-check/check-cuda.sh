#!/bin/bash
set -euo pipefail
docker run --rm --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  robo-gpu-check:ubuntu22.04
