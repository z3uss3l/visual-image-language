#!/usr/bin/env bash
# deploy_zinc.sh - llama-server deployment script optimized for AMD Radeon 780M (Ryzen 7, 32GB RAM)
set -Eeuo pipefail

MODEL_PATH="${MODEL_PATH:-models/model.gguf}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
THREADS="${THREADS:-6}"
CTX_SIZE="${CTX_SIZE:-16384}"
BATCH_SIZE="${BATCH_SIZE:-1024}"
UBATCH_SIZE="${UBATCH_SIZE:-128}"
N_GPU_LAYERS="${N_GPU_LAYERS:--1}"
TEMP="${TEMP:-0.0}"
MIN_P="${MIN_P:-0.05}"

echo "[VLR-LLAMA] Starting llama-server optimized for Radeon 780M..."
echo "  - Model Path: ${MODEL_PATH}"
echo "  - Threads: ${THREADS} (reduced CPU thread overhead for iGPU execution)"
echo "  - Context Size: ${CTX_SIZE} (16k context optimized for 32GB RAM)"
echo "  - Batch Size: ${BATCH_SIZE} (high parallel GPU throughput)"
echo "  - Micro Batch: ${UBATCH_SIZE}"
echo "  - Offload Layers: ${N_GPU_LAYERS} (all layers offloaded to iGPU)"
echo "  - Flash Attention: ON"
echo "  - Listening on: ${HOST}:${PORT}"

exec llama-server \
  --model "${MODEL_PATH}" \
  --host "${HOST}" \
  --port "${PORT}" \
  --threads "${THREADS}" \
  --ctx-size "${CTX_SIZE}" \
  --batch-size "${BATCH_SIZE}" \
  --ubatch-size "${UBATCH_SIZE}" \
  --n-gpu-layers "${N_GPU_LAYERS}" \
  --flash-attn \
  --temp "${TEMP}" \
  --min-p "${MIN_P}" "$@"
