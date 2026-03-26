"""
preprocess.py
RunRepeat 원본 데이터를 Azure AI Search 업로드용으로 변환하는 모듈.
Raw CSV → feature 생성 → shoes_recommendation_ready.csv / shoes_upload.json
"""

import pandas as pd
import re
import json


# ─────────────────────────────────────────
# Feature 변환 함수
# ─────────────────────────────────────────

def convert_cushion(heel, forefoot):
    """힐·포어풋 쿠션 수치 → high / medium / low"""
    try:
        avg = (float(heel) + float(forefoot)) / 2
    except Exception:
        return "medium"

    if avg >= 38:
        return "high"
    elif avg >= 28:
        return "medium"
    else:
        return "low"


def convert_stability(row):
    """아치 지지력 + 비틀림 강성 → stability / neutral"""
    try:
        arch = float(row.get("Arch support", 0))
        torsion = float(row.get("Torsional rigidity", 0))
        if arch >= 4 or torsion >= 4:
            return "stability"
        return "neutral"
    except Exception:
        return "neutral"


def convert_usage(weight):
    """무게(g) 기준 사용 용도 분류"""
    try:
        w = float(weight)
    except Exception:
        return ["daily_run"]

    if w <= 230:
        return ["race"]
    elif w <= 260:
        return ["daily_run"]
    elif w <= 300:
        return ["long_run"]
    else:
        return ["recovery"]


def convert_foot_type(row):
    """아치 지지력 기준 발 타입 분류"""
    try:
        arch = float(row.get("Arch support", 0))
        if arch >= 4:
            return ["flat"]
        elif arch <= 2:
            return ["high_arch"]
        return ["neutral"]
    except Exception:
        return ["neutral"]


def convert_width(x):
    """Width/fit 컬럼 → wide_fit boolean"""
    if pd.isna(x):
        return False
    return "wide" in str(x).lower()


def extract_brand(name):
    """신발 이름에서 브랜드 추출"""
    name = str(name)
    prefixes = ["New Balance", "ASICS", "Nike", "Hoka", "Brooks", "Adidas", "On", "PUMA"]
    for prefix in prefixes:
        if name.startswith(prefix):
            return prefix
    return name.split()[0]


def clean_price(p):
    """원화(₩) / 달러($) / 유로(€) → 원화 정수 변환"""
    if pd.isna(p):
        return 0
    s = str(p).replace(",", "").strip()
    try:
        if "₩" in s:
            return int(s.replace("₩", ""))
        elif "$" in s:
            return int(float(s.replace("$", "")) * 1300)
        elif "€" in s:
            return int(float(s.replace("€", "")) * 1400)
        else:
            return int(float(s))
    except Exception:
        return 0


def make_id(name):
    """신발 이름 → snake_case ID"""
    name = str(name).lower()
    name = re.sub(r"[^a-z0-9 ]", "", name)
    return name.replace(" ", "_")


# ─────────────────────────────────────────
# 파이프라인 실행
# ─────────────────────────────────────────

def run(input_path: str, csv_out: str, json_out: str):
    df = pd.read_csv(input_path)

    df["cushion_level"] = df.apply(
        lambda x: convert_cushion(x.get("Heel Lab"), x.get("Forefoot Lab")), axis=1
    )
    df["stability"] = df.apply(convert_stability, axis=1)
    df["usage"] = df["Weight Lab"].apply(convert_usage)
    df["foot_type"] = df.apply(convert_foot_type, axis=1)
    df["wide_fit"] = df["Width / fit"].apply(convert_width)
    df["brand"] = df["name"].apply(extract_brand)
    df["price"] = df["Price"].apply(clean_price)
    df["id"] = df["name"].apply(make_id)

    final_df = df[[
        "id", "name", "brand", "price",
        "cushion_level", "stability",
        "foot_type", "usage", "wide_fit"
    ]].dropna(subset=["name"])

    # CSV 저장
    final_df.to_csv(csv_out, index=False, encoding="utf-8-sig")
    print(f"CSV 저장 완료: {csv_out}")

    # Azure Search 업로드용 JSON 저장
    data = final_df.to_dict(orient="records")
    for item in data:
        item["@search.action"] = "upload"

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump({"value": data}, f, indent=2, ensure_ascii=False)
    print(f"JSON 저장 완료: {json_out}")


if __name__ == "__main__":
    run(
        input_path="data/processed/RunRepeat_final.csv",
        csv_out="data/processed/shoes_recommendation_ready.csv",
        json_out="data/processed/shoes_upload.json",
    )
