import os
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Northwind Retail AI",
    description="Intentionally testable chatbot for the AI red-teaming lab",
    version="0.1.0",
)

MODEL = os.getenv("OLLAMA_MODEL", "basileak-r4:latest")

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat",
)

# Default 0 keeps the app deterministic. Set OLLAMA_TEMPERATURE to sample at a
# higher temperature, e.g. for attack-success-rate measurement.
TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"

SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(
    encoding="utf-8"
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    model: str

@app.get("/")
def root():
    return {
        "status": "running",
        "application": "Northwind Retail AI Red-Team Target",
        "model": MODEL,
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL,
    }

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": request.message,
            },
        ],
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
        },
    }
    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120,
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not communicate with Ollama: {exc}",
        )

    data = response.json()

    assistant_response = data["message"]["content"]

    return ChatResponse(
        response=assistant_response,
        model=MODEL,
    )