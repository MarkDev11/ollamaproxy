# Ollama Cloud Proxy

API proxy for Ollama Cloud with multiple accounts support and automatic failover. Designed for use with OpenCode as a custom provider.

## Features

- **Multiple Ollama Cloud Accounts** - Support up to 6 Ollama Cloud accounts
- **Automatic Failover** - Automatically switch to next account if failed
- **OpenAI-Compatible API** - Compatible with OpenCode and OpenAI libraries
- **Health Monitoring** - Endpoint to check status of each account
- **Streaming Support** - Real-time streaming responses

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit:

```yaml
ollama_cloud:
  accounts:
    - name: "account-1"
      api_key: "ollama_api_key_1"
      priority: 1
    - name: "account-2"
      api_key: "ollama_api_key_2"
      priority: 2

proxy:
  host: "localhost"
  port: 8080
  api_key: "my-secret-key"

fallback:
  retry_attempts: 3
  timeout: 30
```

## Running the Server

```bash
python main.py
```

Server will run at `http://localhost:8080`

## API Endpoints

### Health Check

```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-28T12:00:00"
}
```

### List Models

```
GET /v1/models
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "glm-5:cloud",
      "object": "model",
      "created": 0,
      "owned_by": "ollama"
    }
  ]
}
```

### Chat Completions

```
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "glm-5:cloud",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": false
}
```

Response:
```json
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "glm-5:cloud",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ]
}
```

### Account Status

```
GET /status
```

Response:
```json
{
  "accounts": [
    {"name": "account-1", "status": "online"},
    {"name": "account-2", "status": "offline", "error": "..."}
  ]
}
```

## OpenCode Integration

### Step 1: Edit OpenCode Configuration

File: `~/.config/opencode/opencode.jsonc`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "disabled_providers": [],
  "provider": {
    "ollamaa": {
      "name": "ollamaa",
      "npm": "@ai-sdk/openai-compatible",
      "models": {
        "glm-5:cloud": { "name": "glm-5" },
        "kimi-k2.5:cloud": { "name": "kimi-k2.5" }
      },
      "options": {
        "baseURL": "http://localhost:8080/v1"
      }
    }
  }
}
```

### Step 2: Restart OpenCode

Close and reopen OpenCode to load the new configuration.

## Available Models

From Ollama Cloud:

- `glm-5:cloud` - GLM-5
- `kimi-k2.5:cloud` - Kimi K2.5
- `qwen3-coder-next:cloud` - Qwen3 Coder Next
- `minimax-m2.5:cloud` - MiniMax M2.5

## How Failover Works

1. Request comes to `/v1/chat/completions`
2. Proxy tries first account (priority 1)
3. If failed, retry up to 3x (configurable)
4. If still failed, switch to next account
5. Return response from successful account

## Troubleshooting

### Server won't start

Make sure port 8080 is not in use:

```bash
netstat -ano | findstr :8080
```

Change port in `config.yaml` if needed.

### All accounts offline

- Check internet connection
- Verify API keys in `config.yaml`
- Check status at `http://localhost:8080/status`

### OpenCode can't connect

- Ensure server is running: `curl http://localhost:8080/health`
- Verify `baseURL` in OpenCode config: `http://localhost:8080/v1`

## Project Structure

```
ollamaproxy/
├── config.example.yaml   # Example configuration
├── config.yaml           # Your configuration (gitignored)
├── main.py              # FastAPI server
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## License

MIT
