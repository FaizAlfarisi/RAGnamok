#!/usr/bin/env bash
# Pull required Ollama models for RAGnamok.
# Usage:
#   ./scripts/pull-ollama-model.sh              # Pull defaults from .env
#   ./scripts/pull-ollama-model.sh qwen3.5:4b   # Pull one model + embedding
set -euo pipefail

# Accept positional args as model names
CHAT_MODELS=("$@")
ENV_FILE=".env"
CHAT_MODEL=""
EMBED_MODEL=""

if [ ${#CHAT_MODELS[@]} -gt 0 ]; then
  EMBED_MODEL="blaifa/multilingual-e5-large-instruct:Q8_0"
else
  # Read model names from root .env if available
  if [ -f "$ENV_FILE" ]; then
    CHAT_MODEL="${SUMMARIZATION_MODEL:-$(grep -s '^SUMMARIZATION_MODEL=' "$ENV_FILE" | cut -d= -f2)}"
    EMBED_MODEL="${EMBEDDING_MODEL_NAME:-$(grep -s '^EMBEDDING_MODEL_NAME=' "$ENV_FILE" | cut -d= -f2)}"
  fi
  CHAT_MODEL="${CHAT_MODEL:-qwen3.5:4b}"
  EMBED_MODEL="${EMBED_MODEL:-blaifa/multilingual-e5-large-instruct:Q8_0}"
  CHAT_MODELS=("$CHAT_MODEL")
fi

_engine() {
  command -v docker &> /dev/null && echo docker || echo podman
}

_ollama_container() {
  local engine; engine="$(_engine)"
  for cname in ragnamok-ollama-1 ragnamok_ollama_1; do
    if $engine ps --format '{{.Names}}' 2>/dev/null | grep -qF "$cname"; then
      echo "$cname"
      return 0
    fi
  done
  return 1
}

_ollama_ready() {
  local engine; engine="$(_engine)"
  local cname
  cname="$(_ollama_container)" || return 1
  $engine exec "$cname" ollama list &>/dev/null
}

_wait_for_ollama() {
  local max=12 i=0
  echo "==> Waiting for Ollama to be ready..."
  while [ $i -lt $max ]; do
    if _ollama_ready; then
      echo "==> Ollama is ready."
      return 0
    fi
    echo "    Not ready yet ($((i + 1))/$max)..."
    sleep 5
    i=$((i + 1))
  done
  echo "ERROR: Ollama not ready after $((max * 5))s."
  echo "Ensure the container is running: docker compose --profile full up -d"
  exit 1
}

_ollama_exec() {
  local model="$1"
  local engine; engine="$(_engine)"
  local cname; cname="$(_ollama_container)" || return 1
  $engine exec "$cname" ollama pull "$model"
}

_pull_with_retry() {
  local label="$1" model="$2" attempt=1 max=3
  while [ $attempt -le $max ]; do
    echo "==> [$attempt/$max] Pulling $label: $model"
    if _ollama_exec "$model"; then
      echo "==> Done: $model"
      return 0
    fi
    echo "    Retrying in 5s..."
    sleep 5
    attempt=$((attempt + 1))
  done
  echo "ERROR: Failed to pull $model after $max attempts."
  exit 1
}

_wait_for_ollama
for model in "${CHAT_MODELS[@]}"; do
  _pull_with_retry "chat model" "$model"
done
_pull_with_retry "embedding model" "$EMBED_MODEL"

# Update model vars in root .env (partial update, preserves other vars)
first_model="${CHAT_MODELS[0]}"
if [ -f .env ]; then
  awk -v model="$first_model" '
    /^SUMMARIZATION_MODEL=/ { print "SUMMARIZATION_MODEL=" model; s=1; next }
    /^GENERATION_MODEL=/    { print "GENERATION_MODEL=" model; g=1; next }
    { print }
    END {
      if (!s) print "SUMMARIZATION_MODEL=" model
      if (!g) print "GENERATION_MODEL=" model
    }
  ' .env > .env.tmp && mv .env.tmp .env
else
  cat > .env <<EOF
SUMMARIZATION_MODEL=$first_model
GENERATION_MODEL=$first_model
EOF
fi
echo "   .env updated with model: $first_model"

echo "==> All models pulled successfully."
