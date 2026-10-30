"""
advisor.py — 동물 친구(기본 이름 '머니')의 AI 맞춤 조언 (이 앱의 핵심 AI 기능)

역할 나누기
- 숫자 계산(월급 배분, 목표, 평생 로드맵)은 planner.py가 공식으로 정확하게 계산해요.
- AI(Gemini 또는 Claude)는 그 숫자들을 '사실 목록'으로 받아서, 사람처럼 상황을 진단하고 조언을 써요.
- AI가 숫자를 지어내지 않았는지 verify_numbers()로 자동 확인해요. (환각 방지)

흐름: build_facts(상황 정리) → ai_advice(AI가 조언 작성) → verify_numbers(숫자 검증)
API 키가 없으면 rule_advice()가 미리 써둔 문장으로 같은 형식의 조언을 만들어요.
"""
import datetime
import hashlib
import json
import re

import character as ch
import llm
import planner as pl

TOPICS = {
    "이번 달 종합 점검": "이번 달 돈 관리 전체(배분, 목표 진행, 소비)를 골고루 점검해줘.",
    "소비 습관 고치기": "최근 소비 내역에서 늘어난 곳과 줄일 수 있는 곳을 중심으로, 목표가 얼마나 빨라지는지 연결해서 조언해줘.",
    "평생 계획·노후": "평생 로드맵(결혼·내 집·자녀·은퇴)과 노후 준비를 중심으로, 지금 나이에 할 일을 조언해줘.",
}

SYSTEM_PROMPT = """너는 '{name}'라는 이름의 귀여운 {animal} 모습을 한 AI 재무설계사야. 사용자의 오랜 친구처럼 짧고 따뜻한 반말로 말해.
사용자의 재무 상황은 앱이 이미 정확하게 계산해서 '사실 목록'으로 줄 거야.

반드시 지킬 것:
- 숫자는 사실 목록에 있는 숫자만 그대로 써. 새로 더하거나 빼서 새 숫자를 만들지 마.
- 특정 주식 종목이나 특정 금융사 상품 이름을 말하지 마. 상품 유형(파킹통장, 적금, 분산 펀드·ETF 등)까지만.
- 수익률은 가정값이라는 걸 잊지 마.
- 혼내지 말고 칭찬과 작은 실천 위주로. 부족한 점은 '이렇게 하면 돼'로 바꿔 말해.
- '지난번 조언' 정보가 있으면, 그걸 기억하고 있다는 걸 자연스럽게 언급해.

답은 아래 형식의 JSON 객체 하나로만 해. 설명 문장이나 코드 블록 표시는 쓰지 마.
{{
  "summary": "지금 상황 한 줄 진단 (40자 안팎)",
  "good": ["잘하고 있는 점 1", "잘하고 있는 점 2"],
  "actions": [
    {{"title": "이번 달 실천 1 (짧게)", "detail": "왜 필요한지, 하면 무엇이 좋아지는지 (사실 목록의 숫자 근거 포함)"}},
    {{"title": "이번 달 실천 2", "detail": "..."}},
    {{"title": "이번 달 실천 3", "detail": "..."}}
  ],
  "future": "평생 관점에서 한마디 (로드맵·노후와 연결)",
  "cheer": "응원 한마디"
}}"""


# ---------------------------------------------------------------
# 1. 상황 정리 — AI에게 줄 '사실 목록' (숫자는 모두 앱이 계산한 값)
# ---------------------------------------------------------------
def build_facts(profile, plan, life, done_goals, summary, checks, need, tx, promises, held_count,
                prev_advice=None, holdings=None):
    age = int(profile.current_age)
    rate = plan.total_saving / profile.income * 100 if profile.income else 0
    lines = [
        f"[기본] {profile.name}, {age}세, {profile.job}, 투자 성향 {profile.risk}",
        f"[한 달 돈] 세후 월급 {ch.fmt(profile.income)}, 고정비 {ch.fmt(profile.fixed)}, "
        f"생활비 계획 {ch.fmt(profile.spending)}, 저축 가능액 {ch.fmt(max(plan.surplus, 0))} "
        f"(월급의 {rate:.0f}%)",
        f"[비상금] 지금 {ch.fmt(profile.emergency_saved)}, 목표(3개월치) {ch.fmt(plan.emergency_target)}, "
        f"이번 달 비상금 배분 {ch.fmt(plan.emergency)}",
    ]
    if holdings:   # 내 포트폴리오: 지금 가입한 상품
        total = sum(float(h["금액"]) for h in holdings)
        groups = pl.holdings_by_group(holdings)
        lines.append("[내 포트폴리오] 총 " + ch.fmt(total) + " — " + ", ".join(
            f"{h['상품']} {ch.fmt(float(h['금액']))}({h['용도']})" for h in holdings))
        lines.append("[포트폴리오 비중] " + ", ".join(f"{g} {round(v / total * 100)}%" for g, v in groups.items())
                     + f" / {profile.risk} 기준 투자 비중 {round(pl.RISK_MIX[profile.risk][1] * 100)}% 안팎")
    for it in plan.items:
        g = it.goal
        when = ch.years_months(it.expected_months) if it.expected_months is not None else "지금 배분으로는 어려움"
        lines.append(
            f"[목표] {g.name}({it.kind}): 모은 돈 {ch.fmt(g.saved)} / 목표 {ch.fmt(g.target)}, "
            f"남은 금액 {ch.fmt(g.target - g.saved)}, 기한 {ch.years_months(g.months)}, "
            f"이번 달 배분 {ch.fmt(it.alloc)} (필요 {ch.fmt(it.need)}), 예상 달성 {when}, "
            f"{'기한 안에 가능' if it.on_track else '기한보다 늦음'}, "
            f"투자 비중 {round(it.invest_ratio * 100)}%"
            + (f", 집값 {ch.fmt(it.price)} 중 대출 빼고 모을 자기자금 기준" if it.price else ""))
    if done_goals:
        lines.append("[이룬 목표] " + ", ".join(g.name for g in done_goals))
    lines.append(f"[노후 자금] 이번 달 배분 {ch.fmt(plan.extra)}, 은퇴 전까지 매달 필요 {ch.fmt(need['monthly'])}, "
                 f"은퇴 {life.retire_age}세, 은퇴 후 생활비 월 {ch.fmt(life.retire_spending)}, "
                 f"국민연금 월 {ch.fmt(life.pension)}")
    pp = pl.pension_plan(profile, life)
    lines.append(f"[연금 3층] 국민연금 월 {ch.fmt(life.pension)}, 퇴직연금({pp['retire_type'] or '없음'}) 월 "
                 f"{ch.fmt(pp['retire_monthly'])}, 개인연금(IRP·연금저축) 매달 {ch.fmt(life.private_monthly)} 납입 → "
                 f"월 {ch.fmt(pp['private_monthly_out'])} 수령, 세액공제로 해마다 {ch.fmt(pp['tax_refund'])} 돌려받음")
    if summary["broke_age"] is None:
        lines.append(f"[평생 로드맵] 90세까지 돈이 버팀, 90세 예상 금융자산 {ch.fmt(summary['final'])}, "
                     f"순자산(집 포함) {ch.fmt(summary['final_net'])}")
    else:
        lines.append(f"[평생 로드맵] {summary['broke_age']}세쯤 현금(금융자산)이 모자라기 시작함, "
                     f"90세 순자산(집 포함) {ch.fmt(summary['final_net'])}")
    for c in checks:
        status = "가능" if c["ok"] else f"부족 {ch.fmt(c['cost'] - max(c['before'], 0))}"
        lines.append(f"[인생 이벤트] {c['age']}세 {c['name']} 필요한 현금 {ch.fmt(c['cost'])}: {status}")
        if c.get("loan"):
            lines.append(f"  - 대출: 집값 {ch.fmt(c['price'])} 중 {ch.fmt(c['loan'])} 대출, 매달 {ch.fmt(c['pay'])} 상환, "
                         f"{c['payoff_age']}세에 다 갚음, 총 이자 {ch.fmt(c['interest'])} (가정 금리 연 "
                         f"{life.loan_rate * 100:.1f}%), 그때 세후 월급의 {round(c['pay_ratio'] * 100)}%")

    # 소비: 최근 두 달 카테고리별 비교 (원 → 만 원)
    months = list(tx)
    if months:
        this = tx[months[-1]]
        last = tx[months[-2]] if len(months) >= 2 else {}
        total = round(sum(this.values()) / 10000)
        lines.append(f"[소비 {months[-1]}] 총 {ch.fmt(total)} (생활비 계획 {ch.fmt(profile.spending)})")
        for cat in sorted(this, key=lambda c: -this[c]):
            now = round(this[cat] / 10000)
            if last:
                diff = now - round(last.get(cat, 0) / 10000)
                lines.append(f"  - {cat} {ch.fmt(now)} (지난달 대비 {diff:+}만 원)")
            else:
                lines.append(f"  - {cat} {ch.fmt(now)}")
    if promises:
        lines.append("[지난달 약속] " + ", ".join(f"{k} {ch.fmt(v)} 이하" for k, v in promises.items()))
    if held_count:
        lines.append(f"[참은 소비] '이거 사도 돼?'에서 {held_count}번 참음")
    if prev_advice:
        acts = prev_advice.get("data", {}).get("actions", [])
        done_flags = prev_advice.get("done", [])
        parts = [f"{a.get('title', '')}({'실천함' if i < len(done_flags) and done_flags[i] else '아직'})"
                 for i, a in enumerate(acts)]
        if parts:
            lines.append(f"[지난번 조언 {prev_advice.get('created', '')[:10]}] " + ", ".join(parts))
    return "\n".join(lines)


def signature(facts: str) -> str:
    """상황이 바뀌었는지 확인하는 지문 (지난번 조언 줄은 제외)"""
    core = "\n".join(ln for ln in facts.splitlines() if not ln.startswith("[지난번 조언"))
    return hashlib.md5(core.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------
# 2. AI 조언
# ---------------------------------------------------------------
def ai_advice(facts: str, topic: str, name="머니", animal="곰"):
    """AI에게 사실 목록과 주제를 주고 조언(JSON)을 받는다. 실패하면 (None, 오류 설명)."""
    try:
        text = llm.complete(SYSTEM_PROMPT.format(name=name, animal=animal),
                            [{"role": "user", "content": f"주제: {topic} — {TOPICS.get(topic, '')}\n\n사실 목록:\n{facts}"}],
                            max_tokens=8000, json_mode=True)
    except llm.LLMError as e:   # 네트워크·키 오류가 나도 앱은 멈추지 않게
        return None, str(e)
    data = parse_advice(text)
    if data is None:
        return None, "AI 답을 읽지 못했어요"
    return data, None


def parse_advice(text: str):
    """AI 답에서 JSON을 찾아 필요한 칸이 다 있는지 확인한다. 이상하면 None."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("summary"):
        return None
    actions = [a for a in data.get("actions", []) if isinstance(a, dict) and a.get("title")]
    return {
        "summary": str(data["summary"]),
        "good": [str(x) for x in data.get("good", []) if x][:3],
        "actions": [{"title": str(a["title"]), "detail": str(a.get("detail", ""))} for a in actions][:3],
        "future": str(data.get("future", "")),
        "cheer": str(data.get("cheer", "")),
    }


# ---------------------------------------------------------------
# 3. 숫자 검증 — AI가 쓴 숫자가 앱이 계산한 숫자 안에 있는지
# ---------------------------------------------------------------
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str):
    return {n.replace(",", "") for n in NUM_RE.findall(text)}


def verify_numbers(advice: dict, facts: str):
    """
    조언 속 숫자(2자리 이상)가 사실 목록에 있는지 확인한다.
    돌려주는 값: (확인한 숫자 개수, 사실 목록에 없는 숫자 목록)
    """
    text = " ".join([advice["summary"], advice["future"], advice["cheer"], *advice["good"],
                     *[a["title"] + " " + a["detail"] for a in advice["actions"]]])
    used = {n for n in _numbers(text) if len(n.split(".")[0]) >= 2}   # 한 자리 숫자(3가지, 2번 등)는 제외
    known = _numbers(facts)
    unknown = sorted(n for n in used if n not in known)
    return len(used), unknown


# ---------------------------------------------------------------
# 4. 기본 모드 조언 (API 키가 없을 때) — 미리 써둔 문장 조합
# ---------------------------------------------------------------
def rule_advice(profile, plan, life, summary, checks, tx, topic):
    items = plan.items
    behind = [it for it in items if not it.on_track]
    rate = plan.total_saving / profile.income * 100 if profile.income else 0

    if plan.surplus <= 0:
        summary_line = "지금은 쓰는 돈이 버는 돈보다 많아. 생활비부터 같이 잡아보자."
    elif behind:
        summary_line = f"{ch.josa(behind[0].goal.name, '이가')} 기한보다 늦어지고 있어. 배분을 조금 손보자."
    else:
        summary_line = "목표들이 전부 계획대로 가고 있어. 아주 잘하고 있어!"

    good = []
    if rate >= 20:
        good.append(f"월급의 {rate:.0f}%를 저축하고 있어. 권장 수준보다 많이 모으는 중이야.")
    if profile.emergency_saved >= plan.emergency_target:
        good.append("비상금 3개월치를 이미 모아뒀어. 갑자기 돈 쓸 일이 생겨도 든든해.")
    on_track = [it.goal.name for it in items if it.on_track]
    if on_track:
        good.append(f"{', '.join(on_track[:2])} 목표는 기한 안에 이룰 수 있어.")
    if not good:
        good.append("재무 계획을 세웠다는 것 자체가 큰 시작이야.")

    actions = []
    months = list(tx)
    if months:
        this = tx[months[-1]]
        last = tx[months[-2]] if len(months) >= 2 else {}
        ups = sorted(((c, round(this[c] / 10000) - round(last.get(c, 0) / 10000)) for c in this),
                     key=lambda x: -x[1])
        if ups and ups[0][1] > 0:
            cat, diff = ups[0]
            actions.append({"title": f"{cat} 지출 줄이기",
                            "detail": f"{ch.josa(cat, '이가')} 지난달보다 {diff}만 원 늘었어. 이번 달은 지난달 수준으로 돌려보자."})
    for it in behind[:1]:
        actions.append({"title": f"{it.goal.name} 기한 다시 보기",
                        "detail": f"매달 {ch.fmt(it.need)}이 필요한데 지금은 {ch.fmt(it.alloc)}이야. "
                                  f"기한을 늘리거나 다른 목표가 끝난 뒤 돈을 몰아주자."})
    if plan.emergency > 0:
        actions.append({"title": "비상금 먼저 채우기",
                        "detail": f"이번 달 {ch.fmt(plan.emergency)}을 파킹통장에 넣어두자."})
    if plan.extra > 0:
        actions.append({"title": "노후 자금 자동이체",
                        "detail": f"남는 {ch.fmt(plan.extra)}은 월급날 바로 노후 자금으로 옮기자."})
    actions.append({"title": "소비 습관 리포트 확인하기",
                    "detail": "언제 돈을 많이 쓰는지 알면 줄일 곳이 바로 보여."})

    if topic == "평생 계획·노후":   # 주제가 평생 계획이면 노후·인생 이벤트 실천을 앞으로
        late = [c for c in checks if not c["ok"]]
        front = [{"title": f"{c['name']} 시기 다시 보기",
                  "detail": f"{c['age']}세에 {ch.fmt(c['cost'] - max(c['before'], 0))} 정도 모자라. "
                            f"평생 플랜의 목표 페이지에서 기한을 1~2년 늘려보자."} for c in late[:1]]
        front.append({"title": "노후 자금 따로 모으기",
                      "detail": f"은퇴 {life.retire_age}세까지 노후 자금을 매달 조금씩 쌓아두면 이자가 이자를 낳아."})
        actions = front + actions

    msgs = ch.roadmap_messages(summary, checks, life.retire_age)
    label, stage_tip = ch.life_stage(profile.current_age)
    return {
        "summary": summary_line,
        "good": good[:2],
        "actions": actions[:3],
        "future": msgs[0] if msgs else stage_tip,
        "cheer": f"{label} 시기야. {stage_tip}",
    }


# ---------------------------------------------------------------
# 5. 바깥에서 쓰는 함수
# ---------------------------------------------------------------
def make_advice(facts, topic, rule_inputs, name="머니", animal="곰"):
    """
    조언을 만든다. API 키가 있으면 AI, 없거나 실패하면 기본 모드.
    rule_inputs: rule_advice에 넘길 (profile, plan, life, summary, checks, tx)
    """
    note = None
    data, mode = None, "기본"
    if llm.api_available():
        data, note = ai_advice(facts, topic, name, animal)
        mode = "AI" if data else "기본"
    if data is None:
        data = rule_advice(*rule_inputs, topic)
    checked, unknown = verify_numbers(data, facts)
    return {
        "topic": topic,
        "mode": mode,
        "note": note,
        "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "signature": signature(facts),
        "data": data,
        "checked": checked,
        "unknown": unknown,
        "done": [False] * len(data["actions"]),
    }
