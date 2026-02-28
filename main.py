import yaml
import os
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, List, Dict, Any
import asyncio
from datetime import datetime
import logging

CONFIG_PATH = "config.yaml"
OLLAMA_BASE_URL = "https://ollama.com"

logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[
    logging.StreamHandler(),
    logging.FileHandler('proxy.log')
])
logger = logging.getLogger()

app = FastAPI(title="Ollama Cloud Proxy", version="1.0.0")

config = {}
accounts = []

def load_config():
    global config, accounts
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
    accounts = sorted(config.get("ollama_cloud", {}).get("accounts", []), key=lambda x: x.get("priority", 999))

load_config()

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    return True

def get_headers_for_account(account: Dict) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {account['api_key']}",
        "Content-Type": "application/json"
    }

def convert_message_for_ollama(message: Dict) -> Dict:
    role = message.get("role", "user")
    content = message.get("content", "")
    
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        text_parts.append(f"[Image: {img_url}]")
        content = "\n".join(text_parts) if text_parts else ""
    
    return {
        "role": role,
        "content": str(content) if content else ""
    }

async def call_ollama_chat(account: Dict, payload: Dict[str, Any], timeout: int = 30) -> Dict:
    headers = get_headers_for_account(account)
    logger.info(f"[DEBUG] Calling Ollama with payload: {payload}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            headers=headers
        )
        logger.info(f"[DEBUG] Ollama response status: {response.status_code}")
        logger.info(f"[DEBUG] Ollama response body preview: {response.text[:200]}")
        
        text = response.text.strip()
        if not text:
            raise Exception("Empty response from Ollama")
        
        try:
            return response.json()
        except:
            lines = text.split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line:
                    try:
                        import json
                        return json.loads(line)
                    except:
                        continue
            raise Exception(f"Could not parse Ollama response: {text[:200]}")

async def stream_ollama_chat(account: Dict, model: str, messages: List[Dict], timeout: int = 120):
    """Stream response from Ollama in SSE format"""
    headers = get_headers_for_account(account)
    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }
    
    logger.info(f"[STREAM] Starting streaming for model {model}")
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/chat",
            json=payload,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        import json
                        data = json.loads(line)
                        
                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        
                        if content or data.get("done", False):
                            chunk = {
                                "id": f"chatcmpl-{datetime.utcnow().timestamp()}",
                                "object": "chat.completion.chunk",
                                "created": int(datetime.utcnow().timestamp()),
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "content": content
                                        },
                                        "finish_reason": "stop" if data.get("done") else None
                                    }
                                ]
                            }
                            yield f"data: {json.dumps(chunk)}\n\n"
                            
                        if data.get("done", False):
                            yield "data: [DONE]\n\n"
                            break
                    except:
                        continue

async def call_ollama_generate(account: Dict, payload: Dict[str, Any], timeout: int = 30) -> Dict:
    headers = get_headers_for_account(account)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

async def call_ollama_models(account: Dict, timeout: int = 30) -> Dict:
    headers = get_headers_for_account(account)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            headers=headers
        )
        response.raise_for_status()
        return response.json()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/v1/models")
async def list_models(authorized: bool = Depends(verify_api_key)):
    for account in accounts:
        try:
            result = await call_ollama_models(account)
            models = result.get("models", [])
            return {
                "object": "list",
                "data": [
                    {
                        "id": m["name"],
                        "object": "model",
                        "created": 0,
                        "owned_by": "ollama"
                    }
                    for m in models
                ]
            }
        except Exception as e:
            logger.info(f"Account {account['name']} failed: {e}")
            continue
    
    raise HTTPException(status_code=503, detail="All accounts failed")

@app.post("/v1/chat/completions")
async def chat_completions(
    payload: Dict[str, Any],
    authorized: bool = Depends(verify_api_key)
):
    model = payload.get("model", "")
    messages = payload.get("messages", [])
    stream = payload.get("stream", False)
    
    logger.info(f"[DEBUG] Incoming model: {model}")
    logger.info(f"[DEBUG] Incoming messages (count): {len(messages)}")
    logger.info(f"[DEBUG] Stream: {stream}")
    
    ollama_model = model.replace(":cloud", "")
    
    ollama_messages = [convert_message_for_ollama(msg) for msg in messages]
    
    fallback_config = config.get("fallback", {})
    retry_attempts = fallback_config.get("retry_attempts", 3)
    timeout = fallback_config.get("timeout", 120)
    
    last_error = None
    for attempt in range(retry_attempts):
        for account in accounts:
            try:
                logger.info(f"Trying account {account['name']} with model {ollama_model}...")
                
                if stream:
                    # Handle streaming response
                    return StreamingResponse(
                        stream_ollama_chat(account, ollama_model, ollama_messages, timeout),
                        media_type="text/event-stream"
                    )
                else:
                    # Non-streaming response
                    ollama_payload = {
                        "model": ollama_model,
                        "messages": ollama_messages,
                        "stream": False,
                        "options": {
                            "num_predict": 4096
                        }
                    }
                    
                    logger.info(f"[DEBUG] Ollama payload prepared")
                    result = await call_ollama_chat(account, ollama_payload, timeout=timeout)
                    
                    logger.info(f"[DEBUG] Ollama response received")
                    
                    msg = result.get("message", {})
                    content = msg.get("content", "")
                    
                    full_content = content if content else ""
                    
                    response_data = {
                        "id": f"chatcmpl-{datetime.utcnow().timestamp()}",
                        "object": "chat.completion",
                        "created": int(datetime.utcnow().timestamp()),
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": full_content
                                },
                                "finish_reason": "stop"
                            }
                        ]
                    }
                    
                    logger.info(f"[DEBUG] Returning response to client")
                    return response_data
                
            except Exception as e:
                logger.info(f"Account {account['name']} failed: {e}")
                last_error = str(e)
                continue
    
    raise HTTPException(status_code=503, detail=f"All accounts failed: {last_error}")

@app.post("/v1/completions")
async def completions(
    payload: Dict[str, Any],
    authorized: bool = Depends(verify_api_key)
):
    model = payload.get("model", "")
    prompt = payload.get("prompt", "")
    stream = payload.get("stream", False)
    
    ollama_payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    fallback_config = config.get("fallback", {})
    retry_attempts = fallback_config.get("retry_attempts", 3)
    timeout = fallback_config.get("timeout", 30)
    
    last_error = None
    for attempt in range(retry_attempts):
        for account in accounts:
            try:
                result = await call_ollama_generate(account, ollama_payload, timeout=timeout)
                
                return {
                    "id": f"cmpl-{datetime.utcnow().timestamp()}",
                    "object": "text_completion",
                    "created": int(datetime.utcnow().timestamp()),
                    "model": model,
                    "choices": [
                        {
                            "text": result.get("response", ""),
                            "index": 0,
                            "finish_reason": "stop"
                        }
                    ]
                }
            except Exception as e:
                last_error = str(e)
                continue
    
    raise HTTPException(status_code=503, detail=f"All accounts failed: {last_error}")

@app.get("/status")
async def status():
    status_list = []
    for account in accounts:
        try:
            await call_ollama_models(account, timeout=5)
            status_list.append({"name": account["name"], "status": "online"})
        except Exception as e:
            status_list.append({"name": account["name"], "status": "offline", "error": str(e)})
    
    return {"accounts": status_list}

if __name__ == "__main__":
    import uvicorn
    proxy_config = config.get("proxy", {})
    host = proxy_config.get("host", "localhost")
    port = proxy_config.get("port", 8080)
    uvicorn.run(app, host=host, port=port)
