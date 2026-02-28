# Ollama Cloud Proxy dengan Failover

API proxy untuk Ollama Cloud dengan dukungan multiple accounts dan automatic failover. Dirancang untuk digunakan dengan OpenCode sebagai custom provider.

## Fitur

- **Multiple Ollama Cloud Accounts** - Support hingga 6 akun Ollama Cloud
- **Automatic Failover** - Otomatis switch ke akun berikutnya jika gagal
- **OpenAI-Compatible API** - Compatible dengan OpenCode dan library OpenAI
- **Health Monitoring** - Endpoint untuk cek status setiap akun

## Instalasi

```bash
pip install -r requirements.txt
```

## Konfigurasi

Edit file `config.yaml`:

```yaml
ollama_cloud:
  accounts:
    - name: "account-1"
      api_key: "ollama_api_key_1"
      priority: 1
    - name: "account-2"
      api_key: "ollama_api_key_2"
      priority: 2
    # Tambahkan akun lain sesuai kebutuhan...

proxy:
  host: "0.0.0.0"
  port: 8080
  api_key: "my-secret-key"

fallback:
  retry_attempts: 3
  timeout: 30
```

## Menjalankan Server

```bash
python main.py
```

Server akan berjalan di `http://localhost:8080`

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
Headers:
  x-api-key: my-secret-key
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen3-coder:480b-cloud",
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
Headers:
  Content-Type: application/json
  x-api-key: my-secret-key

Body:
{
  "model": "qwen3-coder:480b-cloud",
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
  "model": "qwen3-coder:480b-cloud",
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

### Text Completions

```
POST /v1/completions
Headers:
  Content-Type: application/json
  x-api-key: my-secret-key

Body:
{
  "model": "qwen3-coder:480b-cloud",
  "prompt": "Hello!",
  "stream": false
}
```

### Status Akun

```
GET /status
Headers:
  x-api-key: my-secret-key
```

Response:
```json
{
  "accounts": [
    {"name": "account-1", "status": "online"},
    {"name": "account-2", "status": "online"},
    {"name": "account-3", "status": "offline", "error": "..."}
  ]
}
```

## Integrasi dengan OpenCode

### Langkah 1: Edit Konfigurasi OpenCode

File: `~/.config/opencode/opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "qwen3-coder:480b-cloud",
  "provider": {
    "my-ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8080/v1",
        "apiKey": "my-secret-key"
      }
    }
  }
}
```

### Langkah 2: Restart OpenCode

Tutup dan buka kembali OpenCode untuk memuat konfigurasi baru.

## Model yang Tersedia

Berdasarkan Ollama Cloud, beberapa model yang tersedia:

- `qwen3-coder:480b-cloud` - Qwen Coder (480B parameters)
- `deepseek-v3.1:671b-cloud` - DeepSeek V3.1
- `gpt-oss:20b-cloud` - GPT OSS (20B)
- `gpt-oss:120b-cloud` - GPT OSS (120B)

## Cara Kerja Failover

1. Request masuk ke `/v1/chat/completions`
2. Proxy mencoba akun pertama (priority 1)
3. Jika gagal, retry hingga 3x (konfigurasi `retry_attempts`)
4. Jika masih gagal, switch ke akun berikutnya
5. Return response dari akun yang berhasil

## Troubleshooting

### Server tidak bisa start

Pastikan port 8080 tidak digunakan:

```bash
netstat -ano | findstr :8080
```

Ganti port di `config.yaml` jika diperlukan.

### Semua akun offline

- Cek koneksi internet
- Verify API key di `config.yaml`
- Cek status di `http://localhost:8080/status`

### OpenCode tidak bisa connect

- Pastikan server berjalan: `curl http://localhost:8080/health`
- Verify `baseURL` di OpenCode config: `http://localhost:8080/v1`
- Cek API key match antara `config.yaml` dan OpenCode config

## Struktur Project

```
porxyollama/
├── config.yaml          # Konfigurasi akun dan server
├── main.py              # FastAPI server
├── requirements.txt     # Python dependencies
└── README.md            # Dokumentasi ini
```

## Development

### Menambahkan Akun Baru

1. Edit `config.yaml`
2. Tambahkan akun baru dengan priority unik:

```yaml
accounts:
  - name: "account-7"
    api_key: "new_api_key"
    priority: 7
```

3. Restart server (Ctrl+C, lalu `python main.py`)

### Mengubah Port

Edit `config.yaml`:

```yaml
proxy:
  port: 9000  # Port baru
```

## Lisensi

MIT
