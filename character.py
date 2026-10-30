"""
character.py — 캐릭터 성장 단계와 '머니'의 말투
API 없이도 동작하도록 규칙 기반(템플릿)으로 메시지를 만듭니다.

- 내 동물 친구의 부자 단계: 총자산이 늘어날수록 부자 아이템이 생김 (WEALTH_LEVELS)
- 실천 배지: 약속을 지키거나 소비를 참거나 조언을 실천하면 쌓임 (POINTS)
"""

NAME = "머니"

# ---------------------------------------------------------------
# 1. 내 캐릭터의 부자 단계 (총자산 기준, 단위: 만 원)
# ---------------------------------------------------------------
WEALTH_LEVELS = [   # (필요 총자산, 단계 이름, 생기는 부자 아이템)
    (0, "알뜰 새내기", "아직 없음"),
    (1000, "저축 꿈나무", "반짝 동전"),
    (3000, "든든한 직장인", "돼지 저금통"),
    (7000, "재테크 고수", "돈주머니와 반짝이"),
    (15000, "자산가", "금목걸이"),
    (30000, "부자", "왕관과 금빛 배경"),
]


def wealth_of(assets: float):
    """총자산으로 현재 부자 단계와 다음 단계까지 남은 금액을 계산한다."""
    level = 0
    for i, (need, _, _) in enumerate(WEALTH_LEVELS):
        if assets >= need:
            level = i
    need, name, outfit = WEALTH_LEVELS[level]
    if level + 1 < len(WEALTH_LEVELS):
        next_need, next_name, _ = WEALTH_LEVELS[level + 1]
        progress = (assets - need) / (next_need - need)
        return {"level": level, "name": name, "outfit": outfit, "next_name": next_name,
                "next_need": next_need - assets, "progress": max(0.0, min(progress, 1.0))}
    return {"level": level, "name": name, "outfit": outfit, "next_name": None,
            "next_need": None, "progress": 1.0}


# ---------------------------------------------------------------
# 2. 실천 배지 규칙 — 벌보다 보상 중심으로 설계
#    배지는 홈 화면에 '🏅 실천 배지 N개'로 보여요.
# ---------------------------------------------------------------
POINTS = {
    "monthly_review_ok": 2,   # 한 달 생활비를 계획 안에서 썼을 때
    "promise_kept": 1,        # 지난달 약속을 지켰을 때 (약속 하나당)
    "held_back": 1,           # "이거 사도 돼?"에서 참기로 했을 때
    "short_goal_done": 3,     # 목표를 달성했을 때 (목표 하나당)
    "advice_done": 1,         # 머니의 조언 속 실천 항목을 해냈을 때 (항목 하나당)
}


# ---------------------------------------------------------------
# 3. 글자 도우미
# ---------------------------------------------------------------
def josa(word: str, pair: str) -> str:
    """
    받침에 맞는 조사를 붙인다.
    pair 예: "은는", "이가", "을를" (코트는, 배달이, 쇼핑을)
             "으로" (재킷으로, 셔츠로), "이야" (직장인이야, 꿈나무야)
    """
    last = word[-1] if word else ""
    final = (ord(last) - 0xAC00) % 28 if "가" <= last <= "힣" else 0   # 받침 번호 (0이면 받침 없음)
    if pair == "으로":   # ㄹ 받침(8번)은 '로'를 붙임: 서울로
        return word + ("으로" if final and final != 8 else "로")
    if pair == "이야":
        return word + ("이야" if final else "야")
    return word + (pair[0] if final else pair[1])


def fmt(manwon) -> str:
    """만 원 단위 숫자를 보기 좋게 (예: 12000 → 1억 2,000만 원, -500 → -500만 원)"""
    manwon = round(manwon)
    sign = "-" if manwon < 0 else ""
    manwon = abs(manwon)
    if manwon >= 10000:
        eok, rest = divmod(manwon, 10000)
        return sign + (f"{eok}억 {rest:,}만 원" if rest else f"{eok}억 원")
    return f"{sign}{manwon:,}만 원"


def years_months(months) -> str:
    if months is None:
        return "지금 계획으로는 어려워요"
    months = round(months)
    if months <= 0:
        return "바로"
    y, m = divmod(months, 12)
    if y and m:
        return f"{y}년 {m}개월"
    return f"{y}년" if y else f"{m}개월"


# ---------------------------------------------------------------
# 4. 인생 단계별 조언 (나이에 따라 머니가 해주는 말)
# ---------------------------------------------------------------
def life_stage(age: float):
    if age < 30:
        return "20대 · 기초 다지기", "비상금이랑 저축 습관부터 만들자. 지금 모으는 작은 돈이 제일 오래 불어나."
    if age < 40:
        return "30대 · 큰 목표 준비", "결혼이나 내 집 같은 큰 목표가 몰리는 시기야. 목표별로 통장을 나눠두자."
    if age < 50:
        return "40대 · 자산 키우기", "아이 교육비랑 노후 준비를 같이 챙길 때야. 노후 자금을 조금씩 늘려가자."
    if age < 60:
        return "50대 · 은퇴 준비", "은퇴가 가까워졌어. 투자 비중은 줄이고, 모은 돈을 지키는 쪽으로 가자."
    return "은퇴 후 · 지키며 쓰기", "이제는 모은 돈을 오래 나눠 쓰는 게 중요해. 무리한 투자는 줄이자."


# ---------------------------------------------------------------
# 5. 상황별 메시지
# ---------------------------------------------------------------
def greeting(name, items, done_count):
    """홈 화면 첫 인사: 기한이 가장 가까운 목표 이야기부터"""
    if not items:
        if done_count:
            return f"{name}, 세운 목표를 전부 이뤘어! 🎉 다음 꿈은 뭐야? '내 정보'에서 새 목표를 추가해줘."
        return f"안녕 {name}! 아직 목표가 없네. '내 정보'에서 이루고 싶은 걸 알려줘."
    it = items[0]
    g = it.goal
    pct = round(min(g.saved / g.target, 1) * 100) if g.target else 0
    if g.months <= 1:
        return f"{name}, {g.name}까지 {pct}% 왔어. 이번 달만 버티면 돼!"
    return f"안녕 {name}! {g.name}까지 {pct}% 모았어. 오늘도 같이 가보자."


def goal_done_message(goal_name):
    return f"{josa(goal_name, '을를')} 이뤘어! 우리 진짜 해냈다 🎉"


def plan_messages(plan):
    """목표별 저축 탭에서 머니가 하는 말"""
    msgs = []
    if plan.surplus <= 0:
        msgs.append("지금은 쓰는 돈이 버는 돈보다 많아. 저축보다 먼저 생활비를 같이 줄여보자.")
        return msgs

    if plan.emergency > 0:
        msgs.append(f"비상금이 3개월치({fmt(plan.emergency_target)})보다 적어서 "
                    f"이번 달엔 {fmt(plan.emergency)}을 먼저 떼어둘게. 갑자기 돈 쓸 일이 생겨도 목표는 지킬 수 있어.")

    behind = [it for it in plan.items if it.alloc < it.need]
    for it in behind[:2]:
        gap = it.need - it.alloc
        msgs.append(f"{josa(it.goal.name, '을를')} 기한 안에 이루려면 한 달에 {fmt(gap)}이 더 필요해. "
                    f"기한을 조금 늘리거나 생활비를 줄여보자.")
    if plan.items and not behind:
        msgs.append("목표 전부 기한 안에 이룰 수 있게 나눴어. 이대로만 가면 돼!")

    if plan.extra > 0:
        msgs.append(f"남는 {fmt(plan.extra)}은 노후·여유 자금으로 넣자. "
                    f"일찍 시작할수록 이자가 이자를 낳아서 나중에 훨씬 커져.")
    return msgs


def cut_tip_message(category, amount, goal_alloc, goal):
    """가장 많이 쓴 비필수 카테고리를 줄였을 때 가장 가까운 목표가 며칠 당겨지는지"""
    if goal is None or goal_alloc <= 0 or amount <= 0:
        return None
    if amount >= goal_alloc:
        return (f"{category}에서 {fmt(amount)}만 줄여도 "
                f"{josa(goal.name, '을를')} 위한 이번 달 저축은 다 채울 수 있어.")
    days = round(amount / goal_alloc * 30)
    return f"{category}에서 {fmt(amount)}만 줄이면 {josa(goal.name, '을를')} {days}일 일찍 이룰 수 있어."


def long_plan_message(item, risk):
    g = item.goal
    pct = round(item.invest_ratio * 100)
    msg = (f"{josa(g.name, '은는')} 기간이 길어서 {risk} 기준으로 투자 {pct}%까지 넣어도 괜찮아. "
           f"대신 목표가 가까워지면 투자를 줄여서 모은 돈을 지킬 거야.")
    if not item.on_track:
        msg += f" 지금 배분으로는 기한보다 늦어지니까, 다른 목표가 끝나면 그 돈을 여기로 돌리자."
    return msg


def retirement_message(need, extra):
    if need["monthly"] <= 0:
        return "지금 모아둔 돈으로도 노후 준비가 충분해 보여. 멋지다!"
    if extra >= need["monthly"]:
        return (f"노후 자금으로 매달 {fmt(need['monthly'])}이 필요한데, 지금 {fmt(extra)}씩 넣고 있어. "
                f"이대로면 노후도 든든해!")
    gap = need["monthly"] - extra
    return (f"노후 자금으로 매달 {fmt(need['monthly'])}이 필요한데, 지금은 {fmt(extra)}이야. "
            f"다른 목표를 이루고 나면 {fmt(gap)}씩 더 노후 쪽으로 돌려보자.")


def roadmap_messages(summary, checks, retire_age):
    """평생 로드맵 탭에서 머니가 하는 말 (부족해도 혼내지 않고 방법을 제안)"""
    msgs = []
    if summary["broke_age"] is None:
        msgs.append(f"지금 계획대로면 90세까지 돈이 든든하게 남아. 90세에도 예금·투자가 {fmt(summary['final'])} 남아 있어!")
    elif summary["broke_age"] < retire_age:
        msgs.append(f"{summary['broke_age']}세쯤 큰 목표들이 겹쳐서 돈이 잠깐 모자라. "
                    f"'평생 플랜'의 목표 페이지에서 기한을 조금 늘려보자.")
    else:
        msgs.append(f"은퇴 후 {summary['broke_age']}세쯤 현금이 바닥나. "
                    f"'노후 준비' 페이지에서 은퇴를 조금 늦추거나 노후 생활비를 줄여보자.")
        if any(c.get("loan") for c in checks):   # 대출로 산 집이 있으면
            msgs.append("그래도 집은 남아 있으니까, 집을 담보로 매달 연금을 받는 주택연금 같은 방법도 있어. "
                        "조건은 공식 안내에서 꼭 확인해줘.")

    missing = [c for c in checks if not c["ok"]]
    for c in missing[:2]:
        gap = c["cost"] - max(c["before"], 0)
        msgs.append(f"{josa(c['name'], '은는')} {c['age']}세에 {fmt(gap)} 정도 모자라. 시기를 1~2년 미루면 어떨까?")
    if checks and not missing:
        msgs.append("세운 목표들은 전부 그 나이에 이룰 수 있어. 정말 잘 짰다!")
    return msgs


def loan_messages(check, retire_age):
    """내 집 마련 대출 카드에서 동물 친구가 하는 말 (겁주지 않고 방법 위주로)"""
    msgs = [f"집값 {fmt(check['price'])}을 다 모을 필요는 없어. 내 돈(자기자금) {fmt(check['cost'])}만 모으고 "
            f"나머지는 대출로, 매달 {fmt(check['pay'])}씩 갚는 계획이야."]
    if check["payoff_age"] > retire_age:
        msgs.append(f"그런데 대출을 {check['payoff_age']}세에 다 갚아서 은퇴({retire_age}세) 뒤에도 갚아야 해. "
                    "여유가 생길 때 조금씩 미리 갚거나(중도상환), 상환 기간을 줄여보는 것도 방법이야.")
    if check["pay_ratio"] > 0.4:
        msgs.append("월급에 비해 갚는 돈이 커. 집값을 조금 낮추거나 자기자금을 더 모으면 훨씬 편해져.")
    return msgs


def pension_messages(pp, life, gap):
    """노후 준비 페이지에서 동물 친구가 하는 말 (연금 3층)"""
    msgs = []
    if gap > 0:
        msgs.append(f"연금 세 개를 합쳐도 한 달 {fmt(gap)}이 모자라. 지금부터 노후 자금을 조금씩 모으면 채울 수 있어.")
    else:
        msgs.append("연금 세 겹으로 노후 생활비를 다 채울 수 있어. 정말 든든하다!")
    if not life.private_monthly:
        msgs.append("아직 개인연금(IRP·연금저축)이 없네. 조금만 넣어도 연말정산 때 세금을 돌려받고 노후 연금도 늘어나. "
                    "아래 AI 추천 포트폴리오를 확인해봐!")
    elif pp["tax_refund"]:
        msgs.append(f"IRP·연금저축 덕분에 해마다 세금 {fmt(pp['tax_refund'])}을 돌려받고 있어. 잘하고 있어!")
    if pp["retire_type"] == "DC":
        msgs.append("DC형 퇴직연금은 내가 직접 굴리는 거라, 은퇴가 멀었을 땐 너무 예금에만 두지 않는 게 좋아.")
    return msgs


def purchase_message(item, price, impacts):
    lines = [f"{item} {fmt(price)}, 사면 이렇게 바뀌어."]
    for imp in impacts[:4]:
        lines.append(f"· {imp['name']}: 약 {imp['days']}일 늦어져")
    if not impacts:
        lines.append("· 지금은 목표에 넣는 돈이 없어서 계산이 어려워.")
    if impacts:
        far = max(impacts, key=lambda x: x["future_value"])
        if far["future_value"] > price * 1.05:
            lines.append(f"(오늘의 {fmt(price)}은 {far['name']} 시점엔 약 {fmt(far['future_value'])}의 가치야)")
    small = all(imp["days"] <= 14 for imp in impacts)
    lines.append("이 정도면 크게 무리는 아니야. 네가 정해!" if small
                 else "꽤 큰 영향이야. 정말 필요한지 하루만 더 생각해볼래?")
    return "\n".join(lines)


def review_messages(rows, planned_spending, total_this, goal_alloc, goal):
    """월간 점검: 약속 → 늘어난 곳 → 칭찬 → 목표 영향 순서로 먼저 말을 건다."""
    msgs = []

    # 1) 지난달에 한 약속부터 기억해서 꺼낸다
    for r in rows:
        if r["약속 한도"] is None:
            continue
        if r["약속 지킴"]:
            msgs.append(f"지난달 약속한 {r['카테고리']} {fmt(r['약속 한도'])}, "
                        f"이번 달 {fmt(r['이번 달'])}으로 지켰네! 최고야.")
        else:
            msgs.append(f"지난달 약속한 {r['카테고리']} {fmt(r['약속 한도'])}, "
                        f"이번 달엔 {fmt(r['이번 달'])} 썼더라.")

    # 2) 가장 많이 늘어난 카테고리
    up = max(rows, key=lambda r: r["변화"], default=None)
    if up and up["변화"] > 0:
        msgs.append(f"{josa(up['카테고리'], '이가')} 지난달보다 {fmt(up['변화'])} 늘었어.")

    # 3) 가장 많이 줄인 카테고리는 칭찬
    down = min(rows, key=lambda r: r["변화"], default=None)
    if down and down["변화"] < 0:
        msgs.append(f"대신 {josa(down['카테고리'], '은는')} {fmt(-down['변화'])}이나 줄였어. 잘했어!")

    # 4) 계획보다 더 쓴 만큼 가장 가까운 목표가 얼마나 늦어지는지
    over = total_this - planned_spending
    if over > 0 and goal is not None and goal_alloc > 0:
        days = round(over / goal_alloc * 30)
        msgs.append(f"계획보다 {fmt(over)} 더 써서 {josa(goal.name, '은는')} 약 {days}일 늦어지겠어.")
    elif over <= 0:
        msgs.append("이번 달은 계획한 생활비 안에서 썼어! 실천 배지 받을 자격 충분해.")

    return msgs
