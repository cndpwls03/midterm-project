"""
consult.py — 'AI 재무설계사와 상담하기' 채팅의 기본 모드 답변

- AI 모드: llm.reply()가 내 사실 목록 + 모든 제도 자료(knowledge.py)를 근거로 답해요.
- 기본 모드(API 키 없음): rule_answer()가 질문 속 제도 이름을 찾아 쉬운 설명으로 답해요.
  (목표별 제도·상품 추천은 평생 플랜의 목표 페이지 → portfolio.py)

원칙: 특정 금융사 상품은 추천하지 않고 '제도·상품 유형'까지만. 제도 조건은 자료(기준일)에 있는 것만.
"""
import re

import character as ch
import knowledge as kn
import llm

# ---------------------------------------------------------------
# '이거 사도 돼?' — 채팅 질문에서 물건·가격을 찾아낸다 (계산은 planner.purchase_impact)
# ---------------------------------------------------------------
BUY_WORDS = ["사도 돼", "사도돼", "사도 될까", "사도될까", "살까", "사고 싶", "사려고", "질러", "지를까", "사도 괜찮"]
PRICE_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(만|천)?\s*원|(\d[\d,]*(?:\.\d+)?)\s*만")
HOLD_WORDS = ["참을", "안 살", "안살", "그만둘", "포기"]
BUY_OK_WORDS = ["살래", "살게", "사야지", "살 거야", "살거야", "그래도 사"]


def parse_purchase(text):
    """
    '신발 12만 원 사도 돼?' → ("신발", 12)  (가격 단위: 만 원)
    사려는 질문이 아니면 None, 사려는 질문인데 가격이 없으면 (물건, None)
    """
    if not any(w in text for w in BUY_WORDS):
        return None
    m = PRICE_RE.search(text)
    price = None
    if m:
        if m.group(1):
            n = float(m.group(1).replace(",", ""))
            price = n if m.group(2) == "만" else n / 10 if m.group(2) == "천" else n / 10000
        else:
            price = float(m.group(3).replace(",", ""))
    # 물건 이름: 가격 앞에 쓴 말이 있으면 그걸, 없으면 문장에서 '사도 돼' 같은 말을 뺀 나머지
    item = text[:m.start()] if m and text[:m.start()].strip() else PRICE_RE.sub(" ", text)
    item = re.sub(r"^(이|저|그)\s+", "", item.strip())
    for w in BUY_WORDS + ["이거", "그거", "?", "!", "짜리", "정도", "쯤"]:
        item = item.replace(w, " ")
    item = re.sub(r"\s+", " ", item).strip(" ,.~") or "그거"
    item = re.sub(r"(을|를|은|는|이|가)$", "", item).strip() or "그거"
    return item[:20], (round(price, 1) if price else None)


def decision_of(text):
    """'이거 사도 돼?' 답 뒤에 '참을게'·'살래'라고 하면 'hold' / 'buy', 아니면 None"""
    if any(w in text for w in HOLD_WORDS):
        return "hold"
    if any(w in text for w in BUY_OK_WORDS):
        return "buy"
    return None


def explain(concept) -> str:
    """개념 하나를 대화 말투로 설명"""
    points = "\n".join(f"· {p}" for p in concept["points"])
    return (f"{concept['emoji']} {concept['name']} — {concept['one_line']}\n{points}\n"
            f"이런 사람에게 좋아: {concept['for_whom']}\n"
            f"⚠️ {concept['caution']}\n(기준일 {kn.BASE_DATE} · 가입 전에 공식 안내를 꼭 확인해줘)")


def rule_answer(text, topic=None, plan=None):
    """기본 모드 답변: 질문 속 제도 이름을 찾아 설명. 없으면 이번 달 계획이나 간단한 안내."""
    concept = kn.find_concept(text, topic)
    if concept:
        return explain(concept)
    if plan is not None and any(k in text for k in ["나눠", "얼마", "비율", "시작"]):
        parts = [f"비상금 {ch.fmt(plan.emergency)}"] + [f"{it.goal.name} {ch.fmt(it.alloc)}" for it in plan.items[:3]]
        if plan.extra:
            parts.append(f"노후 자금 {ch.fmt(plan.extra)}")
        return ("이번 달 계획으로는 " + ", ".join(parts) + "씩 나누면 돼. "
                "자세한 건 '💰 이번 달 플랜' 탭에서 볼 수 있어!")
    return llm._rule_reply(text)
