"""
recommender.py
추천 로직을 담당하는 모듈.

파이프라인:
  사용자 자연어 입력
  → GPT 번역 (한→영 키워드)
  → OData 필터 생성
  → Azure AI Search (Hybrid)
  → GPT 추천 설명 생성
"""

import os
from openai import AzureOpenAI
from src.azure_search import search


# ─────────────────────────────────────────
# Azure OpenAI 클라이언트
# ─────────────────────────────────────────

client = AzureOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    api_version="2024-02-01",
    azure_endpoint=os.environ["OPENAI_ENDPOINT"],
)

DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]


# ─────────────────────────────────────────
# 한→영 키워드 번역
# ─────────────────────────────────────────

def translate(query: str) -> str:
    """한국어 러닝화 문의 → 영어 키워드 2~3개"""
    try:
        res = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "Translate the user's running shoe inquiry into 2-3 concise English keywords. Return ONLY keywords.",
                },
                {"role": "user", "content": query},
            ],
            temperature=0,
        )
        return res.choices[0].message.content.strip()
    except Exception:
        return query


# ─────────────────────────────────────────
# OData 필터 생성
# ─────────────────────────────────────────

FOOT_MAP = {
    "중립": "neutral",
    "과내전": "overpronation",
    "모름": None,
}

USAGE_MAP = {
    "데일리런": "daily_run",
    "레이스": "race",
}

MAX_PRICE = 540000


def build_filter(
    foot: list[str],
    usage: list[str],
    price_val: int,
) -> str | None:
    """UI 입력값을 Azure AI Search OData 필터 문자열로 변환"""
    filters = []

    if foot:
        mapped = [FOOT_MAP[f] for f in foot if FOOT_MAP.get(f)]
        if mapped:
            filters.append(f"foot_type/any(f: f eq '{mapped[0]}')")

    if usage:
        u_filters = [
            f"usage/any(u: u eq '{USAGE_MAP[u]}')"
            for u in usage
            if u in USAGE_MAP
        ]
        if u_filters:
            filters.append("(" + " or ".join(u_filters) + ")")

    if price_val and price_val < MAX_PRICE:
        filters.append(f"price le {price_val}")

    return " and ".join(filters) if filters else None


# ─────────────────────────────────────────
# GPT 추천 설명 생성
# ─────────────────────────────────────────

def generate_answer(
    query: str,
    docs: list[dict],
    history: list[dict],
) -> str:
    """검색 결과를 바탕으로 친절한 한국어 추천 설명 생성"""
    if not docs:
        return (
            "죄송합니다. 현재 필터 조건에 맞는 제품을 찾을 수 없습니다. "
            "예산을 높이거나 필터를 해제해 보시겠어요?"
        )

    context = "\n".join([
        f"- {d.get('name')} | {int(d.get('price') or 0):,}원 | {d.get('description', '')[:100]}"
        for d in docs
    ])

    messages = [
        {
            "role": "system",
            "content": (
                "러닝화 매장 매니저로서 Context를 기반으로 제품을 추천하세요. "
                "친절한 한국어로 답변하고, 제품의 가격과 장점을 명확히 설명하세요."
            ),
        }
    ]
    messages += history[-6:]
    messages.append({
        "role": "user",
        "content": f"[검색결과]\n{context}\n\n질문: {query}",
    })

    res = client.chat.completions.create(
        model=DEPLOYMENT,
        messages=messages,
    )
    return res.choices[0].message.content


# ─────────────────────────────────────────
# 메인 추천 함수
# ─────────────────────────────────────────

def recommend(
    message: str,
    history: list[dict],
    foot: list[str],
    usage: list[str],
    price_val: int,
) -> tuple[list[dict], str]:
    """
    Gradio chat_process에서 호출하는 통합 함수.

    Returns:
        (업데이트된 history, 빈 문자열)
    """
    if history is None:
        history = []
    if not message:
        return history, ""

    query_en = translate(message)
    filter_q = build_filter(foot, usage, price_val)
    docs = search(query_en, filter_q)
    answer = generate_answer(message, docs, history)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    return history, ""
