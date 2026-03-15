# PolyON Embed — 구현 가이드

**작성일:** 2026-03-15  
**버전:** v0.1 (초안)

---

## Phase 1: 기반 구축

### 1단계: polyon-embed 컨테이너

**디렉토리 구조:**
```
PolyON-embed/
├── app/
│   ├── main.py          FastAPI 앱
│   ├── model.py         모델 로드/추론
│   └── schemas.py       Pydantic 모델
├── Dockerfile
├── requirements.txt
└── module.yaml          PP 모듈 선언
```

**requirements.txt:**
```
fastapi==0.111.0
uvicorn==0.29.0
sentence-transformers==3.0.1
torch==2.2.2+cpu           # CPU 전용 빌드
numpy==1.26.4
```

**main.py 핵심:**
```python
from fastapi import FastAPI
from model import EmbedModel
from schemas import EmbedRequest, EmbedBatchRequest

app = FastAPI()
model = EmbedModel()

@app.post("/embed")
def embed(req: EmbedRequest):
    prefix = "query: " if req.type == "query" else "passage: "
    vector = model.encode(prefix + req.text)
    return {"vector": vector.tolist(), "dimension": len(vector)}

@app.post("/embed/batch")
def embed_batch(req: EmbedBatchRequest):
    prefixed = [f"passage: {t}" for t in req.texts]
    vectors = model.encode_batch(prefixed)
    return {"vectors": [v.tolist() for v in vectors]}

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model.is_loaded()}

@app.get("/model/info")
def model_info():
    return {
        "name": "intfloat/multilingual-e5-base",
        "dimension": 768,
        "languages": 100,
        "loaded": model.is_loaded()
    }
```

### 2단계: OpenSearch 인덱스 초기화

Core에서 PRC search 클레임 처리 시 실행:

```go
// internal/prc/search.go
func (p *SearchProvider) Provision(ctx context.Context, claim Claim) (Credentials, error) {
    indexName := "polyon_" + claim.ModuleID
    
    // knn_vector 포함 인덱스 생성
    body := buildKNNIndexMapping(indexName, claim.Config)
    err := createOpenSearchIndex(p.Endpoint, indexName, body)
    
    return Credentials{
        "index":    indexName,
        "endpoint": p.Endpoint,
    }, err
}
```

### 3단계: Core Search API

```go
// POST /api/v1/search/index
func indexDocument(d *Deps) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var doc SearchDocument
        json.NewDecoder(r.Body).Decode(&doc)
        
        // 1. polyon-embed 호출 (비동기)
        go func() {
            vector := embedText(d.Cfg.EmbedURL, doc.Content, "passage")
            doc.ContentVector = vector
            
            // 2. OpenSearch 저장
            indexToOpenSearch(d.Cfg.SearchURL, "polyon_"+doc.Module, doc)
        }()
        
        httputil.RespondOK(w, map[string]interface{}{"queued": true})
    }
}

// GET /api/v1/search/query
func searchQuery(d *Deps) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        q := r.URL.Query().Get("q")
        modules := r.URL.Query()["modules"]
        
        // 1. 쿼리 임베딩
        queryVector := embedText(d.Cfg.EmbedURL, q, "query")
        
        // 2. Hybrid Search
        results := hybridSearch(d.Cfg.SearchURL, modules, q, queryVector)
        
        httputil.RespondOK(w, map[string]interface{}{
            "results": results,
            "total":   len(results),
        })
    }
}
```

---

## Phase 2: 모듈 연동

### 메일 (Stalwart) 연동

Stalwart에서 메일 수신/발송 후 Core 웹훅 호출:

```python
# 메일 수신 후 인덱싱
requests.post(f"{CORE_URL}/api/v1/search/index", json={
    "module": "mail",
    "resource_type": "email",
    "resource_id": message_id,
    "title": subject,
    "content": body_text,
    "owner": recipient,
    "metadata": {
        "from": sender,
        "to": recipient,
        "date": date_str
    }
})
```

### 드라이브 (Nextcloud) 연동

파일 업로드 후 텍스트 추출 → 인덱싱:

```python
# PDF/DOCX → 텍스트 추출 후 인덱싱
text = extract_text(file_path)
requests.post(f"{CORE_URL}/api/v1/search/index", json={
    "module": "drive",
    "resource_type": "file",
    "resource_id": file_id,
    "title": filename,
    "content": text[:10000],  # 최대 10,000자
    "owner": uploader,
    "metadata": { "path": file_path, "mime": mime_type }
})
```

---

## Phase 3: Console UI

### Search Stack 모니터링 메뉴

`/search/status` API 응답 기반:
```json
{
  "embed": {
    "status": "ok",
    "model": "multilingual-e5-base",
    "latency_ms": 142,
    "requests_per_minute": 23
  },
  "opensearch": {
    "status": "green",
    "indices": [
      { "name": "polyon_mail", "docs": 1523, "size_bytes": 45678901 },
      { "name": "polyon_drive", "docs": 892, "size_bytes": 23456789 }
    ]
  }
}
```

---

## 환경변수 (PRC)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `EMBED_URL` | polyon-embed 엔드포인트 | `http://polyon-embed:4001` |
| `SEARCH_URL` | OpenSearch 엔드포인트 | `http://polyon-search:9200` |
| `EMBED_BATCH_SIZE` | 배치 처리 크기 | `32` |
| `EMBED_CACHE_TTL` | Redis 캐시 TTL (초) | `3600` |
| `SEARCH_HYBRID_KNN_BOOST` | k-NN 가중치 | `0.7` |
| `SEARCH_HYBRID_BM25_BOOST` | BM25 가중치 | `0.3` |

---

## 릴리스 계획

| Phase | 내용 | 예상 기간 |
|-------|------|----------|
| **Phase 1** | polyon-embed 컨테이너 + OpenSearch kNN + Core Search API | 2주 |
| **Phase 2** | 메일 + 드라이브 연동 | 1주 |
| **Phase 3** | 전체 모듈 연동 + Console UI | 2주 |
| **Phase 4** | ONNX 최적화 + AI Agent RAG 연동 | 미정 |
