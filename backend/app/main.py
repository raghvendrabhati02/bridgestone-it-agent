from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Bridgestone IT Agent",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {
        "message": "Bridgestone IT Agent Running"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

@app.post("/chat")
def chat(request: ChatRequest):
    return {
        "user_message": request.message,
        "response": f"I received your issue: {request.message}"
    }