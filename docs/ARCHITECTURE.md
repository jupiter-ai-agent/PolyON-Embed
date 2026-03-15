# PolyON Embed — 아키텍처 설계

**작성일:** 2026-03-15  
**버전:** v0.1 (초안)

---

## 1. 전체 구조

```
┌──────────────────────────────────────────────────────────────┐
│                    PolyON Search Stack                        │
│                                                              │
│  ┌─────────────────────┐    ┌──────────────────────────┐    │
│  │   polyon-embed      │    │   polyon-search          │    │
│  │   (port: 4001)      │    │   (OpenSearch port:9200) │    │
│  │                     │    │                          │    │
│  │  FastAPI            │    │  BM25 (text 필드)        │    │
│  │  sentence-          │◄──►│  k-NN (knn_vector 필드)  │    │
│  │  transformers       │    │  Hybrid Search           │    │
│  │  multilingual-      │    │                          │    │
│  │  e5-base            │    │                          │    │
│  └─────────────────────┘    └──────────────────────────┘    │
│           ▲                            ▲                     │
└───────────┼────────────────────────────┼─────────────────────┘
            │                            │
            └──────────┬─────────────────┘
                       │
              PolyON Core API
              /search/index
              /search/query
              /search/status
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
      메일           드라이브        채팅/ERP/위키
    (Stalwart)     (Nextcloud)     (기타 모듈)
```

---

## 2. 컴포넌트 상세

### 2.1 polyon-embed

**역할:** 텍스트 → 768차원 벡터 변환 서비스

```
컨테이너명: polyon-embed
이미지: jupitertriangles/polyon-embed:v{semver}
포트: 4001
메모리: 2GB limit / 1GB request
CPU: 1000m limit / 200m request
```

**API:**
```
POST /embed           단일 텍스트 임베딩
POST /embed/batch     배치 임베딩 (최대 100건)
GET  /health          헬스체크
GET  /model/info      모델 정보 (이름, 차원, 로드 상태)
```

**E5 Prefix 처리:**
```python
# 문서 인덱싱 시
"passage: " + document_text

# 쿼리 검색 시  
"query: " + query_text
```

### 2.2 polyon-search (OpenSearch 확장)

**기존 인덱스에 knn_vector 필드 추가:**

```json
{
  "mappings": {
    "properties": {
      "id":        { "type": "keyword" },
      "module":    { "type": "keyword" },
      "resource_type": { "type": "keyword" },
      "resource_id":   { "type": "keyword" },
      "title":     { "type": "text", "analyzer": "standard" },
      "content":   { "type": "text", "analyzer": "standard" },
      "content_vector": {
        "type": "knn_vector",
        "dimension": 768,
        "method": {
          "name": "hnsw",
          "space_type": "cosinesimil",
          "engine": "faiss",
          "parameters": { "m": 16, "ef_construction": 100 }
        }
      },
      "owner":     { "type": "keyword" },
      "created_at": { "type": "date" },
      "updated_at": { "type": "date" },
      "metadata":  { "type": "object", "enabled": false }
    }
  },
  "settings": {
    "knn": true,
    "number_of_shards": 1,
    "number_of_replicas": 0
  }
}
```

**인덱스 명명 규칙:** `polyon_{module}` (예: `polyon_mail`, `polyon_drive`)

### 2.3 Core Search API

**파일:** `internal/api/search.go`

```
POST /search/index           문서 인덱싱 (embed + OS 저장)
GET  /search/query           통합 검색 (embed + Hybrid Search)
DELETE /search/index/{id}    문서 인덱스 삭제
GET  /search/status          Search Stack 상태
GET  /search/indices         인덱스 목록 및 통계
```

---

## 3. 인덱싱 흐름

```
모듈 (메일/드라이브/채팅 등)
    │
    ▼ POST /api/v1/search/index
    {
      "module": "mail",
      "resource_type": "email",
      "resource_id": "msg-12345",
      "title": "프로젝트 일정 조율",
      "content": "안녕하세요. 다음 주 회의 일정을 조율하고자...",
      "owner": "cmars",
      "metadata": { "from": "seol.choi@cmars.com" }
    }
    │
    ▼ Core
    polyon-embed POST /embed
    → vector: [0.123, -0.456, ...]  (768차원)
    │
    ▼ OpenSearch PUT polyon_mail/_doc/{id}
    {
      ...원본 필드...,
      "content_vector": [0.123, -0.456, ...]
    }
```

**비동기 처리:** 모듈은 fire-and-forget으로 인덱싱 요청. Core가 큐에 담아 처리.

---

## 4. 검색 흐름

```
사용자 쿼리: "계약 만료 예정 고객"
    │
    ▼ GET /api/v1/search/query?q=계약+만료+예정+고객&modules=mail,drive
    │
    ▼ Core
    polyon-embed POST /embed  (type=query)
    → query_vector: [0.234, -0.123, ...]
    │
    ▼ OpenSearch Hybrid Search
    {
      "query": {
        "bool": {
          "should": [
            {
              "multi_match": {
                "query": "계약 만료 예정 고객",
                "fields": ["title^2", "content"],
                "boost": 0.3
              }
            },
            {
              "knn": {
                "content_vector": {
                  "vector": [0.234, ...],
                  "k": 20,
                  "boost": 0.7
                }
              }
            }
          ]
        }
      },
      "size": 10
    }
    │
    ▼ 결과 반환 (score 통합, 중복 제거, 권한 필터)
```

---

## 5. PRC 클레임 설계

```yaml
# module.yaml 예시 (메일 모듈)
claims:
  - type: search
    config:
      index: mail
      schema:
        - field: subject
          os_type: text
          embed: false
        - field: body
          os_type: text
          embed: true        # 임베딩 대상
        - field: from_addr
          os_type: keyword
          embed: false
```

Core PRC Engine이 `search` 클레임을 처리할 때:
1. OpenSearch에 `polyon_{module}` 인덱스 생성 (knn_vector 포함)
2. 인덱스 정보를 `module_claims`에 저장
3. 환경변수로 `SEARCH_INDEX=polyon_mail` 주입

---

## 6. 모델 관리

### 초기 로딩

```dockerfile
# Dockerfile - 이미지 빌드 시 모델 다운로드 (560MB)
RUN python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('intfloat/multilingual-e5-base')
model.save('/app/models/multilingual-e5-base')
"
```

### RustFS 캐시 (선택)

PRC objectStorage 클레임으로 `embed-models` 버킷을 할당받아 모델 파일 저장.  
컨테이너 재시작 시 RustFS에서 로드 → Docker 이미지 크기 절감 가능.

---

## 7. 성능 최적화

### ONNX Runtime 적용 (Phase 2)

```python
# CPU 추론 속도 2-3배 향상
from optimum.onnxruntime import ORTModelForFeatureExtraction
model = ORTModelForFeatureExtraction.from_pretrained(
    'intfloat/multilingual-e5-base',
    export=True
)
```

### 배치 처리

```python
# 배치 크기 32 기준 최적화
vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
```

### 캐싱

- 동일 텍스트 반복 임베딩 방지: Redis LRU 캐시 (TTL: 1시간)
- 캐시 히트 예상: 쿼리의 약 30% (자주 쓰는 검색어)
