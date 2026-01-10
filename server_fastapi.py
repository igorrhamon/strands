from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class GenRequest(BaseModel):
    prompt: str
    max_tokens: int | None = None


@app.post("/generate")
async def generate(req: GenRequest):
    # Demo implementation: echo the prompt with a prefix.
    # Replace this with actual model inference (e.g., call into a local
    # model server that loads a GitHub-hosted model).
    text = f"[demo-model] Resposta para: {req.prompt}"
    return {"text": text}
