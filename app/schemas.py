from pydantic import BaseModel
from typing import List, Optional

class EmbedRequest(BaseModel):
    text: str
    type: str = "passage"  # "passage" or "query"

class EmbedBatchRequest(BaseModel):
    texts: List[str]
    type: str = "passage"

class EmbedResponse(BaseModel):
    vector: List[float]
    dimension: int

class EmbedBatchResponse(BaseModel):
    vectors: List[List[float]]
    dimension: int
    count: int
