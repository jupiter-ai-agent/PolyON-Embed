from fastapi import FastAPI, HTTPException
from model import EmbedModel
from schemas import EmbedRequest, EmbedBatchRequest, EmbedResponse, EmbedBatchResponse

app = FastAPI(title="PolyON Embed", version="0.1.0")
model = EmbedModel()

@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    prefix = "query: " if req.type == "query" else "passage: "
    try:
        vector = model.encode(prefix + req.text)
        return EmbedResponse(vector=vector.tolist(), dimension=len(vector))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embed/batch", response_model=EmbedBatchResponse)
def embed_batch(req: EmbedBatchRequest):
    prefix = "query: " if req.type == "query" else "passage: "
    try:
        prefixed = [prefix + t for t in req.texts]
        vectors = model.encode_batch(prefixed)
        vlist = [v.tolist() for v in vectors]
        return EmbedBatchResponse(vectors=vlist, dimension=len(vlist[0]) if vlist else 768, count=len(vlist))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model.is_loaded(), "service": "polyon-embed"}

@app.get("/model/info")
def model_info():
    return {
        "name": "intfloat/multilingual-e5-base",
        "dimension": 768,
        "languages": 100,
        "loaded": model.is_loaded()
    }
