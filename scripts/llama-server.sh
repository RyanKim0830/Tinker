#!/usr/bin/env bash
# llama-server 실행 스크립트 (WSL 기준)
# - 모델 경로는 WSL이 읽는 경로(/mnt/c/...)로 지정한다. (Windows 경로 C:\... 는 WSL에서 못 찾는다)
# - LLAMA_CACHE 를 models/ 로 지정해 llama.cpp 캐시도 프로젝트 안에 모은다.
# - 옵션은 b11377 의 --help 로 확인한 이름이다. 다른 버전이면 docs/open-items.md 참고.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp/llama-b11377}"   # 바이너리 + CUDA 런타임이 같이 있는 폴더
MODEL="${MODEL:-$ROOT/models/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf}"

export LD_LIBRARY_PATH="$LLAMA_DIR:${LD_LIBRARY_PATH:-}"
export LLAMA_CACHE="$ROOT/models"

# -c 8192            : 컨텍스트 길이
# -ctk/-ctv q8_0     : KV 캐시 양자화 (VRAM 절약)
# --reasoning off    : Qwen3.5 는 기본 thinking ON 이라 서버에서 끈다
# -ngl 99            : 전 레이어 GPU 적재 (VRAM 6GB, 4B Q5 약 3GB 로 충분)
# 샘플링 파라미터(temperature 등)는 서버가 아니라 요청마다 llm/client.py 가 보낸다. (값은 llm/config.py 한 곳)
exec "$LLAMA_DIR/llama-server" \
  -m "$MODEL" \
  --port 8080 \
  -c 8192 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  --reasoning off \
  -ngl 99 \
  --cpu-moe \
