"""
habits.py — 소비 습관 리포트 (카드 내역의 '날짜·시간'으로 언제 돈을 쓰는지 분석)

역할 나누기 (AI 맞춤 조언과 같은 방식)
1. analyze(): 앱이 요일별·시간대별 지출, 밤 지출 비중, 주말 지출, 소액 결제를 정확하게 계산해요.
2. savings_candidates(): 줄일 수 있는 습관 후보와 '아끼면 목표가 며칠 빨라지는지'를 앱이 계산해요.
3. ai_report(): AI(Gemini 또는 Claude)가 그 숫자를 읽고 눈에 띄는 패턴을 골라, 소비 유형 별명과 함께 설명해요.
4. verify(): AI가 쓴 숫자가 앱 계산값 안에 있는지 확인해요. (환각 방지)
API 키가 없으면 rule_report()가 후보 중 아끼는 금액이 큰 순서로 골라 같은 형식의 리포트를 만들어요.
"""
import csv
import datetime
import hashlib
import json

import advisor as adv
import character as ch
import llm
import planner as pl

DAYS = ["월", "화", "수", "목", "금", "토", "일"]
# 시간대 (시작 시각 이상 ~ 끝 시각 미만)
SLOTS = [("아침", 6, 11), ("점심", 11, 14), ("오후", 14, 18), ("저녁", 18, 21), ("밤", 21, 24), ("새벽", 0, 6)]
LATE_LABEL = "밤 9시~새벽 6시"
SMALL_LIMIT = 10000          # 소액 결제 기준: 1만 원 미만 (원)
MIN_TIMED = 10               # 시간 정보가 있는 결제가 이보다 적으면 분석하지 않음


def slot_of(hour):
    for name, start, end in SLOTS:
        if start <= hour < end:
            return name
    return "새벽"


def is_late(hour):
    return hour >= 21 or hour < 6


# ---------------------------------------------------------------
# 1. 읽기 + 통계 계산
# ---------------------------------------------------------------
def load_rows(path):
    """CSV(날짜,카테고리,내용,금액,시간)를 읽어 분석용 줄 목록으로. 시간이 없거나 이상한 줄은 hour=None."""
    with open(path, encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    rows = []
    for r in raw:
        try:
            day = datetime.date.fromisoformat(r["날짜"].strip())
            amount = int(str(r["금액"]).replace(",", ""))
        except (ValueError, KeyError, AttributeError):
            continue
        hour = None
        t = (r.get("시간") or "").strip()
        if ":" in t:
            try:
                hour = int(t.split(":")[0]) % 24
            except ValueError:
                hour = None
        rows.append({"date": day, "hour": hour, "cat": (r.get("카테고리") or "기타").strip(),
                     "what": (r.get("내용") or "").strip(), "amount": amount})
    return rows


def manwon(won):
    return round(won / 10000)


def analyze(rows):
    """
    요일·시간대별 소비 통계를 계산한다. 금액은 만 원(반올림), 비율은 %.
    시간 정보가 있는 결제가 너무 적으면 None.
    """
    timed = [r for r in rows if r["hour"] is not None]
    if len(timed) < MIN_TIMED:
        return None
    months = sorted({r["date"].strftime("%Y-%m") for r in rows})
    n_months = len(months)
    total = sum(r["amount"] for r in timed)

    # 요일 × 시간대 표 (그래프용)
    grid = {}
    for r in timed:
        key = (DAYS[r["date"].weekday()], slot_of(r["hour"]))
        grid[key] = grid.get(key, 0) + r["amount"]

    by_slot = {}
    for name, _, _ in SLOTS:
        items = [r for r in timed if slot_of(r["hour"]) == name]
        by_slot[name] = {"count": len(items), "amount": manwon(sum(r["amount"] for r in items))}
    by_day = {d: manwon(sum(r["amount"] for r in timed if DAYS[r["date"].weekday()] == d)) for d in DAYS}

    late = [r for r in timed if is_late(r["hour"])]
    late_amount = sum(r["amount"] for r in late)

    # 카테고리별 밤 비중 (결제 3건 이상인 카테고리만)
    cat_late = []
    for cat in sorted({r["cat"] for r in timed}):
        items = [r for r in timed if r["cat"] == cat]
        if len(items) < 3:
            continue
        night = [r for r in items if is_late(r["hour"])]
        cat_late.append({"cat": cat, "count": len(items), "late_count": len(night),
                         "share": round(len(night) / len(items) * 100),
                         "late_monthly": manwon(sum(r["amount"] for r in night) / n_months),
                         "monthly": manwon(sum(r["amount"] for r in items) / n_months)})
    cat_late.sort(key=lambda c: -c["late_monthly"])

    # 주말(금 밤 포함 X, 토·일) vs 평일: 하루 평균
    first, last = min(r["date"] for r in rows), max(r["date"] for r in rows)
    span = [first + datetime.timedelta(days=i) for i in range((last - first).days + 1)]
    weekend_days = sum(1 for d in span if d.weekday() >= 5) or 1
    weekday_days = sum(1 for d in span if d.weekday() < 5) or 1
    weekend_amount = sum(r["amount"] for r in timed if r["date"].weekday() >= 5)
    weekday_amount = total - weekend_amount

    small = [r for r in timed if r["amount"] < SMALL_LIMIT]

    peak_day = max(by_day, key=by_day.get)
    peak_slot = max(by_slot, key=lambda s: by_slot[s]["amount"])
    return {
        "first": first.isoformat(), "last": last.isoformat(), "months": n_months,
        "count": len(rows), "timed": len(timed), "total": manwon(total),
        "monthly_total": manwon(total / n_months),
        "grid": grid, "by_slot": by_slot, "by_day": by_day,
        "peak_day": peak_day, "peak_slot": peak_slot,
        "late_count": len(late), "late_share": round(late_amount / total * 100) if total else 0,
        "late_monthly": manwon(late_amount / n_months),
        "cat_late": cat_late,
        "weekend_daily": round(weekend_amount / weekend_days / 10000, 1),
        "weekday_daily": round(weekday_amount / weekday_days / 10000, 1),
        "weekend_monthly": manwon(weekend_amount / n_months),
        "small_count_monthly": round(len(small) / n_months),
        "small_monthly": manwon(sum(r["amount"] for r in small) / n_months),
    }


# ---------------------------------------------------------------
# 2. 줄일 수 있는 습관 후보 + 목표가 며칠 빨라지는지 (앱이 계산)
# ---------------------------------------------------------------
def days_faster(save, goal_items, risk):
    """
    매달 save(만 원)만큼 목표에 더 넣으면 며칠 빨리 이루는지.
    기한이 가까운 목표부터 보면서, 실제로 빨라지는 첫 목표를 (목표 이름, 일수)로 돌려준다. 없으면 (None, None).
    (예: 코트는 이미 다음 달에 이루면 빨라질 게 없으니 다음 목표인 해외여행으로 계산)
    """
    for it in goal_items or []:
        before = pl.months_with_plan(it.goal, it.alloc, risk)
        after = pl.months_with_plan(it.goal, it.alloc + save, risk)
        if before is None or after is None:
            continue
        days = round((before - after) * 30)
        if days >= 1:
            return it.goal.name, days
    return None, None


def savings_candidates(stats, goal_items, risk):
    """
    goal_items: 이번 달 계획의 목표들 (plan.items, 기한이 가까운 순)
    습관 후보 목록. 각 후보: key, title, fact(근거), save(월 절약 만 원), goal·days(어느 목표가 며칠 빨라지는지),
    category(약속 걸 카테고리), limit(약속 한도 만 원)
    """
    cands = []

    def add(key, title, fact, save, category=None, limit=None):
        if save < 1:
            return
        goal, days = days_faster(save, goal_items, risk)
        cands.append({"key": key, "title": title, "fact": fact, "save": save,
                      "goal": goal, "days": days, "category": category, "limit": limit})

    # 밤에 많이 쓰는 카테고리 (밤 비중 50% 이상)
    for c in stats["cat_late"]:
        if c["share"] >= 50 and c["late_monthly"] >= 2:
            save = round(c["late_monthly"] / 2)
            add(f"late_{c['cat']}", f"밤 {c['cat']} 절반 줄이기",
                f"{c['cat']} 결제 {c['count']}건 중 {c['late_count']}건({c['share']}%)이 {LATE_LABEL}, "
                f"밤 {c['cat']} 월평균 {c['late_monthly']}만 원",
                save, c["cat"], max(c["monthly"] - save, 0))
    # 밤 지출 전체
    if stats["late_share"] >= 25:
        add("late_all", "밤 결제 줄이기",
            f"전체 지출의 {stats['late_share']}%가 {LATE_LABEL}, 월평균 {stats['late_monthly']}만 원",
            round(stats["late_monthly"] * 0.3))
    # 주말 과소비 (주말 하루 평균이 평일의 1.3배 이상)
    if stats["weekday_daily"] and stats["weekend_daily"] >= stats["weekday_daily"] * 1.3:
        add("weekend", "주말 예산 정하기",
            f"주말 하루 평균 {stats['weekend_daily']}만 원, 평일 하루 평균 {stats['weekday_daily']}만 원",
            round(stats["weekend_monthly"] * 0.2))
    # 자잘한 결제
    if stats["small_count_monthly"] >= 6:
        add("small", "자잘한 결제 모으기",
            f"1만 원 미만 결제가 한 달 평균 {stats['small_count_monthly']}번, 월 {stats['small_monthly']}만 원",
            round(stats["small_monthly"] * 0.3))
    cands.sort(key=lambda c: -c["save"])
    return cands


def build_facts(stats, cands):
    """AI에게 줄 '사실 목록' — 숫자는 모두 앱이 계산한 값"""
    lines = [f"[분석 기간] {stats['first']} ~ {stats['last']} ({stats['months']}개월), "
             f"결제 {stats['count']}건 중 시간 있는 결제 {stats['timed']}건, 월평균 지출 {stats['monthly_total']}만 원"]
    lines.append("[시간대별 지출] " + ", ".join(
        f"{name}({s}~{e}시) {stats['by_slot'][name]['count']}건 {stats['by_slot'][name]['amount']}만 원"
        for name, s, e in SLOTS))
    lines.append("[요일별 지출] " + ", ".join(f"{d} {stats['by_day'][d]}만 원" for d in DAYS)
                 + f" — 가장 많이 쓴 요일 {stats['peak_day']}요일, 가장 많이 쓴 시간대 {stats['peak_slot']}")
    lines.append(f"[{LATE_LABEL}] {stats['late_count']}건, 전체 지출의 {stats['late_share']}%, "
                 f"월평균 {stats['late_monthly']}만 원")
    if stats["cat_late"]:
        lines.append("[카테고리별 밤 결제 비중] " + ", ".join(
            f"{c['cat']} {c['late_count']}/{c['count']}건({c['share']}%) 월 {c['monthly']}만 원"
            for c in stats["cat_late"]))
    lines.append(f"[주말 vs 평일] 주말 하루 평균 {stats['weekend_daily']}만 원, 평일 하루 평균 {stats['weekday_daily']}만 원")
    lines.append(f"[소액 결제(1만 원 미만)] 한 달 평균 {stats['small_count_monthly']}번, 월 {stats['small_monthly']}만 원")
    for c in cands:
        speed = f" → {c['goal']} 약 {c['days']}일 빨리" if c["days"] else ""
        lines.append(f"[절약 후보 {c['key']}] {c['title']}: {c['fact']} / 실천하면 월 {c['save']}만 원 절약{speed}")
    return "\n".join(lines)


def signature(facts):
    return hashlib.md5(facts.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------
# 3. AI 리포트
# ---------------------------------------------------------------
PROMPT = """너는 '{name}'라는 이름의 귀여운 {animal} 모습을 한 AI 재무설계사야. 친구처럼 짧고 따뜻한 반말로 말해.
앱이 사용자의 카드 결제를 요일·시간대별로 계산한 '사실 목록'을 줄 거야. 언제, 어떤 상황에서 돈을 쓰는지 습관을 찾아줘.

반드시 지킬 것:
- 숫자는 사실 목록에 있는 숫자만 그대로 써. 새로 계산해서 새 숫자를 만들지 마.
- 패턴은 '[절약 후보 key]'에서 골라 key를 그대로 적어. 후보가 없으면 patterns는 빈 목록으로.
- 혼내지 말고, 사람이 왜 그 시간에 쓰게 되는지 공감하면서 쉽게 실천할 방법을 제안해.
- 특정 금융사 상품 이름은 말하지 마.

답은 아래 형식의 JSON 객체 하나로만 해. 설명 문장이나 코드 블록 표시는 쓰지 마.
{{
  "persona": "소비 유형 별명 (예: 금요일 밤 배달러, 10자 안팎, 귀엽게)",
  "headline": "이 사람 소비 습관 한 줄 요약 (40자 안팎)",
  "patterns": [
    {{"key": "절약 후보 key", "title": "패턴 이름 (짧게)", "insight": "언제·왜 이렇게 쓰는 것 같은지 (숫자 근거 포함)", "tip": "쉽게 해볼 실천 방법 하나"}}
  ],
  "challenge": "이번 주에 해볼 작은 챌린지 한 가지"
}}"""


def parse_report(text, cands):
    """AI 답에서 JSON을 찾아 확인한다. 후보에 없는 key의 패턴은 버린다. 이상하면 None."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("headline"):
        return None
    keys = {c["key"] for c in cands}
    patterns = [p for p in data.get("patterns", []) if isinstance(p, dict) and p.get("key") in keys]
    return {
        "persona": str(data.get("persona", "")),
        "headline": str(data["headline"]),
        "patterns": [{"key": p["key"], "title": str(p.get("title", "")), "insight": str(p.get("insight", "")),
                      "tip": str(p.get("tip", ""))} for p in patterns][:3],
        "challenge": str(data.get("challenge", "")),
    }


def ai_report(facts, cands, name="머니", animal="곰"):
    """AI에게 사실 목록을 주고 리포트(JSON)를 받는다. 실패하면 (None, 오류 설명)."""
    try:
        text = llm.complete(PROMPT.format(name=name, animal=animal),
                            [{"role": "user", "content": f"사실 목록:\n{facts}"}], max_tokens=6000, json_mode=True)
    except llm.LLMError as e:   # 네트워크·키 오류가 나도 앱은 멈추지 않게
        return None, str(e)
    data = parse_report(text, cands)
    if data is None:
        return None, "AI 답을 읽지 못했어요"
    return data, None


# ---------------------------------------------------------------
# 4. 기본 모드 리포트 (API 키가 없을 때) — 규칙으로 고르기
# ---------------------------------------------------------------
PERSONAS = {   # 가장 큰 후보에 따라 붙이는 별명
    "late_배달": "야식 배달러 🌙", "late_쇼핑": "새벽 장바구니러 🛒", "late_식비": "밤 편의점 탐험가 🏪",
    "late_all": "올빼미 소비러 🦉", "weekend": "주말 플렉서 🎉", "small": "티끌 결제러 🪙",
}
TIPS = {
    "late_배달": "밤 9시 이후엔 배달 앱을 폴더 안쪽으로 옮겨두자. 저녁을 조금 든든하게 먹는 것도 좋아.",
    "late_쇼핑": "밤에 담은 건 장바구니에만 두고, 다음 날 아침에 다시 보고 결제하자.",
    "late_식비": "편의점 가기 전에 집에 먹을 걸 하나 챙겨두면 밤 간식비가 줄어.",
    "late_all": "밤 9시 이후 결제는 '하루 자고 결정하기' 규칙을 만들어보자.",
    "weekend": "금요일에 주말 용돈을 정해두고 그 안에서만 써보자.",
    "small": "자잘한 결제는 일주일에 한 번 모아서 얼마인지 확인해보자.",
}


def rule_report(stats, cands):
    patterns = []
    for c in cands[:3]:
        patterns.append({"key": c["key"], "title": c["title"], "insight": c["fact"] + ".",
                         "tip": TIPS.get(c["key"], "한 주만 의식하면서 써보자.")})
    top = cands[0]["key"] if cands else None
    headline = (f"{stats['peak_day']}요일에 가장 많이 쓰고, 시간대로는 {ch.josa(stats['peak_slot'], '이가')} 1등이야. "
                f"지출의 {stats['late_share']}%가 밤 9시 이후에 나가.")
    challenge = ("이번 주는 " + cands[0]["title"] + "부터 해보자!") if cands else "이번 주도 지금처럼만 쓰자!"
    return {"persona": PERSONAS.get(top, "균형 잡힌 소비러 ⚖️"), "headline": headline,
            "patterns": patterns, "challenge": challenge}


# ---------------------------------------------------------------
# 5. 숫자 검증 + 합치기
# ---------------------------------------------------------------
def verify(report, facts):
    """리포트 속 숫자(2자리 이상)가 사실 목록에 있는지. (확인한 숫자 개수, 없는 숫자 목록)"""
    text = " ".join([report["persona"], report["headline"], report["challenge"],
                     *[p["title"] + " " + p["insight"] + " " + p["tip"] for p in report["patterns"]]])
    used = {n for n in adv._numbers(text) if len(n.split(".")[0]) >= 2}
    known = adv._numbers(facts)
    unknown = sorted(n for n in used if n not in known)
    return len(used), unknown


def make_report(stats, cands, facts, name="머니", animal="곰"):
    """리포트를 만든다. API 키가 있으면 AI, 없거나 실패하면 기본 모드."""
    note, data, mode = None, None, "기본"
    if llm.api_available():
        data, note = ai_report(facts, cands, name, animal)
        mode = "AI" if data else "기본"
    if data is None:
        data = rule_report(stats, cands)
    checked, unknown = verify(data, facts)
    return {"mode": mode, "note": note, "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "signature": signature(facts), "data": data, "checked": checked, "unknown": unknown}
