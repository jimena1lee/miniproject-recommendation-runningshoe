"""
gpt_summarize.py
verdict + pros + cons 텍스트를 GPT로 요약하여
description / review_summary 컬럼을 생성하는 모듈.

시행착오 반영:
- GPT 응답이 JSON 형식이 아닐 수 있음 → regex 추출 + fallback 처리
"""

import pandas as pd
import re
import json
import time
import os
from openai import AzureOpenAI


# ─────────────────────────────────────────
# Azure OpenAI 클라이언트 초기화
# ─────────────────────────────────────────

client = AzureOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    api_version="2024-02-01",
    azure_endpoint=os.environ["OPENAI_ENDPOINT"],
)

DEPLOYMENT = os.environ["OPENAI_DEPLOYMENT"]


# ─────────────────────────────────────────
# GPT 요약 함수
# ─────────────────────────────────────────

SYSTEM_PROMPT = """
당신은 러닝화 전문 리뷰어입니다.
아래 정보를 바탕으로 JSON 형식으로만 답하세요. 다른 문장은 절대 포함하지 마세요.

형식:
{
  "description": "150자 이내의 제품 설명 (특징, 용도 중심)",
  "review_summary": "100자 이내의 한 줄 평가 (장단점 요약)"
}
"""


def extract_json_from_text(text: str) -> dict:
    """GPT 응답에서 JSON 부분만 추출 (파싱 실패 대비 regex fallback)"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # regex로 JSON 블록 추출
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


def summarize_shoe(name: str, verdict: str, pros: str, cons: str) -> dict:
    """단일 신발 요약 생성. 실패 시 빈 문자열 반환"""
    prompt = f"""
신발명: {name}
리뷰: {verdict}
장점: {pros}
단점: {cons}
"""
    try:
        res = client.chat.completions.create(
            model=DEPLOYMENT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = res.choices[0].message.content.strip()
        parsed = extract_json_from_text(text)
        return {
            "description": parsed.get("description", ""),
            "review_summary": parsed.get("review_summary", ""),
        }
    except Exception as e:
        print(f"[WARN] {name} 요약 실패: {e}")
        return {"description": "", "review_summary": ""}


# ─────────────────────────────────────────
# 파이프라인 실행
# ─────────────────────────────────────────

def run(input_path: str, output_path: str, delay: float = 1.0):
    """
    input_path: verdict/pros/cons 컬럼이 있는 CSV
    output_path: description/review_summary 추가된 CSV
    delay: API 호출 간격 (초) - Rate limit 방지
    """
    df = pd.read_csv(input_path)

    descriptions = []
    summaries = []

    for _, row in df.iterrows():
        result = summarize_shoe(
            name=row.get("name", ""),
            verdict=row.get("verdict", ""),
            pros=row.get("pros", ""),
            cons=row.get("cons", ""),
        )
        descriptions.append(result["description"])
        summaries.append(result["review_summary"])
        print(f"완료: {row.get('name', '')}")
        time.sleep(delay)

    df["description"] = descriptions
    df["review_summary"] = summaries

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n저장 완료: {output_path}")


if __name__ == "__main__":
    run(
        input_path="data/raw/RunRepeat_raw.csv",
        output_path="data/processed/RunRepeat_final.csv",
    )
