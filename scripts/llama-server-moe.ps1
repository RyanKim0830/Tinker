# llama-server 실행 스크립트 (Windows PowerShell 기준, MoE 모델용)
# - scripts/llama-server.sh (WSL 대안) 와 같은 옵션이다. 한쪽을 바꾸면 다른 쪽도 맞출 것.
# - 모델·바이너리 경로는 Windows 경로. 환경변수 MODEL / LLAMA_DIR 로 바꿀 수 있다.
# - WSL 의 llama-server 와 둘 다 8080 이라 동시에 띄우지 않는다. (docs/adr/0015-llama-server-on-windows.md)
# 실행:  .\scripts\llama-server-moe.ps1
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LlamaDir = if ($env:LLAMA_DIR) { $env:LLAMA_DIR } else { Join-Path $Root "bin\cuda12.4" }   # exe + CUDA 런타임이 같이 있는 폴더
$Model    = if ($env:MODEL)     { $env:MODEL }     else { Join-Path $Root "models\Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf" }

$env:LLAMA_CACHE = Join-Path $Root "models"

# -c 8192            : 컨텍스트 길이
# -ctk/-ctv q8_0     : KV 캐시 양자화 (VRAM 절약)
# --reasoning off    : Qwen 은 기본 thinking ON 이라 서버에서 끈다
# -ngl 99            : 전 레이어 GPU 적재
# --cpu-moe          : MoE 전문가(expert) 가중치는 CPU(RAM)에 둔다 (35B 모델이 VRAM 6GB 에 안 들어가서)
# 샘플링 파라미터(temperature 등)는 서버가 아니라 요청마다 llm/client.py 가 보낸다. (값은 llm/config.py 한 곳)
& (Join-Path $LlamaDir "llama-server.exe") `
  -m $Model `
  --port 8080 `
  -c 8192 `
  --cache-type-k q8_0 --cache-type-v q8_0 `
  --reasoning off `
  -ngl 99 `
  --cpu-moe
