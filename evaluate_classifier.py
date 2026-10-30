"""
evaluate_classifier.py — 카드 문자 자동 분류 정확도 실험 (발표용)

data/labeled_test.csv에 있는 가상 카드 문자 50건을 분류해서
내가 정해둔 정답과 얼마나 맞는지 '기본 모드'와 'AI 모드'를 각각 비교합니다.

실행 방법 (터미널에서 money_planner 폴더 안에서):
    python3 evaluate_classifier.py          # 기본 모드 + (API 키가 있으면) AI 모드
    python3 evaluate_classifier.py --rule   # 기본 모드만

결과는 화면에 표로 나오고, data/eval_result_기본.csv / data/eval_result_AI.csv로도 저장돼요.
AI 모드는 API 사용료가 조금 나와요 (50건을 2번에 나눠 보냄).
"""
import os
import sys

import pandas as pd

import classifier

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_PATH = os.path.join(HERE, "data", "labeled_test.csv")


def evaluate(df, mode):
    """한 모드로 50건을 분류하고 정답과 비교한 표를 돌려준다."""
    result = classifier.classify_lines(df["문자"].tolist(), mode=mode)
    out = df.copy()
    out["예측 카테고리"] = [r["카테고리"] for r in result["rows"]]
    out["예측 금액"] = [r["금액"] for r in result["rows"]]
    out["뽑은 가게"] = [r["내용"] for r in result["rows"]]
    out["카테고리 정답"] = out["예측 카테고리"] == out["정답 카테고리"]
    out["금액 정답"] = out["예측 금액"] == out["정답 금액"]
    for w in result["warnings"]:
        print("  ⚠️", w)
    return out


def report(out, mode_name):
    n = len(out)
    cat_ok = int(out["카테고리 정답"].sum())
    amt_ok = int(out["금액 정답"].sum())
    unknown = int((out["예측 카테고리"] == classifier.UNKNOWN).sum())
    print(f"\n========== {mode_name} 모드 ==========")
    print(f"카테고리 정확도: {cat_ok}/{n} = {cat_ok / n * 100:.1f}%  (미분류 {unknown}건 포함)")
    print(f"금액 추출 정확도: {amt_ok}/{n} = {amt_ok / n * 100:.1f}%")

    # 카테고리별 정확도
    by_cat = out.groupby("정답 카테고리")["카테고리 정답"].agg(["sum", "count"])
    by_cat["정확도(%)"] = (by_cat["sum"] / by_cat["count"] * 100).round(1)
    print("\n[카테고리별 정확도]")
    print(by_cat.rename(columns={"sum": "맞음", "count": "전체"}).to_string())

    wrong = out[~out["카테고리 정답"] | ~out["금액 정답"]]
    if len(wrong):
        print(f"\n[틀린 건 {len(wrong)}개]")
        cols = ["문자", "정답 카테고리", "예측 카테고리", "정답 금액", "예측 금액", "메모"]
        with pd.option_context("display.max_colwidth", 45, "display.width", 200):
            print(wrong[cols].to_string(index=False))
    else:
        print("\n틀린 건이 없어요!")

    path = os.path.join(HERE, "data", f"eval_result_{mode_name}.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n결과 저장: {path}")
    return cat_ok / n


def main():
    df = pd.read_csv(TEST_PATH, encoding="utf-8-sig")
    print(f"테스트 데이터: {len(df)}건 (가상 카드 문자)")

    scores = {"기본": report(evaluate(df, "rule"), "기본")}

    if "--rule" in sys.argv:
        pass
    elif classifier.ai_available():
        scores["AI"] = report(evaluate(df, "ai"), "AI")
    else:
        print("\n(AI 모드는 건너뜀: ANTHROPIC_API_KEY가 설정돼 있지 않아요. README의 'AI 대화 켜기' 참고)")

    print("\n========== 요약 ==========")
    for name, score in scores.items():
        print(f"{name} 모드 카테고리 정확도: {score * 100:.1f}%")


if __name__ == "__main__":
    main()
