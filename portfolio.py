"""
portfolio.py — 장기 목표별 AI 추천 포트폴리오 (평생 플랜의 목표 페이지)

예) 결혼 자금에 매달 28만 원을 넣는다면 → 청년미래적금 20만 + 자유적금 3만 + ISA 안 분산 ETF 5만

역할 나누기 (다른 AI 기능과 같음)
1. 앱이 정한다: 매달 넣을 돈(base), 성향·기간에 맞는 투자 비중, 고를 수 있는 제도·상품 유형 목록(CANDIDATES)
2. AI가 고른다: 그 목록 안에서 무엇에 얼마씩 나눌지 + 내 상황에 맞춘 이유·방법·주의점
3. 앱이 검사한다(check): 목록에 없는 상품은 버림, 금액 합계, 투자 비중, 제도 한도·나이 조건, 글 속 숫자
API 키가 없으면 rule_portfolio()가 정해진 규칙으로 같은 형식의 포트폴리오를 만들어요.
특정 금융사 상품은 다루지 않고 제도·상품 유형까지만 추천해요.
"""
import datetime
import hashlib
import json

import advisor as adv
import character as ch
import knowledge as kn
import llm
import planner as pl

# 제도·상품 유형: 종류(안전/투자/연금), 한 달 최대(만 원, 없으면 None), 짧은 설명
PRODUCTS = {
    "청년미래적금": ("안전", 50, "만 19~34세, 3년 동안 모으면 정부기여금을 보태줌"),
    "주택청약종합저축": ("안전", 25, "분양 신청 자격을 쌓는 통장, 공공분양은 월 25만 원까지 납입 인정"),
    "자유적금·정기적금": ("안전", None, "기한에 맞춰 원금을 지키며 모으는 기본 상품"),
    "정기예금": ("안전", None, "모아둔 목돈을 기한까지 안전하게 맡겨두기"),
    "파킹통장": ("안전", None, "언제든 꺼낼 수 있는 통장, 쓸 날이 가까운 돈"),
    "ISA 계좌 안 분산 ETF": ("투자", None, "세금 혜택 계좌(ISA)에서 여러 종목에 나눠 투자"),
    "적립식 분산 펀드·ETF": ("투자", None, "매달 나눠서 여러 곳에 분산 투자"),
    "연금저축펀드": ("연금", 50, "연 600만 원까지 세액공제, 55세 이후 연금으로 받음"),
    "IRP": ("연금", 75, "연금저축과 합쳐 연 900만 원까지 세액공제, 퇴직금도 받는 계좌"),
}
# 목표 종류마다 고를 수 있는 후보
CANDIDATES = {
    "결혼 자금": ["청년미래적금", "자유적금·정기적금", "정기예금", "파킹통장", "ISA 계좌 안 분산 ETF"],
    "내 집 마련": ["주택청약종합저축", "청년미래적금", "자유적금·정기적금", "정기예금", "ISA 계좌 안 분산 ETF"],
    "노후 준비": ["연금저축펀드", "IRP", "ISA 계좌 안 분산 ETF", "적립식 분산 펀드·ETF", "정기예금"],
    "기타 장기 목표": ["청년미래적금", "자유적금·정기적금", "정기예금", "ISA 계좌 안 분산 ETF", "적립식 분산 펀드·ETF"],
}
YOUTH_AGE = (19, 34)       # 청년미래적금 나이 조건 (knowledge.py 기준)


# ---------------------------------------------------------------
# 1. 목표 페이지의 '사실 목록' (숫자는 모두 앱이 계산)
# ---------------------------------------------------------------
def goal_facts(gtype, name, base, invest_ratio, months, profile, extra_lines=()):
    age = int(profile.current_age)
    invest = round(base * invest_ratio)
    lines = [
        f"[사용자] {age}세, {profile.job}, 투자 성향 {profile.risk}, 세후 월급 {ch.fmt(profile.income)}",
        f"[목표] {name} ({gtype}), 기한 {ch.years_months(months)}" if months else f"[목표] {name} ({gtype})",
        f"[매달 넣을 돈] {base}만 원 — 성향·기간 기준 투자 비중 {round(invest_ratio * 100)}% "
        f"(안전 자산 {base - invest}만 원, 투자 {invest}만 원)",
        "[고를 수 있는 제도·상품 유형] " + " / ".join(
            f"{n}({PRODUCTS[n][0]}" + (f", 월 최대 {PRODUCTS[n][1]}만 원" if PRODUCTS[n][1] else "") + f": {PRODUCTS[n][2]})"
            for n in CANDIDATES[gtype]),
    ]
    lines += list(extra_lines)
    return "\n".join(lines)


def signature(facts):
    return hashlib.md5(facts.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------
# 2. AI 포트폴리오
# ---------------------------------------------------------------
PROMPT = """너는 '{name}'라는 이름의 귀여운 {animal} 모습을 한 AI 재무설계사야. 친구처럼 짧고 따뜻한 반말로 말해.
사용자의 장기 목표 하나를 위해, 매달 넣을 돈을 어떤 제도·상품 유형에 얼마씩 나눌지 포트폴리오를 짜줘.

반드시 지킬 것:
- 상품은 '[고를 수 있는 제도·상품 유형]'에 있는 이름만 그대로 써. 특정 금융사·특정 종목 이름은 절대 쓰지 마.
- 금액(amount)은 만 원 단위 정수이고, 모두 더하면 '[매달 넣을 돈]'과 정확히 같아야 해.
- 투자 종류 상품의 합은 '투자' 금액에 가깝게 맞춰. 상품마다 월 최대 금액과 나이 조건을 지켜.
- 2~4개 상품으로 나눠. 숫자는 사실 목록과 제도 자료에 있는 것만 써.
- 노후 준비는 세액공제를 받는 연금 계좌(연금저축펀드·IRP)를 먼저 채워(합쳐서 연 900만 원 한도). 연금 계좌 안에서도 예금·펀드를 고를 수 있으니 안정형이어도 연금 계좌가 유리해.
- 제도 조건은 [제도 자료]에 있는 것만 말하고, 바뀔 수 있는 건 '공식 안내 확인'이라고 해.

답은 아래 형식의 JSON 객체 하나로만 해.
{{
  "summary": "이 포트폴리오를 한 줄로 (40자 안팎)",
  "items": [
    {{"name": "상품 유형 이름", "amount": 10, "why": "내 상황과 연결한 이유", "how": "어떻게 시작하면 되는지", "caution": "주의할 점"}}
  ],
  "tip": "이 목표를 위한 한마디 조언"
}}"""


def parse(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return None
    items = []
    for it in data["items"]:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        try:
            amount = int(round(float(it.get("amount", 0))))
        except (TypeError, ValueError):
            amount = 0
        items.append({"name": str(it["name"]).strip(), "amount": amount, "why": str(it.get("why", "")),
                      "how": str(it.get("how", "")), "caution": str(it.get("caution", ""))})
    if not items:
        return None
    return {"summary": str(data.get("summary", "")), "items": items[:5], "tip": str(data.get("tip", ""))}


def ai_portfolio(gtype, facts, name, animal):
    topic = pl.GOAL_TYPES[gtype][1]
    try:
        text = llm.complete(PROMPT.format(name=name, animal=animal),
                            [{"role": "user", "content": f"{kn.topic_text(topic)}\n\n[사실 목록]\n{facts}"}],
                            max_tokens=6000, json_mode=True)
    except llm.LLMError as e:
        return None, str(e)
    data = parse(text)
    return (data, None) if data else (None, "AI 답을 읽지 못했어요")


# ---------------------------------------------------------------
# 3. 기본 모드 포트폴리오 (규칙)
# ---------------------------------------------------------------
def _concept(name):
    """상품 이름과 이어지는 제도 설명 (knowledge.py)"""
    alias = {"IRP": "IRP (개인형 퇴직연금)", "ISA 계좌 안 분산 ETF": "ISA (개인종합자산관리계좌)",
             "적립식 분산 펀드·ETF": "적립식·분산 투자", "파킹통장": "비상금·파킹통장"}
    return kn.concept_by_name(alias.get(name, name))


def rule_portfolio(gtype, base, invest_ratio, months, age):
    invest = round(base * invest_ratio)
    safe = base - invest
    youth = YOUTH_AGE[0] <= age <= YOUTH_AGE[1]
    picks = []

    def put(name, amount):
        if amount > 0:
            picks.append((name, amount))

    if gtype == "노후 준비":                       # 세액공제 계좌부터 채우기
        pension_a = min(base, PRODUCTS["연금저축펀드"][1])
        irp = min(base - pension_a, PRODUCTS["IRP"][1] - pension_a)
        put("연금저축펀드", pension_a)
        put("IRP", irp)
        put("ISA 계좌 안 분산 ETF", base - pension_a - irp)
    else:
        rest = safe
        if gtype == "내 집 마련":
            a = min(rest, PRODUCTS["주택청약종합저축"][1])
            put("주택청약종합저축", a)
            rest -= a
        if youth and months and months >= 36:
            a = min(rest, PRODUCTS["청년미래적금"][1])
            put("청년미래적금", a)
            rest -= a
        put("파킹통장" if months and months <= 12 else "자유적금·정기적금", rest)
        put("ISA 계좌 안 분산 ETF", invest)

    items = []
    for name, amount in picks:
        c = _concept(name)
        items.append({"name": name, "amount": amount,
                      "why": c["one_line"] if c else PRODUCTS[name][2],
                      "how": f"매달 {amount}만 원씩 자동이체로 넣기",
                      "caution": c["caution"] if c else "가입 전에 조건을 꼭 확인해줘."})
    summary = f"매달 {base}만 원을 {len(items)}곳에 나눠 담는 포트폴리오야."
    tip = ("세액공제 한도(연 900만 원) 안에서 연금 계좌를 먼저 채우면 세금을 돌려받아." if gtype == "노후 준비"
           else "기한이 가까워질수록 투자 비중을 줄여서 모은 돈을 지키자.")
    return {"summary": summary, "items": items, "tip": tip}


# ---------------------------------------------------------------
# 4. 검사 — AI가 짠 포트폴리오가 규칙을 지켰는지 (앱이 확인)
# ---------------------------------------------------------------
def check(data, gtype, base, invest_ratio, age):
    """규칙을 어긴 상품은 빼고, 지켜야 할 기준을 못 맞춘 건 경고로 돌려준다."""
    warnings = []
    allowed = set(CANDIDATES[gtype])
    kept = []
    for it in data["items"]:
        if it["name"] not in allowed:
            warnings.append(f"후보에 없는 상품 '{it['name']}'은(는) 뺐어요.")
            continue
        limit = PRODUCTS[it["name"]][1]
        if limit and it["amount"] > limit:
            warnings.append(f"{it['name']}: 월 {it['amount']}만 원은 기준(월 {limit}만 원)을 넘어요.")
        if it["name"] == "청년미래적금" and not (YOUTH_AGE[0] <= age <= YOUTH_AGE[1]):
            warnings.append(f"청년미래적금은 만 {YOUTH_AGE[0]}~{YOUTH_AGE[1]}세만 가입할 수 있어요.")
        kept.append(it)
    data["items"] = kept
    total = sum(it["amount"] for it in kept)
    if abs(total - base) > 1:
        warnings.append(f"금액 합계({total}만 원)가 매달 넣을 돈({base}만 원)과 달라요.")
    if gtype != "노후 준비" and base:
        invest = sum(it["amount"] for it in kept if PRODUCTS[it["name"]][0] == "투자")
        target = round(base * invest_ratio)
        if abs(invest - target) > max(2, base * 0.15):
            warnings.append(f"투자 비중({invest}만 원)이 성향·기간 기준({target}만 원)과 많이 달라요.")
    pension = sum(it["amount"] for it in kept if PRODUCTS[it["name"]][0] == "연금")
    room = min(base, pl.PENSION_TAX_LIMIT / 12)          # 세액공제를 받을 수 있는 한 달 금액
    if gtype == "노후 준비" and pension < room * 0.5:
        warnings.append(f"노후 자금인데 연금 계좌(연금저축·IRP)가 월 {pension}만 원뿐이에요. "
                        "세액공제를 받는 연금 계좌를 먼저 채우는 게 유리해요.")
    if pension * 12 > pl.PENSION_TAX_LIMIT:
        warnings.append(f"연금 계좌 합계가 세액공제 한도(연 {pl.PENSION_TAX_LIMIT}만 원)를 넘어요. 넘는 돈은 공제를 못 받아.")
    return warnings


def verify_text(data, facts, gtype):
    """설명 글 속 숫자(2자리 이상)가 사실 목록·제도 자료에 있는지"""
    text = " ".join([data["summary"], data["tip"]] + [it["why"] + " " + it["how"] + " " + it["caution"]
                                                      for it in data["items"]])
    used = {n for n in adv._numbers(text) if len(n.split(".")[0]) >= 2}
    known = adv._numbers(facts + "\n" + kn.all_text())
    return len(used), sorted(n for n in used if n not in known)


def make_portfolio(gtype, base, invest_ratio, months, age, facts, name="머니", animal="곰"):
    note, data, mode = None, None, "기본"
    if llm.api_available():
        data, note = ai_portfolio(gtype, facts, name, animal)
        mode = "AI" if data else "기본"
    if data is None:
        data = rule_portfolio(gtype, base, invest_ratio, months, age)
    warnings = check(data, gtype, base, invest_ratio, age)
    checked, unknown = verify_text(data, facts, gtype)
    return {"mode": mode, "note": note, "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "signature": signature(facts), "base": base, "data": data, "warnings": warnings,
            "checked": checked, "unknown": unknown}
