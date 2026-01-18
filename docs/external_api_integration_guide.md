# GuRag API 외부 연동 가이드

**문서 버전**: 1.0
**작성일**: 2026-01-18
**대상**: 외부 사이트 운영자 및 개발자

---

## 1. 개요

GuRag API는 AI 기반 검색 서비스로, 질의(Query)를 보내면 관련 정보를 검색하고 AI가 생성한 답변을 반환합니다.

### 주요 특징
- REST API 방식
- 별도 인증 불필요 (Public API)
- 모든 도메인에서 호출 가능 (CORS 허용)
- JSON 형식 요청/응답

---

## 2. API 정보

### 기본 정보

| 항목 | 값 |
|------|-----|
| **API 주소** | `https://incremental-rag.onrender.com` |
| **프로토콜** | HTTPS |
| **인증** | 불필요 |
| **응답 형식** | JSON |

### 엔드포인트 목록

| 엔드포인트 | Method | 설명 |
|-----------|--------|------|
| `/search` | POST | 질의 검색 및 AI 답변 생성 |
| `/status` | GET | 시스템 상태 확인 |
| `/docs` | GET | API 문서 (Swagger UI) |

---

## 3. 검색 API 상세

### 요청 (Request)

**URL**
```
POST https://incremental-rag.onrender.com/search
```

**Headers**
```
Content-Type: application/json
```

**Body**
```json
{
  "query": "검색할 질문 내용"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| query | string | ✅ | 검색할 질문 (1~1000자) |

### 응답 (Response)

**성공 시 (HTTP 200)**
```json
{
  "query": "사용자가 보낸 원본 질문",
  "response": "AI가 생성한 답변 텍스트",
  "sources": [
    {
      "source_type": "arxiv_paper | huggingface | expert_insight | manual",
      "title": "출처 제목",
      "url": "출처 URL",
      "author": "저자",
      "relevance_score": 0.95
    }
  ],
  "search_path": "cache | vector_db | mcp | not_found",
  "processing_time_ms": 1234.56,
  "keywords": ["추출된", "키워드", "목록"]
}
```

**응답 필드 설명**

| 필드 | 타입 | 설명 |
|------|------|------|
| query | string | 원본 질의 |
| response | string | AI 생성 답변 |
| sources | array | 참조 출처 목록 |
| search_path | string | 검색 경로 (cache/vector_db/mcp/not_found) |
| processing_time_ms | number | 처리 시간 (밀리초) |
| keywords | array | 추출된 키워드 |

---

## 4. 연동 예제 코드

### JavaScript (Fetch API)

```javascript
async function searchGuRag(query) {
  const response = await fetch('https://incremental-rag.onrender.com/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: query }),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }

  return await response.json();
}

// 사용 예시
try {
  const result = await searchGuRag('What is machine learning?');
  console.log('답변:', result.response);
  console.log('출처:', result.sources);
} catch (error) {
  console.error('검색 실패:', error);
}
```

### JavaScript (Axios)

```javascript
const axios = require('axios');

async function searchGuRag(query) {
  const response = await axios.post(
    'https://incremental-rag.onrender.com/search',
    { query: query },
    { headers: { 'Content-Type': 'application/json' } }
  );
  return response.data;
}

// 사용 예시
const result = await searchGuRag('Explain neural networks');
console.log(result.response);
```

### Node.js (Express 연동)

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/api/search', async (req, res) => {
  try {
    const { query } = req.body;

    const response = await fetch('https://incremental-rag.onrender.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    const data = await response.json();
    res.json(data);

  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(3000);
```

### Python (requests)

```python
import requests

def search_gurag(query):
    response = requests.post(
        'https://incremental-rag.onrender.com/search',
        json={'query': query},
        headers={'Content-Type': 'application/json'}
    )
    response.raise_for_status()
    return response.json()

# 사용 예시
result = search_gurag('What is deep learning?')
print(result['response'])
```

### cURL

```bash
curl -X POST https://incremental-rag.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What is transformer architecture?"}'
```

---

## 5. 에러 처리

### HTTP 상태 코드

| 코드 | 설명 | 대응 방법 |
|------|------|----------|
| 200 | 성공 | 정상 처리 |
| 400 | 잘못된 요청 | query 필드 확인 |
| 500 | 서버 오류 | 재시도 또는 문의 |
| 502/503 | 서버 일시 중단 | 잠시 후 재시도 |

### 에러 응답 형식

```json
{
  "detail": "에러 메시지"
}
```

### 권장 에러 처리

```javascript
async function searchWithRetry(query, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch('https://incremental-rag.onrender.com/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });

      if (response.ok) {
        return await response.json();
      }

      if (response.status >= 500) {
        // 서버 오류 시 재시도
        await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        continue;
      }

      throw new Error(`API Error: ${response.status}`);

    } catch (error) {
      if (i === maxRetries - 1) throw error;
    }
  }
}
```

---

## 6. 권장 사항

### 타임아웃 설정
- **권장 타임아웃**: 60초
- 첫 요청 시 서버 콜드 스타트로 인해 응답이 느릴 수 있음

### 요청 빈도
- 과도한 요청 자제 (초당 10회 이하 권장)
- 동일 쿼리 반복 시 캐시 활용으로 빠른 응답

### 응답 활용
- `response` 필드: 사용자에게 표시할 메인 답변
- `sources` 필드: 출처 표시로 신뢰성 확보
- `search_path` 필드: 디버깅 및 성능 모니터링용

---

## 7. 테스트 방법

### 1) 브라우저에서 테스트
API 문서 페이지에서 직접 테스트:
```
https://incremental-rag.onrender.com/docs
```

### 2) cURL로 테스트
```bash
# 상태 확인
curl https://incremental-rag.onrender.com/status

# 검색 테스트
curl -X POST https://incremental-rag.onrender.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'
```

### 3) 온라인 도구
- Postman
- Insomnia
- HTTPie

---

## 8. 기술 지원

### API 문서
- Swagger UI: https://incremental-rag.onrender.com/docs
- ReDoc: https://incremental-rag.onrender.com/redoc

### 상태 확인
```
GET https://incremental-rag.onrender.com/status
```

응답 예시:
```json
{
  "status": "healthy",
  "database_connected": true,
  "cache_entries": 10,
  "knowledge_entries": 4,
  "cache_hit_rate": 0.5
}
```

---

## 9. 요약

| 항목 | 내용 |
|------|------|
| **API URL** | `https://incremental-rag.onrender.com/search` |
| **Method** | `POST` |
| **Content-Type** | `application/json` |
| **Request Body** | `{"query": "질문 내용"}` |
| **인증** | 불필요 |
| **타임아웃** | 60초 권장 |

---

**문서 끝**
