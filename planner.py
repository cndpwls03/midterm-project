"""
planner.py — 재무 설계 계산 모듈
화면(app.py)과 분리해서 '돈 계산'만 담당합니다. 모든 금액 단위는 '만 원'입니다.

크게 네 가지를 계산해요.
1) 이번 달 돈 나누기 (여러 목표에 얼마씩 넣을지)
2) 장기 목표 플랜 (기간에 따라 예적금/투자 비중을 어떻게 바꿀지)
3) 평생 로드맵 (지금부터 90세까지 해마다 자산이 어떻게 변하는지)
4) 소비 내역 점검 (지난달과 이번 달 비교)
"""
import csv
import math
from dataclasses import dataclass, replace

# ---------------------------------------------------------------
# 1. 기본 설정값 (발표 때 "왜 이 숫자인지" 설명할 수 있어야 하는 부분)
# ---------------------------------------------------------------

# 투자 성향별 기본 자금 배분 비율: (예적금 비중, 투자 비중)
RISK_MIX = {
    "안정형": (0.8, 0.2),
    "중립형": (0.6, 0.4),
    "공격형": (0.3, 0.7),
}

# 시뮬레이션용 가정 연수익률 — 실제 수익을 보장하지 않습니다.
ASSUMED_RETURN = {"예적금": 0.03, "투자": 0.05}

EMERGENCY_MONTHS = 3      # 비상금 목표: 고정비+생활비의 3개월치
EMERGENCY_SHARE = 0.15    # 비상금이 부족할 때 저축 가능액 중 비상금에 넣는 비율
LIFE_END_AGE = 90         # 평생 로드맵을 계산하는 마지막 나이
PENSION_AGE = 65          # 국민연금을 받기 시작하는 나이 (가정)

# 투자 성향 진단 문항 (은행 투자성향 진단을 참고해 간단히 만든 5문항, 각 1~4점)
RISK_QUESTIONS = [
    ("투자해 본 경험이 있어?",
     [("예적금만 해봤어", 1), ("펀드나 ETF를 조금 해봤어", 2),
      ("주식·ETF를 꾸준히 해", 3), ("고위험 상품까지 해봤어", 4)]),
    ("투자한 돈이 1년 뒤 10% 떨어지면?",
     [("바로 다 팔 거야", 1), ("일부 팔고 지켜볼래", 2),
      ("그대로 기다릴래", 3), ("오히려 더 살래", 4)]),
    ("투자로 기대하는 건?",
     [("원금만 지키면 돼", 1), ("예금보다 조금 더", 2),
      ("물가보다 확실히 더", 3), ("손실이 나도 높은 수익", 4)]),
    ("이 돈을 쓸 때까지 얼마나 기다릴 수 있어?",
     [("1년 이내", 1), ("1~3년", 2), ("3~5년", 3), ("5년 이상", 4)]),
    ("가진 돈 중 투자에 쓸 수 있는 비중은?",
     [("10% 이하", 1), ("10~30%", 2), ("30~50%", 3), ("50% 이상", 4)]),
]


def risk_from_score(score: int) -> str:
    """진단 점수(5~20점)를 투자 성향으로 바꾼다."""
    if score <= 9:
        return "안정형"
    if score <= 14:
        return "중립형"
    return "공격형"


# ---------------------------------------------------------------
# 2. 데이터 묶음 (사용자 정보, 목표, 은퇴·가족 계획)
# ---------------------------------------------------------------

@dataclass
class Profile:
    name: str
    age: int                 # 가입할 때 나이
    job: str
    income: float            # 세후 월 수입
    fixed: float             # 고정비 (월세, 공과금, 통신비 등)
    spending: float          # 한 달 생활비 (평소 쓰는 돈)
    risk: str                # 안정형 / 중립형 / 공격형
    emergency_saved: float   # 지금 모아둔 비상금
    other_assets: float = 0.0     # 목표 외 예적금·투자 (노후·여유 자금)
    salary_growth: float = 0.03   # 연봉 상승률 (가정)
    months_passed: int = 0        # 가입 후 지난 개월 수 (예전 버전 호환용, 지금은 0)
    real_estate: float = 0.0      # 달성한 '내 집' 같은 부동산 가치

    @property
    def current_age(self) -> float:
        return self.age + self.months_passed / 12


@dataclass
class Goal:
    name: str
    target: float          # 목표 금액
    saved: float           # 지금까지 모은 돈
    months: int            # 목표까지 남은 기간 (개월)
    is_asset: bool = False # 내 집처럼 사고 나서도 '자산'으로 남는 목표인지
    done: bool = False     # 달성 여부
    category: str = ""     # 장기 목표 종류: 결혼 자금 / 내 집 마련 / 기타 장기 목표 ("" 이면 이름으로 추측)


# 장기 목표 종류 → (아이콘, 관련 상담 주제(knowledge.py), 이름에 들어가면 이 종류로 보는 단어)
GOAL_TYPES = {
    "결혼 자금": ("💍", "결혼 자금 설계", ["결혼", "웨딩", "신혼"]),
    "내 집 마련": ("🏠", "내 집 마련", ["집", "주택", "아파트", "전세"]),
    "노후 준비": ("🌳", "은퇴·노후 설계", []),
    "기타 장기 목표": ("🎯", "투자 처음 시작하기", []),
}
LONG_TERM_MONTHS = 12      # 기한이 1년보다 길면 장기 목표 (평생 플랜에 전용 페이지가 생김)


def goal_type(g) -> str:
    """목표의 종류. 저장된 종류가 없으면 이름과 '자산' 여부로 추측한다."""
    if g.category in GOAL_TYPES:
        return g.category
    for t, (_, _, words) in GOAL_TYPES.items():
        if any(w in g.name for w in words):
            return t
    return "내 집 마련" if g.is_asset else "기타 장기 목표"


@dataclass
class Life:
    retire_age: int = 60          # 은퇴 나이
    retire_spending: float = 200  # 은퇴 후 한 달 생활비 (지금 물가 기준)
    pension: float = 80           # 국민연금 예상 월 수령액
    child_on: bool = False        # 자녀 계획 여부
    child_age: int = 34           # 첫째가 태어날 때 내 나이
    child_years: int = 20         # 양육·교육 기간 (년)
    child_yearly: float = 1000    # 1년 양육·교육비
    # 내 집 마련 대출 (주택담보대출) — 모두 가정값, 실제 한도·금리는 지역·규제·소득(DSR)에 따라 다름
    loan_on: bool = True          # 집(자산으로 남는 목표)을 살 때 대출을 받는지
    loan_ratio: float = 0.6       # 집값 중 대출 비율 (0.6 = 60%, 나머지 40%는 모은 돈으로)
    loan_years: int = 30          # 상환 기간 (년), 원리금균등 상환
    loan_rate: float = 0.04       # 대출 금리 (연 4% 가정)
    # 연금 3층 (1층 국민연금은 위 pension) — 모두 가정값
    retire_pension_on: bool = True    # 2층 퇴직연금: 회사에 다니면 1년에 월급 한 달치 정도가 쌓임
    retire_pension_type: str = "DC"   # "DB"(회사가 굴림, 은퇴 직전 월급 기준) / "DC"(내가 굴림)
    private_monthly: float = 0        # 3층 개인연금: IRP·연금저축에 매달 넣는 돈 (저축에서 옮겨 넣음)


# ---------------------------------------------------------------
# 3. 기간·나이에 따른 예적금/투자 비중
# ---------------------------------------------------------------

def horizon_factor(years_left: float) -> float:
    """
    목표까지 남은 기간이 짧으면 투자 비중을 줄인다.
    투자는 손실이 나도 회복할 시간이 필요하기 때문 (1년 미만이면 투자 0%).
    """
    if years_left < 1:
        return 0.0
    if years_left < 3:
        return 0.3
    if years_left < 5:
        return 0.6
    return 1.0


def horizon_mix(risk: str, years_left: float):
    """성향 + 남은 기간으로 정한 (예적금 비중, 투자 비중)"""
    invest = RISK_MIX[risk][1] * horizon_factor(years_left)
    return 1 - invest, invest


def age_mix(risk: str, age: float):
    """노후 자금처럼 기한 없는 돈은 나이가 들수록 투자 비중을 줄인다 (40세부터 60세까지 절반으로)."""
    base = RISK_MIX[risk][1]
    if age < 40:
        factor = 1.0
    elif age < 60:
        factor = 1 - 0.5 * (age - 40) / 20
    else:
        factor = 0.4
    invest = base * factor
    return 1 - invest, invest


def mix_rate(invest_ratio: float) -> float:
    """투자 비중으로 계산한 가정 연수익률"""
    return (1 - invest_ratio) * ASSUMED_RETURN["예적금"] + invest_ratio * ASSUMED_RETURN["투자"]


def long_annual_rate(risk: str) -> float:
    """성향 기본 비중으로 계산한 가정 연수익률"""
    return mix_rate(RISK_MIX[risk][1])


def goal_kind(months: int) -> str:
    if months <= 12:
        return "단기"
    if months < 36:
        return "중기"
    return "장기"


def product_type(months: int, invest_ratio: float) -> str:
    """목표 기간에 맞는 상품 '유형' (특정 금융사·종목은 추천하지 않음)"""
    if months <= 12:
        return "자유적금·파킹통장"
    if months < 36:
        return "정기적금" + (" + 분산 펀드·ETF 조금" if invest_ratio > 0 else "")
    return "정기예금·적금 + 분산 펀드·ETF"


# ---------------------------------------------------------------
# 4. 목표 하나에 대한 계산 (기간이 줄어들수록 투자 비중도 줄이는 방식)
# ---------------------------------------------------------------

def _rate_at(risk: str, months_left: int) -> float:
    _, invest = horizon_mix(risk, months_left / 12)
    return mix_rate(invest)


def project_balance(saved, monthly, months, risk, steps):
    """매달 monthly씩 넣었을 때 steps개월 동안의 잔액 변화 (목표 기한 months 기준으로 비중 조정)"""
    balance = saved
    history = []
    for m in range(1, steps + 1):
        left = max(months - m + 1, 0)            # 이번 달 기준 남은 개월
        balance = balance * (1 + _rate_at(risk, left) / 12) + monthly
        history.append(balance)
    return history


def months_with_plan(goal: Goal, monthly, risk, limit=600):
    """매달 monthly씩 넣으면 몇 개월 뒤에 목표에 도달하는지 (못 이루면 None)"""
    if goal.saved >= goal.target:
        return 0
    if monthly <= 0:
        return None
    balance = goal.saved
    for m in range(1, limit + 1):
        left = max(goal.months - m + 1, 0)
        balance = balance * (1 + _rate_at(risk, left) / 12) + monthly
        if balance >= goal.target:
            return m
    return None


def monthly_need(goal: Goal, risk: str) -> float:
    """기한 안에 목표를 이루려면 매달 얼마가 필요한지 (조금씩 바꿔보며 찾는 방식)"""
    if goal.saved >= goal.target:
        return 0
    months = max(int(goal.months), 1)
    low, high = 0.0, goal.target
    for _ in range(40):
        mid = (low + high) / 2
        if project_balance(goal.saved, mid, months, risk, months)[-1] >= goal.target:
            high = mid
        else:
            low = mid
    return high


def months_to_goal(target, saved, monthly, annual_rate=0.0, limit=600):
    """고정 수익률로 목표까지 몇 개월 걸리는지 (못 이루면 None)"""
    if saved >= target:
        return 0
    if monthly <= 0:
        return None
    r = annual_rate / 12
    balance = saved
    for month in range(1, limit + 1):
        balance = balance * (1 + r) + monthly
        if balance >= target:
            return month
    return None


def glide_path(risk: str, months: int):
    """
    장기 목표를 기간별로 나눠, 시기마다 예적금/투자 비중을 보여준다.
    예) 10년 목표 → 지금~5년 차: 투자 많이 / 5~7년 차: 줄이기 / 마지막 1년: 예적금만
    """
    phases = []
    # (남은 기간 하한, 상한) 단위: 년
    bands = [(5, None), (3, 5), (1, 3), (0, 1)]
    for low, high in bands:
        start_left = months if high is None else min(months, high * 12)
        end_left = low * 12
        if start_left <= end_left:
            continue
        dep, inv = horizon_mix(risk, (start_left - 1) / 12 if start_left > 0 else 0)
        phases.append({
            "start": months - start_left,   # 시작 시점 (지금부터 몇 개월 뒤)
            "end": months - end_left,       # 끝 시점
            "deposit": dep,
            "invest": inv,
            "rate": mix_rate(inv),
        })
    return phases


# ---------------------------------------------------------------
# 5. 이번 달 돈 나누기 (여러 목표)
# ---------------------------------------------------------------

@dataclass
class GoalPlan:
    goal: Goal
    kind: str              # 단기 / 중기 / 장기
    need: float            # 기한 안에 이루려면 필요한 월 저축액
    alloc: float           # 이번 달 실제로 넣는 돈
    deposit: float         # 그중 예적금
    invest: float          # 그중 투자형
    invest_ratio: float    # 투자 비중
    rate: float            # 가정 연수익률 (지금 비중 기준)
    expected_months: object  # 지금 배분으로 달성까지 걸리는 개월 (못 이루면 None)
    product: str           # 추천 상품 유형
    price: float = None    # 대출로 사는 집이면 집값 (goal.target은 내 돈으로 모을 자기자금)

    @property
    def on_track(self) -> bool:
        return self.expected_months is not None and self.expected_months <= self.goal.months


@dataclass
class Plan:
    net: float             # 순수익 = 수입 - 고정비
    surplus: float         # 저축 가능액 = 순수익 - 생활비
    emergency: float       # 비상금(파킹통장)
    emergency_target: float
    items: list            # 목표별 배분 [GoalPlan, ...] (기한이 가까운 순서)
    extra: float           # 목표에 넣고 남은 돈 → 노후·여유 자금
    extra_deposit: float
    extra_invest: float

    @property
    def shortage(self) -> float:
        return sum(max(it.need - it.alloc, 0) for it in self.items)

    @property
    def total_invest(self) -> float:
        return sum(it.invest for it in self.items) + self.extra_invest

    @property
    def total_saving(self) -> float:
        return self.emergency + sum(it.alloc for it in self.items) + self.extra


def make_plan(p: Profile, goals, loan_ratio: float = 0.0) -> Plan:
    """
    순수익을 생활비 → 비상금 → 기한이 가까운 목표부터 → 남는 돈은 노후 자금 순서로 나눈다.
    loan_ratio: 집(자산 목표)을 대출로 살 때 대출 비율. 그러면 집값이 아니라 자기자금만 모으도록 계산한다.
    """
    net = p.income - p.fixed
    surplus = net - p.spending
    emergency_target = (p.fixed + p.spending) * EMERGENCY_MONTHS
    active = sorted([g for g in goals if not g.done], key=lambda g: g.months)

    remaining = max(surplus, 0)

    # (1) 비상금: 3개월치보다 부족할 때만 일부를 떼어둔다
    emergency = 0
    if remaining > 0:
        gap = max(emergency_target - p.emergency_saved, 0)
        emergency = round(min(remaining * EMERGENCY_SHARE, gap))
        remaining -= emergency

    # (2) 목표: 기한이 가까운 것부터 필요한 만큼 (남은 돈 한도 안에서)
    items = []
    for g in active:
        price = None
        if g.is_asset and loan_ratio > 0:   # 대출로 사는 집 → 모을 돈은 자기자금(집값 × (1 − 대출 비율))
            price = g.target
            g = replace(g, target=round(g.target * (1 - loan_ratio)))
        need = math.ceil(monthly_need(g, p.risk))
        alloc = min(need, remaining)
        remaining -= alloc
        dep_ratio, inv_ratio = horizon_mix(p.risk, g.months / 12)
        invest = round(alloc * inv_ratio)
        items.append(GoalPlan(
            goal=g, kind=goal_kind(g.months), need=need, alloc=alloc,
            deposit=alloc - invest, invest=invest, invest_ratio=inv_ratio,
            rate=mix_rate(inv_ratio),
            expected_months=months_with_plan(g, alloc, p.risk),
            product=product_type(g.months, inv_ratio),
            price=price,
        ))

    # (3) 남는 돈: 노후·여유 자금 (나이에 맞춰 투자 비중 조정)
    _, extra_inv_ratio = age_mix(p.risk, p.current_age)
    extra_invest = round(remaining * extra_inv_ratio)
    return Plan(net, surplus, emergency, emergency_target, items,
                remaining, remaining - extra_invest, extra_invest)


# ---------------------------------------------------------------
# 5-1. 내 포트폴리오 — 지금 가입한 상품과 금액 (모은 돈의 '진짜 출처')
# ---------------------------------------------------------------
# 상품 종류 → 묶음 (안전: 원금 보장 예적금 / 청약 / 투자: 원금 손실 가능 / 연금: 노후 연금 계좌)
HOLDING_TYPES = {
    "파킹통장·입출금": "안전", "자유적금·정기적금": "안전", "정기예금": "안전", "청년미래적금": "안전",
    "주택청약종합저축": "청약", "주식": "투자", "ETF·펀드": "투자", "ISA": "투자", "코인": "투자",
    "연금저축": "연금", "IRP": "연금", "기타": "안전",
}
EMERGENCY_USE = "비상금"
FREE_USE = "노후·여유 자금"


def default_holdings(p: Profile, goals):
    """처음 한 번: 가입 때 입력한 금액(비상금·그 외 자산·목표별 모은 돈)으로 기본 목록을 만든다."""
    rows = []
    if p.emergency_saved:
        rows.append({"상품": "파킹통장·입출금", "금액": p.emergency_saved, "용도": EMERGENCY_USE})
    if p.other_assets:
        rows.append({"상품": "자유적금·정기적금", "금액": p.other_assets, "용도": FREE_USE})
    for g in goals:
        if g.saved and not g.done:
            rows.append({"상품": "주택청약종합저축" if g.is_asset else "자유적금·정기적금", "금액": g.saved, "용도": g.name})
    return rows


def apply_holdings(p: Profile, goals, holdings):
    """
    내 포트폴리오를 기준으로 비상금·노후 자금·목표별 모은 돈을 다시 계산한다.
    용도가 '비상금'이면 비상금, 목표 이름이면 그 목표의 모은 돈, 나머지는 노후·여유 자금.
    """
    names = {g.name for g in goals}
    by_use = {}
    for h in holdings:
        use = h.get("용도") if h.get("용도") in names | {EMERGENCY_USE} else FREE_USE
        by_use[use] = by_use.get(use, 0) + float(h.get("금액") or 0)
    p = replace(p, emergency_saved=by_use.get(EMERGENCY_USE, 0), other_assets=by_use.get(FREE_USE, 0))
    goals = [replace(g, saved=by_use.get(g.name, 0)) if not g.done else g for g in goals]
    return p, goals


def holdings_by_group(holdings):
    """묶음(안전·청약·투자·연금)별 합계"""
    out = {}
    for h in holdings:
        grp = HOLDING_TYPES.get(h.get("상품"), "안전")
        out[grp] = out.get(grp, 0) + float(h.get("금액") or 0)
    return out


def total_assets(p: Profile, goals) -> float:
    """총자산 = 비상금 + 노후·여유 자금 + 목표별로 모은 돈 + 부동산"""
    return (p.emergency_saved + p.other_assets + p.real_estate
            + sum(g.saved for g in goals if not g.done))


# ---------------------------------------------------------------
# 6. 평생 로드맵 (지금 ~ 90세)
# ---------------------------------------------------------------

DSR_LIMIT = 0.4   # 은행권 DSR 규제 기준(연 소득 대비 1년 원리금 40%) — 참고용 비교 기준


def loan_payment(principal, annual_rate, years):
    """원리금균등 상환: 매달 같은 돈(원금+이자)을 갚을 때 한 달 상환액 (만 원)"""
    n = years * 12
    r = annual_rate / 12
    if principal <= 0 or n <= 0:
        return 0
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


PENSION_TAX_LIMIT = 900        # IRP + 연금저축 세액공제 한도 (연 만 원)
PENSION_TAX_RATE = (0.165, 0.132)   # 세액공제율: 총급여 5,500만 원 이하 16.5%, 넘으면 13.2%
NET_TO_GROSS = 0.85            # 세후 월급 ≈ 세전 월급 × 0.85 로 가정 (총급여 추정용)


def pension_plan(p: Profile, life: Life):
    """
    연금 3층 계산 (모두 가정값, 금액 단위 만 원)
    - 1층 국민연금: 입력한 월 수령액 (65세부터)
    - 2층 퇴직연금: 일하는 동안 해마다 월급 한 달치가 쌓임
        DC형 = 해마다 쌓인 돈을 성향·나이에 맞는 비중으로 굴림 / DB형 = 은퇴 직전 월급 × 일한 햇수
    - 3층 개인연금: IRP·연금저축에 매달 넣는 돈을 굴림 + 해마다 세액공제로 세금을 돌려받음
    은퇴하면 모인 퇴직·개인연금을 90세까지 나눠 받는다고 본다 (나눠 받는 동안 예적금 금리로 불어남).
    """
    start = int(p.current_age)
    years = max(life.retire_age - start, 0)
    dc = private = 0.0
    acc = {}                                    # 나이별 연금 계좌 잔액 (그 해 말 기준)
    for k in range(years):
        age = start + k
        salary = p.income * (1 + p.salary_growth) ** k          # 그 해 월급 (세후 기준으로 단순화)
        _, inv = age_mix(p.risk, age)
        r = mix_rate(inv)
        dc = dc * (1 + r) + salary
        private = private * (1 + r) + life.private_monthly * 12
        db_so_far = salary * (k + 1)
        retire_so_far = (dc if life.retire_pension_type == "DC" else db_so_far) if life.retire_pension_on else 0
        acc[age] = retire_so_far + private
    final_salary = p.income * (1 + p.salary_growth) ** (years - 1) if years else 0
    db = final_salary * years
    retire_balance = (dc if life.retire_pension_type == "DC" else db) if life.retire_pension_on else 0
    pay_years = max(LIFE_END_AGE - life.retire_age + 1, 1)
    pay_rate = ASSUMED_RETURN["예적금"]
    gross_year = p.income * 12 / NET_TO_GROSS
    tax_rate = PENSION_TAX_RATE[0] if gross_year <= 5500 else PENSION_TAX_RATE[1]
    yearly_in = life.private_monthly * 12
    return {
        "national": life.pension,
        "retire_type": life.retire_pension_type if life.retire_pension_on else None,
        "retire_balance": retire_balance, "dc_balance": dc, "db_balance": db,
        "retire_monthly": loan_payment(retire_balance, pay_rate, pay_years),
        "dc_monthly": loan_payment(dc, pay_rate, pay_years), "db_monthly": loan_payment(db, pay_rate, pay_years),
        "private_balance": private,
        "private_monthly_out": loan_payment(private, pay_rate, pay_years),
        "private_in": life.private_monthly,
        "tax_rate": tax_rate,
        "tax_refund": min(yearly_in, PENSION_TAX_LIMIT) * tax_rate,   # 해마다 돌려받는 세금
        "pay_years": pay_years, "acc": acc,
    }


def simulate_life(p: Profile, goals, life: Life, shift=None):
    """
    1년 단위로 90세까지 자산을 계산한다.
    - 은퇴 전: 매년 (월 저축 가능액 × 12)을 모으고, 연봉 상승률만큼 저축도 늘어난다고 가정
    - 은퇴 후: 국민연금(65세부터)을 받고 은퇴 생활비를 쓴다
    - 목표 기한이 되면 그 금액을 쓰고, 자녀가 있으면 매년 양육비를 쓴다
    - 연금 3층: 일하는 동안 개인연금 납입액은 현금에서 연금 계좌로 옮기고 세액공제를 돌려받는다.
      은퇴 뒤엔 국민연금 + 퇴직연금 + 개인연금을 매달 받는다 (pension_plan 참고)
    - 집(자산으로 남는 목표)은 대출을 켜면 자기자금(집값 × (1 − 대출 비율), 대출 없이 내 돈으로 내는 몫)만 현금으로 내고,
      다음 해부터 원리금균등으로 매달 갚는다. 집값은 부동산으로 남는다 (집값 상승은 가정하지 않음)
    shift: {"이벤트 이름": 미룰 햇수} — 시기를 옮겨 계산해볼 때 사용 (지금 화면에서는 안 씀)
    """
    shift = shift or {}
    start = int(p.current_age)
    active = [g for g in goals if not g.done]
    cash = p.emergency_saved + p.other_assets + sum(g.saved for g in active)
    home = p.real_estate
    yearly_save = max(p.income - p.fixed - p.spending, 0) * 12
    retire_age = life.retire_age + shift.get("은퇴", 0)
    child_start = life.child_age + shift.get("자녀 양육", 0)
    goal_age = {g.name: max(start + int(g.months // 12) + shift.get(g.name, 0), start) for g in active}

    pp = pension_plan(p, life)
    pension_bal = 0.0                    # 연금 계좌 잔액 (순자산에 포함)
    rows, checks = [], []
    loans = []   # 갚고 있는 대출 [{"balance": 남은 원금, "pay": 월 상환액}]
    for age in range(start, LIFE_END_AGE + 1):
        _, inv = age_mix(p.risk, age)
        cash += cash * mix_rate(inv) if cash > 0 else 0       # 이자·수익
        if age < retire_age:
            cash += yearly_save * (1 + p.salary_growth) ** (age - start)
            cash += pp["tax_refund"] - pp["private_in"] * 12      # 개인연금으로 옮긴 돈, 돌려받은 세금
            pension_bal = pp["acc"].get(age, pension_bal)
        else:
            pension = life.pension * 12 if age >= PENSION_AGE else 0
            payout = (pp["retire_monthly"] + pp["private_monthly_out"]) * 12 if age <= LIFE_END_AGE else 0
            if age == retire_age:
                pension_bal = pp["retire_balance"] + pp["private_balance"]
            pension_bal = max(pension_bal * (1 + ASSUMED_RETURN["예적금"]) - payout, 0)
            cash += pension + payout - life.retire_spending * 12

        # 대출 상환: 12달 동안 이자는 남은 원금에 붙고, 상환액 중 이자를 뺀 만큼 원금이 줄어든다
        for ln in loans:
            for _ in range(12):
                if ln["balance"] <= 0:
                    break
                interest = ln["balance"] * life.loan_rate / 12
                pay = min(ln["pay"], ln["balance"] + interest)
                ln["balance"] -= pay - interest
                cash -= pay
        loans = [ln for ln in loans if ln["balance"] > 0.5]

        events = []
        if life.child_on and child_start <= age < child_start + life.child_years:
            cash -= life.child_yearly
            if age == child_start:
                events.append("자녀 양육 시작")
        for g in active:
            if goal_age[g.name] == age:
                loan = g.target * life.loan_ratio if (g.is_asset and life.loan_on) else 0
                cost = g.target - loan          # 현금으로 내야 하는 돈 (대출이면 자기자금)
                check = {"name": g.name, "age": age, "cost": cost, "price": g.target, "loan": loan,
                         "before": cash, "ok": cash >= cost}
                if loan:
                    pay = loan_payment(loan, life.loan_rate, life.loan_years)
                    income_then = p.income * (1 + p.salary_growth) ** (age - start)
                    check.update({"pay": pay, "payoff_age": age + life.loan_years,
                                  "interest": pay * life.loan_years * 12 - loan,
                                  "pay_ratio": pay / income_then if income_then else 0})
                    loans.append({"balance": loan, "pay": pay})
                checks.append(check)
                cash -= cost
                if g.is_asset:
                    home += g.target
                events.append(g.name)
        if age == retire_age:
            events.append("은퇴")
        debt = sum(ln["balance"] for ln in loans)
        rows.append({"나이": age, "금융자산": round(cash), "부동산": round(home), "대출 잔액": round(debt),
                     "연금 자산": round(pension_bal),
                     "순자산": round(cash + home + pension_bal - debt), "이벤트": ", ".join(events)})
    return rows, checks


def life_summary(rows):
    """로드맵 요약: 돈이 바닥나는 나이, 90세 자산, 가장 적을 때"""
    broke = next((r["나이"] for r in rows if r["금융자산"] < 0), None)
    return {
        "broke_age": broke,
        "final": rows[-1]["금융자산"] if rows else 0,
        "final_net": rows[-1]["순자산"] if rows else 0,     # 금융자산 + 부동산 − 대출
        "min": min((r["금융자산"] for r in rows), default=0),
    }


def retirement_need(p: Profile, life: Life):
    """은퇴 후 90세까지 필요한 돈과, 그 돈을 은퇴 전까지 모으려면 매달 얼마가 필요한지"""
    pp = pension_plan(p, life)
    total = 0
    for age in range(life.retire_age, LIFE_END_AGE + 1):
        pension = (life.pension if age >= PENSION_AGE else 0) + pp["retire_monthly"] + pp["private_monthly_out"]
        total += max(life.retire_spending - pension, 0) * 12
    months_left = max(round((life.retire_age - p.current_age) * 12), 1)
    mid_age = (p.current_age + life.retire_age) / 2
    _, inv = age_mix(p.risk, mid_age)
    rate = mix_rate(inv)
    monthly = _monthly_for(total, p.other_assets, months_left, rate)
    return {"total": total, "monthly": monthly, "months_left": months_left, "rate": rate}


def _monthly_for(target, saved, months, annual_rate):
    """고정 수익률로 months개월 뒤 target을 만들려면 매달 얼마가 필요한지"""
    r = annual_rate / 12
    grow = (1 + r) ** months
    rest = target - saved * grow
    if rest <= 0:
        return 0
    return rest / months if r == 0 else rest * r / (grow - 1)


# ---------------------------------------------------------------
# 7. "이거 사도 돼?" — 소비가 목표들에 미치는 영향
# ---------------------------------------------------------------

def purchase_impact(price, plan: Plan):
    """
    price만큼 쓰면 목표별로 며칠 늦어지는지 계산한다.
    오늘 쓴 돈은 목표 시점까지 불어날 기회도 잃으므로 미래가치로 환산한다.
    """
    result = []
    for it in plan.items:
        if it.alloc <= 0:
            continue
        future_value = price * (1 + it.rate / 12) ** it.goal.months
        result.append({"name": it.goal.name,
                       "days": round(future_value / it.alloc * 30),
                       "future_value": round(future_value, 1)})
    return result


# ---------------------------------------------------------------
# 8. 월간 점검 — 소비 내역 불러오기와 비교
# ---------------------------------------------------------------

def load_transactions(path_or_lines):
    """CSV(날짜,카테고리,내용,금액)를 읽어 {월: {카테고리: 합계}} 형태로 만든다. 금액 단위: 원"""
    if isinstance(path_or_lines, str):
        with open(path_or_lines, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = list(csv.DictReader(path_or_lines))

    by_month = {}
    for row in rows:
        month = row["날짜"][:7]                 # 2026-10-03 → 2026-10
        cat = row["카테고리"].strip()
        amount = int(str(row["금액"]).replace(",", ""))
        by_month.setdefault(month, {})
        by_month[month][cat] = by_month[month].get(cat, 0) + amount
    return dict(sorted(by_month.items()))


def compare_months(last: dict, this: dict, promises: dict):
    """카테고리별로 지난달과 이번 달을 비교하고, 약속(한도)을 지켰는지 확인한다. 단위: 만 원"""
    rows = []
    for cat in sorted(set(last) | set(this), key=lambda c: -this.get(c, 0)):
        before = round(last.get(cat, 0) / 10000)
        now = round(this.get(cat, 0) / 10000)
        limit = promises.get(cat)
        rows.append({
            "카테고리": cat,
            "지난달": before,
            "이번 달": now,
            "변화": now - before,
            "약속 한도": limit,
            "약속 지킴": None if limit is None else now <= limit,
        })
    return rows
