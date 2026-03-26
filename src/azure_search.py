"""
azure_search.py
Azure AI Search와의 연동을 담당하는 모듈.

주요 기능:
- 문서 업로드 (/indexes/{index}/docs/index)
- Hybrid 검색 (filter + semantic + vector)

시행착오 반영:
- /docs → 검색용, /docs/index → 업로드용 (혼동 주의)
"""

import os
import json
import requests


# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────

SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
SEARCH_API_KEY = os.environ["SEARCH_API_KEY"]
SEARCH_INDEX = os.environ.get("SEARCH_INDEX", "shoes")
API_VERSION = "2024-07-01"


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "api-key": SEARCH_API_KEY,
    }


# ─────────────────────────────────────────
# 문서 업로드
# ─────────────────────────────────────────

def upload_documents(json_path: str) -> dict:
    """
    shoes_upload.json을 Azure AI Search 인덱스에 업로드.
    엔드포인트: /indexes/{index}/docs/index  ← /docs/search 와 다름 (주의)
    """
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/index?api-version={API_VERSION}"

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    res = requests.post(url, headers=_headers(), json=payload)
    res.raise_for_status()
    print(f"업로드 완료: {res.status_code}")
    return res.json()


# ─────────────────────────────────────────
# 검색
# ─────────────────────────────────────────

def search(
    query: str,
    filter_query: str | None = None,
    top: int = 5,
) -> list[dict]:
    """
    Hybrid 검색: semantic + vector + filter 조합.

    Args:
        query: 영어 키워드 (번역된 쿼리)
        filter_query: OData 필터 문자열 (예: "price le 300000 and foot_type/any(f: f eq 'neutral')")
        top: 반환할 최대 결과 수

    Returns:
        rerankerScore 기준 정렬된 문서 리스트
    """
    url = f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version={API_VERSION}"

    body = {
        "search": query,
        "vectorQueries": [
            {
                "kind": "text",
                "text": query,
                "fields": "embedding",
                "k": 10,
            }
        ],
        "queryType": "semantic",
        "semanticConfiguration": "semantic-config",
        "top": top,
    }

    if filter_query:
        body["filter"] = filter_query

    try:
        res = requests.post(url, headers=_headers(), json=body)
        res.raise_for_status()
        docs = res.json().get("value", [])
        return sorted(docs, key=lambda x: x.get("@search.rerankerScore", 0), reverse=True)
    except requests.RequestException as e:
        print(f"[ERROR] 검색 실패: {e}")
        return []
