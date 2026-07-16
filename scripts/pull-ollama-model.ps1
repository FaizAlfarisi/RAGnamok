# Pull required Ollama models for RAGnamok.
# Usage:
#   .\scripts\pull-ollama-model.ps1                    # Pull defaults from .env
#   .\scripts\pull-ollama-model.ps1 qwen3.5:4b         # Pull one model + embedding
#   .\scripts\pull-ollama-model.ps1 qwen3.5:4b gemma3:12b  # Pull multiple + embedding

$Models = $args

$CHAT_MODEL = ""
$EMBED_MODEL = ""

if ($Models.Count -gt 0) {
    $CHAT_MODELS = $Models
    $EMBED_MODEL = "blaifa/multilingual-e5-large-instruct:Q8_0"
} else {
    # Read model names from root .env if available
    $envFile = ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^SUMMARIZATION_MODEL=(.+)') { $CHAT_MODEL = $matches[1] }
            if ($_ -match '^EMBEDDING_MODEL_NAME=(.+)') { $EMBED_MODEL = $matches[1] }
        }
    }
    if (-not $CHAT_MODEL) { $CHAT_MODEL = "qwen3.5:4b" }
    if (-not $EMBED_MODEL) { $EMBED_MODEL = "blaifa/multilingual-e5-large-instruct:Q8_0" }
    $CHAT_MODELS = @($CHAT_MODEL)
}

$MAX_RETRIES = 3

function Get-Engine {
    if (Get-Command docker -ErrorAction SilentlyContinue) { return "docker" }
    if (Get-Command podman -ErrorAction SilentlyContinue) { return "podman" }
    return $null
}

function Get-Container {
    param($Engine)
    $names = @("ragnamok_ollama_1", "ragnamok-ollama-1")
    $psOutput = & $Engine ps --format "{{.Names}}" 2>&1 | Out-String
    foreach ($n in $names) {
        if ($psOutput -match [regex]::Escape($n)) { return $n }
    }
    return $null
}

function Pull-Model {
    param($Model)
    $Engine = Get-Engine
    if (-not $Engine) {
        Write-Host "   No container engine found. Install docker or podman."
        return $false
    }
    $CName = Get-Container -Engine $Engine
    if (-not $CName) {
        Write-Host "   Ollama container not found. Run: $Engine compose up -d"
        return $false
    }
    Write-Host "   Pulling via $Engine exec $CName..."
    & $Engine exec $CName ollama pull $Model 2>&1 | Out-Host
    return $LASTEXITCODE -eq 0
}

Write-Host "============================================"
Write-Host "  RAGnamok Ollama Model Puller"
Write-Host "============================================"

# --- Wait for Ollama to be ready ---
function Test-OllamaReady {
    $e = Get-Engine
    $c = Get-Container -Engine $e
    if (-not $c) { return $false }
    & $e exec $c ollama list 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
}

$maxWait = 12
for ($i = 0; $i -lt $maxWait; $i++) {
    if (Test-OllamaReady) {
        Write-Host "Ollama is ready."
        break
    }
    if ($i -eq ($maxWait - 1)) {
        Write-Host "ERROR: Ollama not ready after $($maxWait * 5)s."
        Write-Host "Ensure the container is running: docker compose --profile full up -d"
        exit 1
    }
    Write-Host "  Waiting for Ollama ($($i+1)/$maxWait)..."
    Start-Sleep -Seconds 5
}

$models = @($CHAT_MODELS | ForEach-Object { @{Label="chat model"; Model=$_} })
$models += @{Label="embedding model"; Model=$EMBED_MODEL}

foreach ($m in $models) {
    $ok = $false
    for ($i = 1; $i -le $MAX_RETRIES; $i++) {
        Write-Host "[$i/$MAX_RETRIES] Pulling $($m.Label): $($m.Model)"
        $ok = Pull-Model -Model $m.Model
        if ($ok) {
            Write-Host "  Done: $($m.Model)"
            break
        }
        if ($i -lt $MAX_RETRIES) {
            Write-Host "  Retrying in 5s..."
            Start-Sleep -Seconds 5
        }
    }
    if (-not $ok) {
        Write-Host "ERROR: Failed to pull $($m.Model) after $MAX_RETRIES attempts."
        Write-Host "Ensure the Ollama container is running."
        exit 1
    }
}

# Update model vars in root .env (partial update, preserves other vars)
$firstModel = $CHAT_MODELS[0]
$lines = @()
if (Test-Path ".env") {
    $lines = Get-Content ".env"
}
$hadSum = $false
$hadGen = $false
$newLines = $lines | ForEach-Object {
    if ($_ -match '^SUMMARIZATION_MODEL=') { $hadSum = $true; "SUMMARIZATION_MODEL=$firstModel" }
    elseif ($_ -match '^GENERATION_MODEL=') { $hadGen = $true; "GENERATION_MODEL=$firstModel" }
    else { $_ }
}
if (-not $hadSum) { $newLines += "SUMMARIZATION_MODEL=$firstModel" }
if (-not $hadGen) { $newLines += "GENERATION_MODEL=$firstModel" }
$newLines | Set-Content ".env" -Encoding UTF8
Write-Host "   .env updated with model: $firstModel"

Write-Host "All models pulled successfully."
