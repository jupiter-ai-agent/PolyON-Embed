# PolyON Embed — 전략 및 목표

**작성일:** 2026-03-15  
**작성자:** Jupiter (AI 팀장, Triangle.s)  
**승인:** CMARS (대표)

---

## 1. 배경 및 문제 인식

### 1.1 현재 PP 검색의 한계

PolyON Platform은 OpenSearch(ES 호환)를 Foundation 검색 인프라로 채택하고 있습니다.  
OpenSearch의 기본 검색 방식인 **BM25(키워드 매칭)**는 다음과 같은 본질적 한계를 가집니다.

| 한계 | 예시 |
|------|------|
| **동의어 처리 불가** | "휴가" 검색 시 "연차" 문서 누락 |
| **의미 기반 검색 불가** | "계약 만료 임박" 검색 시 관련 메일 누락 |
| **다국어 의미 연결 불가** | 한국어 질의로 영어 문서 검색 불가 |
| **오타/유사어 처리 제한** | "회의록" 검색 시 "미팅 노트" 누락 |

### 1.2 비즈니스 임팩트

PolyON이 지향하는 **Workstream(업무 중심 그룹웨어)** 비전에서 검색은 핵심입니다.

- 사원이 "이 프로젝트 관련 메일 다 찾아줘"라고 할 때
- 관리자가 "지난 달 계약 관련 문서 모두 보여줘"라고 할 때
- AI Agent가 컨텍스트를 구성하기 위해 관련 문서를 찾을 때

단순 키워드 검색으로는 이를 만족시킬 수 없습니다.

---

## 2. 전략

### 2.1 핵심 전략: BM25 + k-NN 하이브리드 검색

```
BM25 (키워드 정확도) + k-NN (의미 유사도) = Hybrid Search
```

두 방식을 결합해 정확도와 재현율을 모두 높입니다.

- **BM25**: 정확한 키워드 매칭 (기존 강점 유지)
- **k-NN**: 의미적으로 유사한 문서 발견 (신규 능력)
- **Boost 가중치**: 검색 유형에 따라 조정 (기본 BM25:0.3 / k-NN:0.7)

### 2.2 모델 선택: multilingual-e5-base

**선택 근거:**

| 항목 | 내용 |
|------|------|
| 모델 | `intfloat/multilingual-e5-base` |
| 지원 언어 | 100개 언어 (한국어 포함) |
| 벡터 차원 | 768 |
| 모델 크기 | ~560MB |
| 라이선스 | MIT |
| 특징 | E5 prefix 방식으로 문서/쿼리 구분 처리 |
| 참고 | [Elastic 블로그](https://www.elastic.co/search-labs/blog/multilingual-vector-search-e5-embedding-model) |

**E5 Prefix 규칙 (품질에 중요):**
```
문서 인덱싱: "passage: {문서 내용}"
쿼리 검색:  "query: {검색어}"
```

### 2.3 아키텍처 원칙

**독립 컨테이너 원칙 (PP 제6원칙 준수)**

`polyon-embed`를 OpenSearch에 통합하지 않고 독립 컨테이너로 분리합니다.

```
이유:
1. 모델 독립 업그레이드 (e5-base → e5-large, 혹은 다른 모델)
2. 메모리 격리 (OpenSearch 1GB + Embed 2GB 별도 관리)
3. CPU 최적화 적용 가능 (ONNX Runtime, quantization)
4. 단일 책임 원칙 — 임베딩 생성에만 집중
```

---

## 3. 목표

### 3.1 단기 목표 (Phase 1)

- [ ] `polyon-embed` 컨테이너 구축 (FastAPI + sentence-transformers)
- [ ] OpenSearch knn_vector 인덱스 스키마 정의
- [ ] Core `/search/index`, `/search/query` API 구현
- [ ] 메일(Stalwart) 인덱싱 연동 — 첫 번째 모듈
- [ ] Console Search Stack 모니터링 메뉴

### 3.2 중기 목표 (Phase 2)

- [ ] 모든 Foundation 모듈 인덱싱 연동
  - 메일 (Stalwart)
  - 드라이브 (Nextcloud)
  - 채팅 (Mattermost)
  - ERP (Odoo)
  - 위키 (AFFiNE)
- [ ] 실시간 인덱싱 (Webhook/Event 기반)
- [ ] 검색 결과 랭킹 튜닝 (Boost 가중치 최적화)

### 3.3 장기 목표 (Phase 3)

- [ ] AI Agent 컨텍스트 공급 (RAG — Retrieval Augmented Generation)
- [ ] 개인화 검색 (사용자별 접근 권한 필터)
- [ ] 크로스 모듈 통합 검색 (메일 + 문서 + 채팅 한 번에)
- [ ] 다국어 질의 → 다국어 결과 (언어 무관 검색)

---

## 4. PP 플랫폼 내 위치

### 4.1 Foundation 확장 컴포넌트

```
Foundation (필수)           Foundation (확장)
├── PostgreSQL               └── polyon-embed ← 여기
├── Redis
├── OpenSearch  ─────────────────┐
├── RustFS                       │ knn_vector 저장/조회
├── Samba DC                     │
├── Keycloak                     │
└── Stalwart                     │
                                 ▼
              PolyON Search Stack
              (OpenSearch + polyon-embed)
```

**분류 기준:**
- 없어도 기본 기능(BM25 검색) 작동 → 필수 Foundation 아님
- 모든 모듈이 의미 검색에 의존 가능 → Module 아님
- 플랫폼 레벨 서비스 → **Foundation 확장**으로 분류

### 4.2 PRC (Platform Resource Claim)

다른 모듈이 검색 인덱싱을 선언할 때:

```yaml
claims:
  - type: search          # 신규 PRC 타입
    config:
      index: mail         # 인덱스명
      fields:             # 인덱싱할 필드
        - name: subject
          type: text
        - name: body
          type: semantic  # embed 처리 대상
```

---

## 5. 성능 목표 (CPU 환경)

| 지표 | 목표값 | 비고 |
|------|--------|------|
| 쿼리 임베딩 지연 | < 200ms | 사용자 체감 허용 범위 |
| 문서 인덱싱 처리량 | > 10건/초 | 배치 처리 기준 |
| 메모리 사용량 | < 2GB | PP 서버 32GB 기준 여유 |
| 검색 정확도 향상 | BM25 대비 +20% | MRR@10 기준 |

PP 서버 스펙: Intel Xeon E5-2620 v3 (12코어), 32GB RAM — CPU 추론 충분히 가능.

---

## 6. 제약 및 리스크

| 리스크 | 대응 |
|--------|------|
| 첫 구동 시 모델 다운로드 (~560MB) | Docker 이미지에 모델 번들 또는 RustFS에 캐시 |
| CPU 추론 속도 | 배치 인덱싱은 비동기, ONNX Runtime 적용 검토 |
| OpenSearch kNN 메모리 오버헤드 | HNSW 파라미터 튜닝 (m=16, ef_construction=100) |
| 인덱스 마이그레이션 | 기존 OS 인덱스와 별도 knn 인덱스 병행 운영 |

---

## 7. 성공 기준

> "사용자가 한국어로 '이번 달 계약 관련 내용'을 검색했을 때,  
> 계약서 파일, 관련 메일, 채팅 메시지를 언어/형식과 무관하게 한 번에 찾을 수 있다."

이것이 PolyON Embed의 최종 목표입니다.
