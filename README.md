# PolyON Embed

**PP 플랫폼의 의미 기반 검색 인프라 — multilingual-e5-base 임베딩 서비스**

---

## 개요

`polyon-embed`는 PolyON Platform의 **Foundation 확장 컴포넌트**입니다.

OpenSearch(BM25 키워드 검색)만으로는 한계가 있는 **자연어/의미 기반 검색**을 가능하게 합니다. `multilingual-e5-base` 모델을 사용해 100개 언어의 텍스트를 768차원 벡터로 변환하고, OpenSearch kNN과 결합해 **Hybrid Search(의미 + 키워드)**를 제공합니다.

---

## 관련 문서

- [전략 및 목표](docs/STRATEGY.md)
- [아키텍처 설계](docs/ARCHITECTURE.md)
- [구현 가이드](docs/IMPLEMENTATION.md)
