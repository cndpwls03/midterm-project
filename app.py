"""
app.py — '머니: 평생 함께하는 재무설계사' 화면
실행: streamlit run app.py

화면 흐름
  가입(1~4단계: 기본 정보 → 투자 성향 진단 → 목표 → 은퇴·가족 계획)
  → 캐릭터 만들기(5단계)
  → 메인 화면 (탭: 홈 / 소비 / 이번 달 플랜 / 평생 플랜 / AI 재무설계사와 상담하기)
  → 사이드바: 내 정보 수정, 캐릭터 꾸미기

계산은 planner.py, 캐릭터 말투는 character.py, 캐릭터 그림은 avatar.py, 화면 꾸미기는 ui.py,
AI 조언은 advisor.py, 카드 분류는 classifier.py, 기억은 memory.py, AI 대화는 llm.py가 담당합니다.
"""
import math
import os
from dataclasses import replace

import altair as alt
import pandas as pd
import streamlit as st

import advisor as adv
import avatar as av
import character as ch
import consult as cs
import habits as hb
import llm
import memory as mem
import knowledge as kn
import planner as pl
import portfolio as pf
import ui

st.set_page_config(page_title="머니 - 평생 재무설계사", page_icon="🌱", layout="centered")
ui.inject_css()   # 글꼴·색·카드 모양 적용

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "data", "sample_spending.csv")
ESSENTIAL = {"식비", "교통", "기타"}  # 줄이라고 하기 어려운 카테고리 (절약 팁에서 제외)
JOBS = ["사무직(회사원)", "공무원", "전문직", "IT·개발", "금융", "서비스·판매", "생산·기술",
        "자영업", "프리랜서", "학생·취업 준비", "기타"]
STEP_NAMES = ["기본 정보", "투자 성향 진단", "나의 목표", "은퇴·가족 계획", "캐릭터 만들기"]
RISK_HELP = ("안정형: 원금 손실이 싫어요 / 중립형: 약간의 손실은 감수해요 / "
             "공격형: 높은 수익을 위해 손실도 감수해요")

# 캐릭터의 기억을 불러온다 (앱을 껐다 켜도 유지)
if "memory" not in st.session_state:
    st.session_state.memory = mem.load()
memory = st.session_state.memory


def remember():
    mem.save(memory)


def show_avatar(look, age, level, width=220):
    """캐릭터 SVG를 화면 가운데에 그린다."""
    st.markdown(f"<div style='text-align:center'>{ui.avatar_img(look, age, level, width)}</div>",
                unsafe_allow_html=True)


def pick(label, options, current, key, fmt=None):
    """알약 모양 버튼으로 하나 고르기. 선택을 해제하면 원래 값을 유지한다."""
    value = st.pills(label, options, selection_mode="single", key=key,
                     default=current if current in options else options[0],
                     format_func=fmt or (lambda x: x))
    return value if value is not None else current


def avatar_editor(look, age, key):
    """동물 친구 꾸미기 화면. 위에는 동물 고르기, 아래 왼쪽은 미리보기, 오른쪽은 꾸미기. 고른 모양(dict)을 돌려준다."""
    look = {**av.DEFAULT_LOOK, **(look or {})}
    if look["animal"] not in av.ANIMALS:      # 예전 사람 캐릭터 정보면 기본 동물로
        look = dict(av.DEFAULT_LOOK)
    new = dict(look)

    # 1) 동물 고르기: 지금 꾸민 옷·머리띠를 입힌 썸네일로 나란히 보여줌
    animals = list(av.ANIMALS)
    with st.container(key="card-animals"):
        st.markdown("**1. 동물 친구 고르고 이름 짓기** — 이 친구가 평생 내 재무설계사가 되어줄 거야")
        name = st.text_input("친구 이름", look.get("name") or ch.NAME, max_chars=10, key=f"{key}_name",
                             placeholder="예: 머니, 몽실이, 저금이")
        new["name"] = name.strip() or ch.NAME
        cols = st.columns(len(animals))
        for col, a in zip(cols, animals):
            col.markdown(f"<div style='text-align:center'>{ui.avatar_img(dict(look, animal=a, fur='기본'), 27, 0, 86)}</div>",
                         unsafe_allow_html=True)
        new["animal"] = pick("동물", animals, look["animal"], f"{key}_an",
                             fmt=lambda a: f"{av.ANIMALS[a][0]} {a}")

    left, right = st.columns([1, 1.25])
    with right:
        st.markdown("**2. 꾸미기**")
        new["fur"] = pick("털 색", list(av.FUR_COLORS), look["fur"], f"{key}_fur")
        new["eyes"] = pick("눈", av.EYE_STYLES, look["eyes"], f"{key}_eye")
        new["outfit"] = pick("옷", av.OUTFITS, look["outfit"], f"{key}_out")
        new["head"] = pick("머리 장식", av.HEADWEAR, look["head"], f"{key}_head")
        new["glasses"] = pick("안경", av.GLASSES, look["glasses"], f"{key}_gl")
        new["neck"] = pick("목 장식", av.NECKWEAR, look["neck"], f"{key}_neck")
        c1, c2, c3 = st.columns(3)
        new["cloth"] = c1.color_picker("옷 색", look["cloth"], key=f"{key}_cl")
        new["accent"] = c2.color_picker("장식 색", look["accent"], key=f"{key}_ac")
        new["cheek"] = c3.checkbox("볼터치", look["cheek"], key=f"{key}_ck")
    with left:
        st.markdown("**미리보기**")
        preview = st.empty()
        preview_age = st.slider("나이 들면?", 20, 90, int(age), key=f"{key}_age")
        preview_level = st.select_slider(
            "부자가 되면?", options=list(range(len(ch.WEALTH_LEVELS))),
            format_func=lambda i: ch.WEALTH_LEVELS[i][1], key=f"{key}_lv")
        with preview.container():
            show_avatar(new, preview_age, preview_level, width=270)
            st.markdown(f"<p style='text-align:center;color:#6B7280'>{preview_age}세 · "
                        f"{ch.WEALTH_LEVELS[preview_level][1]} · {ch.WEALTH_LEVELS[preview_level][2]}</p>",
                        unsafe_allow_html=True)
    return new


# ===============================================================
# 가입 화면 (1~5단계)
# ===============================================================
def go(step):
    st.session_state.step = step
    st.rerun()


def onboarding():
    d = st.session_state.setdefault("draft", {})       # 가입 중에 입력한 값을 임시로 모아두는 곳
    step = st.session_state.setdefault("step", 1)

    st.markdown("<div class='hero' style='display:block'><div class='hello'>🌱 머니에 온 걸 환영해!</div>"
                "<div class='sub' style='margin:6px 0 0'>몇 가지만 알려주면, 평생 함께할 동물 친구 재무설계사가 "
                "지금부터 90세까지 재무 계획을 같이 세워줄게요.</div></div>",
                unsafe_allow_html=True)
    st.progress(step / len(STEP_NAMES), text=f"{step}/{len(STEP_NAMES)}단계 · {STEP_NAMES[step - 1]}")

    # ---------- 1단계: 기본 정보 ----------
    if step == 1:
        with st.form("step1"):
            st.subheader("1. 나에 대해 알려줘")
            name = st.text_input("닉네임", d.get("name", ""), placeholder="예: 지민")
            c1, c2 = st.columns(2)
            age = c1.number_input("나이", 18, 80, d.get("age", 27))
            job = c2.selectbox("직업", JOBS, index=JOBS.index(d.get("job", JOBS[0])))

            st.markdown("**한 달 돈 흐름** (단위: 만 원)")
            income = st.number_input("세후 월급 (통장에 실제로 들어오는 돈)", 0, 10000, d.get("income", 250), step=10)
            c1, c2 = st.columns(2)
            fixed = c1.number_input("고정비 (월세·관리비·통신비·보험료)", 0, 10000, d.get("fixed", 30), step=5)
            spending = c2.number_input("생활비 (식비·쇼핑·교통·여가)", 0, 10000, d.get("spending", 120), step=5)

            st.markdown("**지금 가진 돈** (단위: 만 원)")
            c1, c2 = st.columns(2)
            emergency = c1.number_input("바로 꺼내 쓸 수 있는 현금 (비상금)", 0, 100000,
                                        d.get("emergency_saved", 200), step=10)
            other = c2.number_input("그 외 예적금·투자", 0, 1000000, d.get("other_assets", 0), step=50,
                                    help="목표용으로 모은 돈은 3단계에서 목표별로 따로 입력해요. 가입 후 홈의 '내 포트폴리오'에서 상품별로 나눠 적을 수 있어요.")
            growth = st.slider("앞으로 연봉이 매년 몇 % 오를까? (가정)", 0.0, 10.0,
                               d.get("growth_pct", 3.0), 0.5)

            if st.form_submit_button("다음 →", type="primary"):
                d.update(name=name.strip() or "나", age=int(age), job=job, income=income, fixed=fixed,
                         spending=spending, emergency_saved=emergency, other_assets=other,
                         growth_pct=growth)
                go(2)

    # ---------- 2단계: 투자 성향 진단 ----------
    elif step == 2:
        st.subheader("2. 투자 성향 진단")
        st.caption("은행의 투자성향 진단을 참고해 간단히 만든 5문항이에요. 정답은 없으니 편하게 골라줘.")
        prev = d.get("risk_answers", [0] * len(pl.RISK_QUESTIONS))
        with st.form("step2"):
            answers = []
            for i, (question, options) in enumerate(pl.RISK_QUESTIONS):
                labels = [o[0] for o in options]
                choice = st.radio(f"Q{i + 1}. {question}", labels, index=prev[i], key=f"rq{i}")
                answers.append(labels.index(choice))
            checked = st.form_submit_button("결과 보기")
        if checked:
            score = sum(pl.RISK_QUESTIONS[i][1][a][1] for i, a in enumerate(answers))
            d.update(risk_answers=answers, risk_score=score, risk=pl.risk_from_score(score))

        if "risk_score" in d:
            dep, inv = pl.RISK_MIX[d["risk"]]
            st.success(f"진단 결과: **{d['risk']}** ({d['risk_score']}점 / 20점) — "
                       f"기본 비중 예적금 {round(dep * 100)}% · 투자 {round(inv * 100)}%")
            d["risk"] = st.radio("이 성향으로 진행할게요 (원하면 바꿔도 돼요)", list(pl.RISK_MIX),
                                 index=list(pl.RISK_MIX).index(d["risk"]), horizontal=True, help=RISK_HELP)
        c1, c2 = st.columns(2)
        if c1.button("← 이전"):
            go(1)
        if c2.button("다음 →", type="primary", disabled="risk_score" not in d):
            go(3)

    # ---------- 3단계: 목표 ----------
    elif step == 3:
        age = d["age"]
        st.subheader("3. 이루고 싶은 목표")
        st.caption("비상금(생활비 3개월치)은 동물 친구가 알아서 챙겨요. 금액 단위: 만 원")
        presets = d.get("presets", {
            "결혼 자금": {"on": age < 35, "target": 3000, "at": max(age + 3, 32), "saved": 0, "asset": False},
            "내 집 마련": {"on": True, "target": 30000, "at": max(age + 8, 38), "saved": 500, "asset": True},
        })
        custom = d.get("custom", pd.DataFrame([
            {"목표": "코트", "목표 금액": 30, "모은 돈": 21, "기한(개월)": 1},
            {"목표": "해외여행", "목표 금액": 300, "모은 돈": 50, "기한(개월)": 12},
        ]))
        with st.form("step3"):
            st.markdown("**인생의 큰 목표** — 체크한 것만 계획에 넣어요")
            new_presets = {}
            for label, p in presets.items():
                c = st.columns([1.2, 1, 1, 1])
                on = c[0].checkbox(label, p["on"], key=f"p_{label}_on")
                target = c[1].number_input("목표 금액", 1, 1000000, p["target"], step=100, key=f"p_{label}_t")
                at = c[2].number_input("몇 살에?", age, 90, max(p["at"], age), key=f"p_{label}_a")
                saved = c[3].number_input("지금 모은 돈", 0, 1000000, p["saved"], step=50, key=f"p_{label}_s")
                new_presets[label] = {"on": on, "target": target, "at": at, "saved": saved, "asset": p["asset"]}

            st.markdown("**그 밖의 목표** — 표를 눌러서 고치거나, 맨 아래 줄에서 추가할 수 있어요")
            edited = st.data_editor(
                custom, num_rows="dynamic", hide_index=True, key="custom_goals",
                column_config={
                    "목표": st.column_config.TextColumn("목표", required=True),
                    "목표 금액": st.column_config.NumberColumn("목표 금액(만 원)", min_value=1, step=1),
                    "모은 돈": st.column_config.NumberColumn("모은 돈(만 원)", min_value=0, step=1),
                    "기한(개월)": st.column_config.NumberColumn("기한(개월)", min_value=1, max_value=480, step=1),
                })
            submitted = st.form_submit_button("다음 →", type="primary")
        if submitted:
            goals = []
            for label, p in new_presets.items():
                if p["on"]:
                    goals.append({"name": label, "target": p["target"], "saved": p["saved"],
                                  "months": max((p["at"] - age) * 12, 1), "is_asset": p["asset"], "done": False})
            goals += goals_from_table(edited)
            d.update(presets=new_presets, custom=edited, goals=unique_names(goals))
            if not d["goals"]:
                st.error("목표를 하나 이상 정해줘!")
            else:
                go(4)
        if st.button("← 이전"):
            go(2)

    # ---------- 4단계: 은퇴·가족 계획 ----------
    elif step == 4:
        age = d["age"]
        life = d.get("life", {"retire_age": 60, "retire_spending": 200, "pension": 80,
                              "child_on": False, "child_age": max(age + 7, 34), "child_years": 20,
                              "child_yearly": 1000})
        st.subheader("4. 은퇴·가족 계획")
        st.caption("평생 로드맵을 그리는 데 쓰여요. 모르면 기본값 그대로 둬도 괜찮아요. 금액 단위: 만 원")
        with st.form("step4"):
            new_life = life_inputs(life, age, key="ob")
            submitted = st.form_submit_button("다음 → 캐릭터 만들기", type="primary")
        if submitted:
            d["life"] = new_life
            go(5)
        if st.button("← 이전"):
            go(3)

    # ---------- 5단계: 캐릭터 만들기 ----------
    elif step == 5:
        st.subheader("5. 함께할 동물 친구 만들기")
        st.caption("마음에 드는 동물을 고르고 옷과 머리띠로 꾸며줘. 나이가 들면 친구도 함께 나이 들고, "
                   "돈을 모아 목표를 이룰수록 점점 부자가 돼요.")
        look = avatar_editor(d.get("avatar"), d["age"], key="new")
        d["avatar"] = look
        c1, c2 = st.columns(2)
        if c1.button("← 이전"):
            go(4)
        if c2.button("완성! 함께 시작하기 🎉", type="primary"):
            memory["profile"] = {
                "name": d["name"], "age": d["age"], "job": d["job"], "income": d["income"],
                "fixed": d["fixed"], "spending": d["spending"], "risk": d["risk"],
                "emergency_saved": d["emergency_saved"], "other_assets": d["other_assets"],
                "salary_growth": d["growth_pct"] / 100, "months_passed": 0, "real_estate": 0,
            }
            memory["goals"] = d["goals"]
            memory["life"] = d["life"]
            memory["avatar"] = look
            remember()
            st.session_state.pop("draft", None)
            st.session_state.pop("step", None)
            st.session_state.flash = [f"반가워 {d['name']}! 나는 {look.get('name') or ch.NAME}야. 평생 같이 가보자 🌱"]
            st.session_state.balloons = True
            st.rerun()


def life_inputs(life, age, key):
    """은퇴·자녀 계획 입력칸 (가입 4단계와 '내 정보' 탭에서 같이 사용)"""
    c1, c2, c3 = st.columns(3)
    retire_age = c1.number_input("은퇴 나이", min(age + 1, 80), 80, max(life["retire_age"], min(age + 1, 80)),
                                 key=f"{key}_ra")
    retire_spending = c2.number_input("은퇴 후 한 달 생활비", 0, 10000, life["retire_spending"], step=10,
                                      key=f"{key}_rs", help="지금 물가 기준으로 생각해줘.")
    pension = c3.number_input("국민연금 예상 월 수령액", 0, 1000, life["pension"], step=10, key=f"{key}_pe",
                              help="국민연금공단 '내 연금 알아보기'에서 확인할 수 있어요. 65세부터 받는다고 가정해요.")
    child_on = st.checkbox("자녀 계획이 있어요", life["child_on"], key=f"{key}_co")
    c1, c2, c3 = st.columns(3)
    child_age = c1.number_input("첫째가 태어날 때 내 나이", age, 60, max(life["child_age"], age), key=f"{key}_ca")
    child_years = c2.number_input("양육·교육 기간 (년)", 1, 30, life["child_years"], key=f"{key}_cy")
    child_yearly = c3.number_input("1년 양육·교육비", 0, 10000, life["child_yearly"], step=100, key=f"{key}_cc")
    # 내 집 마련 대출 (주택담보대출) — 모두 가정값
    loan_on = st.checkbox("집을 살 때 대출을 받을 거예요 (주택담보대출)", life.get("loan_on", True), key=f"{key}_lo",
                          help="'자산으로 남음'에 체크한 목표(예: 내 집 마련)에 적용돼요.")
    c1, c2, c3 = st.columns(3)
    loan_ratio = c1.number_input("집값 중 대출 비율 (%)", 0, 80, round(life.get("loan_ratio", 0.6) * 100), step=5,
                                 key=f"{key}_lr", help="실제 한도는 지역·규제(LTV)·소득(DSR)에 따라 달라요. 은행이나 주택도시기금에서 확인해줘.")
    loan_years = c2.number_input("상환 기간 (년)", 5, 50, life.get("loan_years", 30), step=5, key=f"{key}_ly")
    loan_rate = c3.number_input("대출 금리 (연 %, 가정)", 0.0, 15.0, round(life.get("loan_rate", 0.04) * 100, 1),
                                step=0.1, key=f"{key}_lt")
    return {"retire_age": int(retire_age), "retire_spending": retire_spending, "pension": pension,
            "child_on": child_on, "child_age": int(child_age), "child_years": int(child_years),
            "child_yearly": child_yearly, "loan_on": loan_on, "loan_ratio": loan_ratio / 100,
            "loan_years": int(loan_years), "loan_rate": round(loan_rate / 100, 4)}


def goals_from_table(df, old=None):
    """표(data_editor)에 입력한 목표를 저장 형식으로 바꾼다. 빈 줄은 건너뛴다.
    old: 원래 목표 목록 — 이름이 같으면 목표 종류(category)를 그대로 이어받는다."""
    kinds = {g["name"]: g.get("category", "") for g in (old or [])}
    goals = []
    for _, row in df.iterrows():
        name = row.get("목표")
        if pd.isna(name) or not str(name).strip():
            continue
        target = row.get("목표 금액")
        if pd.isna(target) or target <= 0:
            continue
        saved = 0 if pd.isna(row.get("모은 돈")) else float(row.get("모은 돈"))
        months = 12 if pd.isna(row.get("기한(개월)")) else int(row.get("기한(개월)"))
        goals.append({"name": str(name).strip(), "target": float(target), "saved": saved,
                      "months": max(months, 1),
                      "is_asset": bool(row.get("자산", False)) if not pd.isna(row.get("자산", False)) else False,
                      "done": bool(row.get("달성", False)) if not pd.isna(row.get("달성", False)) else False,
                      "category": kinds.get(str(name).strip(), "")})
    return goals


def unique_names(goals):
    """목표 이름이 겹치면 뒤에 숫자를 붙인다 (예: 여행, 여행2)"""
    seen = {}
    for g in goals:
        base = g["name"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            g["name"] = f"{base}{seen[base]}"
    return goals


if not memory.get("profile") or not memory.get("avatar"):
    onboarding()
    st.stop()


# ===============================================================
# 여기부터 메인 화면 — 저장된 정보로 계산
# ===============================================================
profile = pl.Profile(**memory["profile"])
goals = [pl.Goal(**g) for g in memory["goals"]]
life = pl.Life(**memory["life"])
look = memory["avatar"]
if memory.get("holdings") is None:      # 처음 한 번: 가입 때 입력한 금액으로 기본 포트폴리오를 만든다
    memory["holdings"] = pl.default_holdings(profile, goals)
    remember()
holdings = memory["holdings"]
profile, goals = pl.apply_holdings(profile, goals, holdings)   # 비상금·목표별 모은 돈은 포트폴리오에서 계산

active = [g for g in goals if not g.done]
done = [g for g in goals if g.done]
plan = pl.make_plan(profile, goals, life.loan_ratio if life.loan_on else 0)   # 대출로 사는 집은 자기자금만 모음
nearest = plan.items[0] if plan.items else None    # 기한이 가장 가까운 목표
age_now = int(profile.current_age)
assets = pl.total_assets(profile, goals)
wealth = ch.wealth_of(assets)
badges = memory["points"]                            # 실천 배지 (소비 참기·조언 실천·목표 달성)
buddy = (look or {}).get("name") or ch.NAME          # 내가 지어준 동물 친구 이름 (= 나의 재무설계사)
animal = (look or {}).get("animal") if (look or {}).get("animal") in av.ANIMALS else av.DEFAULT_LOOK["animal"]
BUDDY_ICON = av.ANIMALS[animal][0]                   # 말풍선에 나오는 동물 아이콘


def say(text):
    """동물 친구가 말하는 말풍선"""
    with st.chat_message("assistant", avatar=BUDDY_ICON):
        st.markdown(ui.esc(text))


def back_home():
    st.session_state.page = None
    st.rerun()


# ---- 목표를 바꿀 때 '내 포트폴리오'도 같이 정리하는 도우미 ----
def add_goal(name, target, months, saved=0.0, is_asset=False, category=""):
    """목표를 추가한다. 이미 모은 돈이 있으면 그 목표 용도의 상품으로 포트폴리오에 넣는다."""
    memory["goals"].append({"name": name, "target": float(target), "saved": 0.0, "months": int(months),
                            "is_asset": is_asset, "done": False, "category": category})
    memory["goals"] = unique_names(memory["goals"])
    final = memory["goals"][-1]["name"]
    if saved:
        memory["holdings"].append({"상품": "주택청약종합저축" if is_asset else "자유적금·정기적금",
                                   "금액": float(saved), "용도": final})
    return final


def delete_goal(name):
    """목표를 지운다. 그 목표용으로 모은 돈은 '노후·여유 자금'으로 옮긴다."""
    memory["goals"] = [g for g in memory["goals"] if g["name"] != name]
    for h in memory["holdings"]:
        if h.get("용도") == name:
            h["용도"] = pl.FREE_USE
    memory["portfolios"].pop(name, None)


def complete_goal(name):
    """목표 달성: 그 목표용으로 모은 돈은 썼다고 보고 포트폴리오에서 빼고, 집이면 부동산으로 남긴다."""
    for g in memory["goals"]:
        if g["name"] == name:
            g["done"] = True
            if g.get("is_asset"):
                memory["profile"]["real_estate"] = memory["profile"].get("real_estate", 0) + g["target"]
    memory["holdings"] = [h for h in memory["holdings"] if h.get("용도") != name]
    memory["points"] += ch.POINTS["short_goal_done"]


# ---------------- 사이드바: 내 캐릭터 + 설정 메뉴 ----------------
with st.sidebar:
    st.markdown(f"<div style='text-align:center'>{ui.avatar_img(look, age_now, wealth['level'], 150)}</div>",
                unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;margin-top:8px'>{BUDDY_ICON} <b>{buddy}</b> & <b>{profile.name}</b> · {age_now}세<br>"
                f"<span style='color:#6B7280'>{profile.job} · {profile.risk}</span></p>", unsafe_allow_html=True)
    if st.button("✏️ 내 정보 수정", width="stretch"):
        st.session_state.page = "settings"
        st.rerun()
    if st.button("🎨 캐릭터 꾸미기", width="stretch"):
        st.session_state.page = "avatar"
        st.rerun()
    st.caption(f"🤖 AI 연결됨 ({llm.provider()})" if llm.api_available() else "🔤 기본 모드 (API 키 없음)")
    if llm.key_problem():
        st.caption("⚠️ " + llm.key_problem())
    st.divider()
    with st.expander("처음부터 다시 시작"):
        st.caption("가입 정보, 목표, 캐릭터, 배지, 대화 기록이 모두 지워져요. (소비 내역은 남아요)")
        sure = st.checkbox("정말 지울게요")
        if st.button("모두 지우고 다시 가입", disabled=not sure):
            mem.reset()
            st.session_state.memory = mem.load()
            for k in ["draft", "step", "purchase", "page"]:
                st.session_state.pop(k, None)
            st.rerun()

# ---------------- 캐릭터 꾸미기 화면 ----------------
if st.session_state.get("page") == "avatar":
    st.markdown("## 🎨 동물 친구 꾸미기")
    st.caption("동물과 옷, 머리 장식을 바꿔봐. 슬라이더로 나이 든 모습, 부자가 된 모습도 미리 볼 수 있어요.")
    new_look = avatar_editor(look, age_now, key="edit")
    c1, c2 = st.columns(2)
    if c1.button("← 돌아가기", width="stretch"):
        back_home()
    if c2.button("저장하기", type="primary", width="stretch"):
        memory["avatar"] = new_look
        remember()
        st.session_state.flash = ["캐릭터를 새로 꾸몄어!"]
        back_home()
    st.stop()

# ---------------- 내 정보 수정 화면 ----------------
if st.session_state.get("page") == "settings":
    st.markdown("## ✏️ 내 정보 수정")
    st.caption("목표는 '💰 이번 달 플랜'(짧은 목표)과 '🗺️ 평생 플랜'(장기 목표)에서, 모은 돈은 홈의 '💼 내 포트폴리오'에서 고쳐요.")
    if st.button("← 돌아가기"):
        back_home()
    with st.form("edit_profile"):
        st.markdown("**👤 기본 정보**")
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("닉네임", profile.name)
        age_in = c2.number_input("지금 나이", 18, 90, age_now)
        job = c3.selectbox("직업", JOBS, index=JOBS.index(profile.job) if profile.job in JOBS else 0)
        st.markdown("**💸 한 달 돈 흐름** (만 원)")
        c1, c2, c3 = st.columns(3)
        income = c1.number_input("세후 월급", 0, 10000, int(profile.income), step=10)
        fixed = c2.number_input("고정비", 0, 10000, int(profile.fixed), step=5)
        spending = c3.number_input("생활비", 0, 10000, int(profile.spending), step=5)
        risk = st.radio("투자 성향", list(pl.RISK_MIX), index=list(pl.RISK_MIX).index(profile.risk),
                        horizontal=True, help=RISK_HELP)
        growth = st.slider("연봉 상승률 (%, 가정)", 0.0, 10.0, round(profile.salary_growth * 100, 1), 0.5)
        st.markdown("**🌳 은퇴·가족 계획**")
        new_life = life_inputs(memory["life"], age_now, key="info")
        if st.form_submit_button("정보 저장하기", type="primary"):
            p = memory["profile"]
            if int(age_in) != age_now:  # 나이를 직접 고치면 그 나이부터 다시 센다
                p["age"], p["months_passed"] = int(age_in), 0
            p.update(name=name.strip() or "나", job=job, income=income, fixed=fixed, spending=spending,
                     risk=risk, salary_growth=growth / 100)
            memory["life"] = {**memory["life"], **new_life}   # 연금 설정 등 이 화면에 없는 항목은 그대로 둔다
            remember()
            st.session_state.flash = ["내 정보를 저장했어!"]
            back_home()

    st.stop()

# ---------------- 계산: 소비 내역, 평생 로드맵, 노후 ----------------
# 소비 내역: 내 소비 내역 파일(data/my_spending.csv)이 있으면 그걸, 없으면 예시 데이터
try:
    spending_path = mem.SPENDING_PATH if os.path.exists(mem.SPENDING_PATH) else SAMPLE_CSV
    habit_rows = hb.load_rows(spending_path)      # 소비 습관 리포트용 (날짜·시간까지)
    if os.path.exists(mem.SPENDING_PATH):
        tx = pl.load_transactions(mem.SPENDING_PATH)
        tx_source = "내 소비 내역 (data/my_spending.csv)"
    else:
        tx = pl.load_transactions(SAMPLE_CSV)
        tx_source = "예시 데이터 (가상의 사회초년생 9~10월)"
except Exception as e:
    st.error(f"소비 내역 파일을 읽지 못했어요. ({e})")
    tx, tx_source, habit_rows = {}, "읽기 실패", []
months = list(tx)
latest = tx[months[-1]] if months else {}

life_rows, checks = pl.simulate_life(profile, goals, life)
summary = pl.life_summary(life_rows)
need = pl.retirement_need(profile, life)

# AI 조언에 줄 '사실 목록' — 숫자는 모두 위에서 앱이 계산한 값
held_count = sum(1 for d in memory["decisions"] if d["choice"] == "hold")
facts = adv.build_facts(profile, plan, life, done, summary, checks, need, tx,
                        {}, held_count, memory.get("advice"), holdings)

# 소비 습관 리포트에 줄 통계와 절약 후보 (숫자는 모두 앱이 계산)
habit_stats = hb.analyze(habit_rows)
if habit_stats:
    habit_cands = hb.savings_candidates(habit_stats, plan.items, profile.risk)
    habit_facts = hb.build_facts(habit_stats, habit_cands)
else:
    habit_cands, habit_facts = [], ""


def new_advice(topic):
    """동물 친구에게 새 조언을 받아 기억에 저장한다. (지난 조언은 기록으로 옮김)"""
    with st.spinner(f"{ch.josa(buddy, '이가')} 내 상황을 읽고 조언을 쓰는 중..."):
        record = adv.make_advice(facts, topic, (profile, plan, life, summary, checks, tx), buddy, animal)
    if memory.get("advice"):
        memory["advice_history"] = (memory["advice_history"] + [memory["advice"]])[-10:]
    memory["advice"] = record
    remember()


# 처음 메인 화면에 들어오면 첫 조언을 자동으로 받아둔다
if memory.get("advice") is None:
    new_advice(list(adv.TOPICS)[0])
    st.rerun()

# 지난 행동의 알림 (가입 완료, 저장, 실천 체크 등)
for note in st.session_state.pop("flash", []):
    st.toast(note, icon="🌱")
if st.session_state.pop("balloons", False):
    st.balloons()


# ===============================================================
# 동물 친구의 AI 맞춤 조언 카드 (홈 화면의 주인공)
# ===============================================================
GROUP_COLORS = {"안전": ui.GREEN, "청약": "#3BC9DB", "투자": ui.BLUE, "연금": ui.AMBER}


def render_holdings():
    """홈: 지금 어떤 상품에 얼마가 들어 있는지 (내 포트폴리오) + 수정하기"""
    total = sum(float(h.get("금액") or 0) for h in holdings)
    with st.container(key="card-holdings"):
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
                    f"<h3 style='margin:0'>💼 내 포트폴리오</h3>"
                    f"<div style='font-size:1.3rem;font-weight:800'>{ch.fmt(total)}</div></div>"
                    f"<div class='small'>지금 가입한 상품과 금액 · 용도별로 비상금·목표·노후 자금에 자동으로 반영돼요</div>",
                    unsafe_allow_html=True)
        if not holdings:
            st.info("아직 등록한 상품이 없어요. 아래 '✏️ 내 포트폴리오 수정'에서 가입한 상품을 넣어줘!")
        else:
            # 같은 상품은 하나로 합쳐서 보여준다 (용도별 금액은 작은 글씨로)
            merged = {}
            for h in holdings:
                m = merged.setdefault(h["상품"], {"금액": 0.0, "용도": {}})
                m["금액"] += float(h["금액"] or 0)
                m["용도"][h["용도"]] = m["용도"].get(h["용도"], 0) + float(h["금액"] or 0)
            rows = sorted(merged.items(), key=lambda kv: -kv[1]["금액"])
            colors = [GROUP_COLORS.get(pl.HOLDING_TYPES.get(name, "안전"), ui.MUTED) for name, _ in rows]
            left, right = st.columns([1, 1.5])
            with left:
                hdf = pd.DataFrame({"상품": [name for name, _ in rows], "금액": [m["금액"] for _, m in rows]})
                donut = alt.Chart(hdf).mark_arc(innerRadius=58, cornerRadius=4).encode(
                    theta="금액:Q", color=alt.Color("상품:N", scale=alt.Scale(domain=hdf["상품"].tolist(), range=colors),
                                                  legend=None), tooltip=["상품", "금액"]).properties(height=220)
                ui.chart(donut)
            with right:
                ui.alloc_rows([(colors[i], name,
                                pl.HOLDING_TYPES.get(name, "안전") + " · " + ", ".join(
                                    f"{u} {ch.fmt(v)}" if len(m["용도"]) > 1 else u for u, v in m["용도"].items()),
                                ch.fmt(m["금액"]), f"{round(m['금액'] / total * 100)}%" if total else "")
                               for i, (name, m) in enumerate(rows)])
            # 묶음별 비중 + 내 성향 기준과 비교
            groups = pl.holdings_by_group(holdings)
            st.markdown(" ".join(ui.chip(f"{g} {round(groups.get(g, 0) / total * 100)}% · {ch.fmt(groups.get(g, 0))}",
                                         GROUP_COLORS[g]) for g in GROUP_COLORS if groups.get(g)), unsafe_allow_html=True)
            invest_now = round(groups.get("투자", 0) / total * 100) if total else 0
            invest_rec = round(pl.RISK_MIX[profile.risk][1] * 100)
            if abs(invest_now - invest_rec) <= 10:
                ui.tip(f"투자 비중 {invest_now}% — {profile.risk} 기준({invest_rec}% 안팎)에 잘 맞아요.", ui.GREEN)
            elif invest_now > invest_rec:
                ui.tip(f"투자 비중 {invest_now}% — {profile.risk} 기준({invest_rec}% 안팎)보다 높아요. "
                       "원금 손실이 걱정되면 예적금 쪽을 조금 늘려봐.", ui.AMBER)
            else:
                ui.tip(f"투자 비중 {invest_now}% — {profile.risk} 기준({invest_rec}% 안팎)보다 낮아요. "
                       "기한이 긴 돈은 조금 투자해도 괜찮아.", ui.BLUE)
        if profile.real_estate:
            st.caption(f"🏠 부동산 {ch.fmt(profile.real_estate)}은 포트폴리오와 따로 총자산에 들어가요.")

        with st.expander("✏️ 내 포트폴리오 수정"):
            uses = [pl.EMERGENCY_USE] + [g.name for g in active] + [pl.FREE_USE]
            hdf = pd.DataFrame(holdings, columns=["상품", "금액", "용도"])
            with st.form("edit_holdings"):
                st.caption("줄을 눌러 고치고, 맨 아래 줄에서 추가, 줄을 선택해 삭제해요. 금액 단위: 만 원 · "
                           "'용도'를 목표로 정하면 그 목표의 모은 돈이 돼요.")
                edited = st.data_editor(hdf, num_rows="dynamic", hide_index=True, width="stretch", key="holdings_editor",
                                        column_config={
                                            "상품": st.column_config.SelectboxColumn("상품", options=list(pl.HOLDING_TYPES),
                                                                                   required=True),
                                            "금액": st.column_config.NumberColumn("금액 (만 원)", min_value=0, step=1),
                                            "용도": st.column_config.SelectboxColumn("용도", options=uses, required=True),
                                        })
                if st.form_submit_button("저장하기", type="primary"):
                    new = []
                    for _, r in edited.iterrows():
                        if pd.isna(r["상품"]) or pd.isna(r["금액"]) or float(r["금액"]) <= 0:
                            continue
                        new.append({"상품": r["상품"], "금액": float(r["금액"]),
                                    "용도": r["용도"] if r["용도"] in uses else pl.FREE_USE})
                    memory["holdings"] = new
                    remember()
                    st.session_state.flash = ["포트폴리오를 저장했어! 목표 진행률도 다시 계산했어."]
                    st.rerun()


def render_advice(record):
    d = record["data"]
    with st.container(key="card-ai"):
        mode_chip = ui.chip("✨ AI가 직접 작성", ui.BLUE) if record["mode"] == "AI" else ui.chip("기본 모드", ui.MUTED)
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<h3 style='margin:0'>{BUDDY_ICON} {buddy}의 AI 맞춤 조언</h3>{mode_chip}</div>"
                    f"<div class='small'>주제: {record['topic']} · {record['created']}</div>",
                    unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:1.35rem;font-weight:800;margin:14px 0 6px;letter-spacing:-0.02em'>"
                    f"💬 {ui.esc(d['summary'])}</div>", unsafe_allow_html=True)
        if d["good"]:
            ui.tip("<b>👍 잘하고 있는 점</b><br>" + "<br>".join(f"· {g}" for g in d["good"]), ui.GREEN)

        st.markdown(f"**✅ 이번 달 실천 3가지** <span class='small'>— 하고 나면 체크! 다음 조언 때 {ch.josa(buddy, '이가')} 기억해</span>",
                    unsafe_allow_html=True)
        rewarded = record.setdefault("rewarded", [False] * len(d["actions"]))
        for i, a in enumerate(d["actions"]):
            checked = st.checkbox(f"**{a['title']}**", value=record["done"][i], key=f"adv_{record['created']}_{i}")
            st.caption(ui.esc(a["detail"]))
            if checked != record["done"][i]:
                record["done"][i] = checked
                if checked and not rewarded[i]:   # 배지는 항목마다 한 번만
                    rewarded[i] = True
                    memory["points"] += ch.POINTS["advice_done"]
                    st.session_state.flash = ["실천 완료! 🏅 실천 배지 +1"]
                remember()
                st.rerun()

        if d["future"]:
            ui.tip(f"<b>🌳 평생 관점</b><br>{d['future']}", ui.BLUE)
        if d["cheer"]:
            say(d["cheer"])

        # AI가 쓴 숫자가 앱 계산값과 맞는지 (환각 방지)
        if record["mode"] == "AI":
            if record["unknown"]:
                st.warning(f"⚠️ 앱 계산에 없는 숫자가 있어요: {', '.join(record['unknown'])} — 이 부분은 한 번 더 확인해줘.")
            elif record["checked"]:
                st.caption(f"✅ 숫자 검증 통과: AI가 쓴 숫자 {record['checked']}개가 모두 앱 계산과 일치해요.")
        else:
            st.caption("지금은 미리 써둔 문장으로 만든 기본 조언이에요. API 키를 설정하면 AI가 내 상황을 읽고 직접 써줘요.")
            if record.get("note"):
                st.caption(f"({record['note']})")

        if record["signature"] != adv.signature(facts):
            st.info("지난 조언 이후로 내 정보가 바뀌었어. 새 조언을 받아볼래?")
        c1, c2 = st.columns([2, 1])
        topics = list(adv.TOPICS)
        topic = c1.selectbox("어떤 조언이 필요해?", topics, key="adv_topic", label_visibility="collapsed",
                             index=topics.index(record["topic"]) if record["topic"] in topics else 0)
        if c2.button("🔄 새 조언 받기", type="primary", width="stretch"):
            new_advice(topic)
            st.rerun()


# ===============================================================
# 탭 (5개)
# ===============================================================
tab_home, tab_spend, tab_month, tab_life, tab_chat = st.tabs(
    ["🏠 홈", "🧾 소비", "💰 이번 달 플랜", "🗺️ 평생 플랜", "💬 AI 재무설계사와 상담하기"])

# ---------------- 🏠 홈 ----------------
with tab_home:
    if wealth["next_need"] is not None:
        progress_text = f"다음 단계 {ui.LEVEL_EMOJI[wealth['level'] + 1]} {wealth['next_name']}까지 {ch.fmt(wealth['next_need'])}"
    else:
        progress_text = "최고 단계에 도달했어요 👑"
    chips = (ui.chip(f"{BUDDY_ICON} {ch.josa(buddy, '과와')} 함께", ui.BLUE)
             + ui.chip(f"{ui.LEVEL_EMOJI[wealth['level']]} {wealth['name']}", ui.GREEN)
             + ui.chip(ch.life_stage(age_now)[0], ui.BLUE)
             + ui.chip(f"🏅 실천 배지 {badges}개", ui.AMBER))
    ui.hero(look, age_now, wealth["level"], f"안녕, {profile.name}! 👋",
            f"{age_now}세 · {profile.job} · {profile.risk}", chips,
            ch.fmt(assets), wealth["progress"], progress_text)

    render_holdings()
    render_advice(memory["advice"])

# ---------------- 💰 이번 달 플랜: 목표별 저축 + 목표 추가·관리 ----------------
with tab_month:
    ui.section("💰 이번 달, 어디에 얼마씩 넣을까?", "비상금 → 기한이 가까운 목표 → 남는 돈은 노후 자금 순서로 나눠요")
    c1, c2, c3 = st.columns(3)
    c1.metric("순수익 (월급 − 고정비)", ch.fmt(plan.net))
    c2.metric("생활비", ch.fmt(profile.spending))
    c3.metric("저축 가능액", ch.fmt(max(plan.surplus, 0)))

    if plan.surplus > 0:
        palette = [ui.MUTED, ui.BLUE, ui.GREEN, ui.AMBER, "#9775FA", "#FF8787", "#3BC9DB", "#F783AC"]
        rows = [("🛟 비상금", "파킹통장", plan.emergency, plan.emergency, 0)]
        rows += [(f"🎯 {it.goal.name}", it.product, it.alloc, it.deposit, it.invest) for it in plan.items]
        rows.append(("🌳 노후·여유 자금", "연금저축·IRP 같은 노후 상품", plan.extra, plan.extra_deposit, plan.extra_invest))
        colors = [palette[i % len(palette)] for i in range(len(rows))]

        with st.container(key="card-alloc"):
            left, right = st.columns([1, 1.4])
            with left:   # 도넛 그래프
                donut_df = pd.DataFrame({"어디에": [r[0] for r in rows], "금액": [r[2] for r in rows]})
                donut = alt.Chart(donut_df).mark_arc(innerRadius=62, cornerRadius=4).encode(
                    theta="금액:Q",
                    color=alt.Color("어디에:N", scale=alt.Scale(domain=donut_df["어디에"].tolist(), range=colors),
                                    legend=None),
                    tooltip=["어디에", "금액"]).properties(height=230)
                ui.chart(donut)
            with right:
                ui.alloc_rows([(colors[i], r[0], r[1], ch.fmt(r[2]),
                                f"예적금 {ch.fmt(r[3])} · 투자 {ch.fmt(r[4])}") for i, r in enumerate(rows)])
    else:
        st.warning("지금은 저축할 수 있는 돈이 없어요. 사이드바에서 생활비를 다시 확인해봐.")

    for m in ch.plan_messages(plan):
        say(m)
    optional = {k: v for k, v in latest.items() if k not in ESSENTIAL}
    if optional and nearest:   # 가장 많이 쓴 비필수 카테고리로 절약 팁
        top_cat = max(optional, key=optional.get)
        tip = ch.cut_tip_message(top_cat, max(1, round(optional[top_cat] / 10000 * 0.3)), nearest.alloc, nearest.goal)
        if tip:
            say(tip)
    st.caption("수익률은 가정값이에요 (예적금 연 3%, 투자 연 5%). 특정 종목·금융사 상품이 아니라 상품 유형과 비중만 제안해요. "
               "실제 예적금 금리는 금융감독원 '금융상품 한눈에'에서 비교할 수 있어요.")

    ui.section("➕ 목표 바로 추가", "새 목표를 넣으면 이번 달 배분이 바로 다시 계산돼요")
    with st.form("quick_goal", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        q_name = c1.text_input("목표 이름", placeholder="예: 노트북")
        q_target = c2.number_input("목표 금액 (만 원)", 1, 1000000, 100)
        q_months = c3.number_input("기한 (개월)", 1, 480, 6)
        q_saved = c4.number_input("모은 돈 (만 원)", 0, 1000000, 0)
        if st.form_submit_button("목표 추가하기"):
            if not q_name.strip():
                st.error("목표 이름을 적어줘!")
            else:
                add_goal(q_name.strip(), q_target, q_months, q_saved)
                remember()
                extra_note = " 기한이 1년 넘어서 평생 플랜에도 페이지가 생겼어!" if q_months > pl.LONG_TERM_MONTHS else ""
                st.session_state.flash = [f"'{q_name.strip()}' 목표를 추가했어!{extra_note}"]
                st.rerun()

    shorts = [it for it in plan.items if it.goal.months <= pl.LONG_TERM_MONTHS]
    if shorts:
        with st.expander(f"🎯 짧은 목표 관리 ({len(shorts)}개) — 달성했거나 필요 없어진 목표 정리"):
            for i, it in enumerate(shorts):
                g = it.goal
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{g.name}** · {ch.fmt(g.saved)} / {ch.fmt(g.target)} · {ch.years_months(g.months)} 뒤")
                if c2.button("🎉 달성!", key=f"done_short_{i}", width="stretch"):
                    complete_goal(g.name)
                    remember()
                    st.session_state.flash = [ch.goal_done_message(g.name), f"🏅 실천 배지 +{ch.POINTS['short_goal_done']}"]
                    st.rerun()
                if c3.button("삭제", key=f"del_short_{i}", width="stretch"):
                    delete_goal(g.name)
                    remember()
                    st.session_state.flash = [f"'{g.name}' 목표를 지웠어. 모아둔 돈은 노후·여유 자금으로 옮겼어."]
                    st.rerun()
        st.caption("기한이 1년 넘는 목표는 '🗺️ 평생 플랜'의 목표 페이지에서 고칠 수 있어요.")

    ui.tip("🛍️ 사고 싶은 게 있으면 '💬 AI 재무설계사와 상담하기'에서 <b>'신발 12만 원 사도 돼?'</b>처럼 물어봐. "
           "목표가 며칠 늦어지는지 계산해줄게!", ui.BLUE)

# ---------------- 🗺️ 평생 플랜: 한눈에 보기 → 장기 목표별 페이지 → 노후 준비 → 장기 목표 설정 ----------------
long_items = [it for it in plan.items if it.goal.months > pl.LONG_TERM_MONTHS]   # 기한이 1년 넘는 목표
pension = pl.pension_plan(profile, life)                                         # 연금 3층 계산


def render_overview():
    """평생 플랜 첫 화면: 90세까지 그래프와 인생 이벤트 점검"""
    ui.section(f"🗺️ {profile.name}의 평생 플랜", f"{age_now}세부터 {pl.LIFE_END_AGE}세까지, 큰 목표와 노후를 한눈에")
    saving_rate = plan.total_saving / profile.income if profile.income else 0
    invest_rate = plan.total_invest / plan.total_saving if plan.total_saving else 0
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    last_row = life_rows[-1]
    c1.metric("90세 예상 순자산", ch.fmt(summary["final_net"]),
              help=f"금융자산 {ch.fmt(last_row['금융자산'])} + 부동산 {ch.fmt(last_row['부동산'])} "
                   f"+ 연금 {ch.fmt(last_row['연금 자산'])} − 대출 {ch.fmt(last_row['대출 잔액'])}")
    c2.metric("현금이 버티는 나이", "90세까지 OK" if summary["broke_age"] is None else f"{summary['broke_age']}세",
              help="예금·투자 같은 금융자산이 0 아래로 내려가는 나이 (집·연금 계좌는 빼고 계산)")
    c3.metric("월급 중 저축", f"{round(saving_rate * 100)}%")
    c4.metric("저축 중 투자", f"{round(invest_rate * 100)}%")

    df = pd.DataFrame(life_rows)
    with st.container(key="card-roadmap"):
        area = alt.Chart(df).mark_area(
            line={"color": ui.BLUE, "strokeWidth": 2.5},
            color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                               stops=[alt.GradientStop(color="#FFFFFF", offset=0),
                                      alt.GradientStop(color="#C9D4FF", offset=1)])).encode(
            x=alt.X("나이:Q", title="나이", scale=alt.Scale(zero=False)),
            y=alt.Y("금융자산:Q", title=None),
            tooltip=["나이", "금융자산", "부동산", "연금 자산", "대출 잔액", "순자산", "이벤트"])
        debt_line = alt.Chart(df[df["대출 잔액"] > 0]).mark_line(color=ui.RED, strokeWidth=2, strokeDash=[6, 4]).encode(
            x="나이:Q", y="대출 잔액:Q", tooltip=["나이", "대출 잔액"])
        events_df = df[df["이벤트"] != ""]
        points = alt.Chart(events_df).mark_point(size=110, filled=True, color=ui.AMBER).encode(
            x="나이:Q", y="금융자산:Q", tooltip=["나이", "금융자산", "이벤트"])
        big = {g.name for g in active if g.target >= 1000} | {"은퇴", "자녀 양육 시작"}
        label_df = events_df[events_df["이벤트"].apply(lambda e: any(n in big for n in e.split(", ")))]
        labels = alt.Chart(label_df).mark_text(dy=-15, fontSize=12, fontWeight="bold", color="#1E2532").encode(
            x="나이:Q", y="금융자산:Q", text="이벤트")
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[4, 4], color="#9CA3AF").encode(y="y:Q")
        ui.chart((area + zero + debt_line + points + labels).properties(height=320))
        loan_note = (f"빨간 점선은 남은 대출이에요 (집값의 {round(life.loan_ratio * 100)}% 대출, {life.loan_years}년 원리금균등 상환, "
                     f"연 {life.loan_rate * 100:.1f}% 가정). " if life.loan_on else "")
        st.caption("그래프 단위: 만 원. 파란 영역은 예금·투자 같은 금융자산이에요. " + loan_note +
                   "저축은 연봉 상승률만큼 늘고, 은퇴 후엔 국민연금·퇴직연금·개인연금을 받으며 은퇴 생활비를 쓴다고 가정했어요. "
                   "물가 상승과 집값 변화는 반영하지 않았어요.")
    for m in ch.roadmap_messages(summary, checks, life.retire_age):
        say(m)
    if checks:
        st.dataframe(pd.DataFrame([{
            "나이": f"{c['age']}세", "이벤트": c["name"],
            "필요한 현금": ch.fmt(c["cost"]) + (f" (집값 {ch.fmt(c['price'])} − 대출 {ch.fmt(c['loan'])})" if c["loan"] else ""),
            "그때 예상 자산": ch.fmt(c["before"]), "가능?": "✅ 가능" if c["ok"] else "⚠️ 부족"} for c in checks]),
            hide_index=True, width="stretch")
    st.caption("💡 위쪽 탭에서 장기 목표를 누르면 목표별 저축 계획과 AI 추천 포트폴리오를 볼 수 있어요. "
               "새 장기 목표는 '➕ 장기 목표 설정' 탭에서 만들어요.")


# ---- 목표 페이지 공통: AI 추천 포트폴리오 + 먼저 알아두면 좋은 것 ----
def new_portfolio(key, gtype, base, invest_ratio, months, facts_g):
    with st.spinner(f"{ch.josa(buddy, '이가')} 내 상황에 맞는 포트폴리오를 짜는 중... (AI 서버가 붐비면 30초쯤 걸릴 수 있어)"):
        memory["portfolios"][key] = pf.make_portfolio(gtype, base, invest_ratio, months, age_now, facts_g, buddy, animal)
    remember()


def render_portfolio(idx, key, gtype, base, invest_ratio, months, extra_lines=(), base_note=None):
    """목표 하나의 AI 추천 포트폴리오 카드 (나에게 맞는 제도·상품 유형 + 매달 금액)"""
    facts_g = pf.goal_facts(gtype, key, base, invest_ratio, months, profile, extra_lines)
    record = memory["portfolios"].get(key)
    ui.section("🤖 AI 추천 포트폴리오", "나에게 맞는 제도·상품 유형에 매달 얼마씩 나눌지 AI가 내 상황을 보고 짜줘요")
    with st.container(key=f"card-ai-pf-{idx}"):
        if base_note:
            st.caption(base_note)
        if record is None:
            st.markdown(f"매달 **{ch.fmt(base)}**을 어디에 나눠 담으면 좋을지 {ch.josa(buddy, '이가')} 분석해줄게.")
            if st.button("🤖 포트폴리오 분석 받기", type="primary", key=f"pf_new_{idx}"):
                new_portfolio(key, gtype, base, invest_ratio, months, facts_g)
                st.rerun()
            return
        d = record["data"]
        mode_chip = ui.chip("✨ AI가 직접 분석", ui.BLUE) if record["mode"] == "AI" else ui.chip("기본 모드", ui.MUTED)
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<div style='font-size:1.15rem;font-weight:800'>💬 {ui.esc(d['summary'])}</div>{mode_chip}</div>"
                    f"<div class='small'>매달 {ch.fmt(record['base'])} 기준 · {record['created']}</div>",
                    unsafe_allow_html=True)
        palette = [ui.BLUE, ui.GREEN, ui.AMBER, "#9775FA", "#FF8787"]
        colors = [palette[i % len(palette)] for i in range(len(d["items"]))]
        left, right = st.columns([1, 1.4])
        with left:
            pdf = pd.DataFrame({"상품": [it["name"] for it in d["items"]], "금액": [it["amount"] for it in d["items"]]})
            donut = alt.Chart(pdf).mark_arc(innerRadius=55, cornerRadius=4).encode(
                theta="금액:Q", color=alt.Color("상품:N", scale=alt.Scale(domain=pdf["상품"].tolist(), range=colors),
                                              legend=None), tooltip=["상품", "금액"]).properties(height=200)
            ui.chart(donut)
        with right:
            ui.alloc_rows([(colors[i], it["name"], pf.PRODUCTS.get(it["name"], ("",))[0], ch.fmt(it["amount"]),
                            f"{round(it['amount'] / max(record['base'], 1) * 100)}%") for i, it in enumerate(d["items"])])
        for it in d["items"]:
            caution = f"<div class='rec-row' style='color:#B7791F'>⚠️ {ui.esc(it['caution'])}</div>" if it["caution"] else ""
            st.markdown(f"<div class='rec'><div class='rec-name'>{ui.esc(it['name'])} · 월 {ch.fmt(it['amount'])}</div>"
                        f"<div class='rec-row'>💡 {ui.esc(it['why'])}</div><div class='rec-row'>✅ {ui.esc(it['how'])}</div>"
                        f"{caution}</div>", unsafe_allow_html=True)
        if d["tip"]:
            say(d["tip"])

        # 앱이 확인한 것: 금액 합계·투자 비중·제도 한도 + 글 속 숫자 (AI 환각 방지)
        for w in record["warnings"]:
            st.warning("⚠️ " + w)
        if record["mode"] == "AI":
            if record["unknown"]:
                st.warning(f"⚠️ 앱 계산·제도 자료에 없는 숫자가 있어요: {', '.join(record['unknown'])} — 한 번 더 확인해줘.")
            elif not record["warnings"]:
                st.caption(f"✅ 검증 통과: 금액 합계·투자 비중·제도 한도를 지켰고, 글 속 숫자 {record['checked']}개도 "
                           "모두 앱 계산·제도 자료와 일치해요.")
        else:
            st.caption("지금은 규칙으로 짠 기본 포트폴리오예요. API 키를 설정하면 AI가 내 상황을 읽고 직접 짜줘요.")
            if record.get("note"):
                st.caption(f"({record['note']})")
        st.caption("특정 금융사 상품이 아니라 제도·상품 유형까지만 추천해요. 수익률은 가정값이고, 가입 전엔 조건을 꼭 확인해줘.")

        if gtype == "노후 준비":   # 연금 계좌 금액을 바로 평생 계산에 반영
            in_pension = sum(it["amount"] for it in d["items"] if pf.PRODUCTS.get(it["name"], ("",))[0] == "연금")
            if in_pension and in_pension != life.private_monthly:
                if st.button(f"✅ IRP·연금저축 월 {ch.fmt(in_pension)}을 내 노후 계획에 반영하기", key=f"pf_apply_{idx}"):
                    memory["life"]["private_monthly"] = in_pension
                    remember()
                    st.session_state.flash = ["반영했어! 노후 연금과 평생 그래프가 다시 계산됐어."]
                    st.rerun()
        c1, c2 = st.columns([2, 1])
        if record["signature"] != pf.signature(facts_g):
            c1.info("분석한 뒤로 내 정보가 바뀌었어. 다시 분석해볼래?")
        if c2.button("🔄 다시 분석하기", width="stretch", key=f"pf_re_{idx}"):
            new_portfolio(key, gtype, base, invest_ratio, months, facts_g)
            st.rerun()


def render_concepts(gtype):
    """이 목표와 관련된 제도·개념 쉬운 설명 (knowledge.py)"""
    topic = pl.GOAL_TYPES[gtype][1]
    info = kn.TOPICS[topic]
    ui.section("📚 먼저 알아두면 좋은 것", f"기준일 {kn.BASE_DATE} · 제도는 자주 바뀌니 가입 전에 공식 안내를 꼭 확인해줘")
    for c in info["concepts"]:
        with st.expander(f"{c['emoji']} **{c['name']}** — {ui.esc(c['one_line'])}"):
            st.markdown("\n".join(f"- {ui.esc(p)}" for p in c["points"]))
            ui.tip(f"👤 <b>이런 사람에게</b> · {c['for_whom']}", ui.GREEN)
            ui.tip(f"⚠️ <b>주의</b> · {c['caution']}", ui.AMBER)
    st.caption("공식 확인처: " + " · ".join(f"[{s}]({kn.SOURCES[s]})" for s in info["sources"]))


# ---- 장기 목표 페이지 (결혼 자금·내 집 마련·기타) ----
def render_goal_page(idx, it):
    g = it.goal
    gtype = pl.goal_type(g)
    icon = pl.GOAL_TYPES[gtype][0]
    sub = f"{ch.years_months(g.months)} 뒤 · {gtype}"
    if it.price:
        sub += f" · 집값 {ch.fmt(it.price)} 중 대출 빼고 내 돈(자기자금) {ch.fmt(g.target)}을 모아요"
    ui.section(f"{icon} {g.name}", sub)
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    c1.metric("모을 돈" if not it.price else "모을 자기자금", ch.fmt(g.target))
    c2.metric("지금 모은 돈", ch.fmt(g.saved), help=f"진행률 {round(min(g.saved / g.target, 1) * 100) if g.target else 100}%")
    c3.metric("이번 달 넣는 돈", ch.fmt(it.alloc))
    c4.metric("예상 달성", ch.years_months(it.expected_months) + " 뒤" if it.expected_months is not None else "지금 배분으론 어려움")
    if it.alloc < it.need:
        ui.tip(f"기한({ch.years_months(g.months)}) 안에 이루려면 매달 <b>{ch.fmt(it.need)}</b>이 필요해요. "
               f"지금은 앞 목표에 먼저 넣느라 {ch.fmt(it.need - it.alloc)} 모자라요.", ui.AMBER)

    # 기간에 따라 예적금·투자 비중을 바꿔가는 계획
    ui.section("📈 저축·투자 비중 계획", "목표가 가까워질수록 투자를 줄여서 모은 돈을 지켜요")
    base = it.alloc if it.alloc >= 5 else max(math.ceil(it.need), 1)
    with st.container(key=f"card-goalplan-{idx}"):
        phase_rows = []
        for ph in pl.glide_path(profile.risk, g.months):
            start = "지금" if ph["start"] == 0 else f"{ch.years_months(ph['start'])} 뒤"
            phase_rows.append({"시기": f"{start} ~ {ch.years_months(ph['end'])} 뒤",
                               "예적금": f"{round(ph['deposit'] * 100)}%", "투자": f"{round(ph['invest'] * 100)}%",
                               "매달 예적금": ch.fmt(base * ph["deposit"]), "매달 투자": ch.fmt(base * ph["invest"])})
        st.dataframe(pd.DataFrame(phase_rows), hide_index=True, width="stretch")
        balance = pl.project_balance(g.saved, base, g.months, profile.risk, g.months)
        proj = pd.DataFrame({"개월": range(1, len(balance) + 1), "예상 잔액": [round(b) for b in balance]})
        line = alt.Chart(proj).mark_line(color=ui.GREEN, strokeWidth=2.5).encode(
            x=alt.X("개월:Q"), y=alt.Y("예상 잔액:Q", title=None), tooltip=["개월", "예상 잔액"])
        target_rule = alt.Chart(pd.DataFrame({"y": [g.target]})).mark_rule(color=ui.AMBER, strokeDash=[6, 4]).encode(y="y:Q")
        ui.chart((line + target_rule).properties(height=200))
        st.caption(f"매달 {ch.fmt(base)}씩 넣을 때 · 초록 선: 예상 잔액 · 주황 점선: 목표 {ch.fmt(g.target)} · "
                   f"{ch.years_months(g.months)} 뒤 약 {ch.fmt(balance[-1])} (가정 수익률 기준)")
    say(ch.long_plan_message(it, profile.risk))

    # 집이면 대출 플랜
    extra = [f"[진행] 모은 돈 {ch.fmt(g.saved)}, 이번 달 배분 {ch.fmt(it.alloc)}, 기한 안에 필요한 월 {ch.fmt(it.need)}"]
    loan = next((c for c in checks if c["name"] == g.name and c["loan"]), None)
    if loan:
        ui.section("🏦 대출 플랜", f"{loan['age']}세 · 집값 {ch.fmt(loan['price'])} = 내 돈(자기자금) "
                                 f"{ch.fmt(loan['cost'])} + 대출 {ch.fmt(loan['loan'])}")
        with st.container(key=f"card-loan-{idx}"):
            k1, k2 = st.columns(2)
            k3, k4 = st.columns(2)
            k1.metric("대출 금액", ch.fmt(loan["loan"]))
            k2.metric("매달 갚을 돈", ch.fmt(loan["pay"]), help="원리금균등: 매달 같은 금액(원금 + 이자)을 갚아요.")
            k3.metric("다 갚는 나이", f"{loan['payoff_age']}세")
            k4.metric("총 이자 (가정 금리 기준)", ch.fmt(loan["interest"]))
            color = ui.GREEN if loan["pay_ratio"] <= pl.DSR_LIMIT else ui.AMBER
            ui.tip(f"그때 예상 월급(세후, 연봉 상승률 반영)의 <b>{round(loan['pay_ratio'] * 100)}%</b>를 대출 갚는 데 써요. "
                   f"은행은 보통 1년 원리금이 연 소득의 {round(pl.DSR_LIMIT * 100)}%를 넘지 않게 빌려줘요(DSR 규제, 세전 소득 기준). "
                   "이 비율은 참고용이에요.", color)
        for m in ch.loan_messages(loan, life.retire_age):
            say(m)
        st.caption("대출 비율·기간·금리는 '➕ 장기 목표 설정' 탭이나 사이드바 '✏️ 내 정보 수정'에서 바꿀 수 있어요.")
        extra.append(f"[대출] 집값 {ch.fmt(loan['price'])} 중 {ch.fmt(loan['loan'])} 대출, 매달 {ch.fmt(loan['pay'])} 상환, "
                     f"{loan['payoff_age']}세에 다 갚음, 그때 세후 월급의 {round(loan['pay_ratio'] * 100)}%")

    with st.expander("⚙️ 이 목표 수정하기 (금액·기한·달성)"):
        with st.form(f"edit_goal_{idx}"):
            c1, c2 = st.columns(2)
            new_target = c1.number_input("집값 (만 원)" if it.price else "목표 금액 (만 원)", 1, 10000000,
                                         int(it.price or g.target), step=100)
            new_months = c2.number_input("남은 기한 (개월)", 1, 480, int(g.months))
            st.caption("모은 돈은 홈의 '💼 내 포트폴리오'에서 용도를 이 목표로 정하면 반영돼요.")
            b1, b2 = st.columns(2)
            save_it = b1.form_submit_button("저장하기", type="primary", width="stretch")
            done_it = b2.form_submit_button("🎉 목표 달성!", width="stretch")
        if save_it:
            for x in memory["goals"]:
                if x["name"] == g.name:
                    x["target"], x["months"] = float(new_target), int(new_months)
            remember()
            st.session_state.flash = [f"'{g.name}' 목표를 고쳤어!"]
            st.rerun()
        if done_it:
            complete_goal(g.name)
            remember()
            st.session_state.flash = [ch.goal_done_message(g.name)]
            st.rerun()

    note = None if base == it.alloc else (f"지금은 앞 목표에 먼저 넣느라 이번 달 배분이 {ch.fmt(it.alloc)}이라서, "
                                          f"기한 안에 이루는 데 필요한 월 {ch.fmt(base)} 기준으로 짰어요.")
    render_portfolio(idx, g.name, gtype, base, it.invest_ratio, g.months, extra, note)
    render_concepts(gtype)


# ---- 노후 준비 페이지 (연금 3층) ----
def render_retire_page(idx):
    ui.section("🌳 노후 준비", f"은퇴 {life.retire_age}세 · 은퇴 후 생활비 월 {ch.fmt(life.retire_spending)} · "
                              f"{pl.LIFE_END_AGE}세까지")
    national, retire_m, private_m = life.pension, pension["retire_monthly"], pension["private_monthly_out"]
    income_65 = national + retire_m + private_m
    gap = life.retire_spending - income_65

    # 연금 3층: 65세 이후 한 달에 들어오는 돈 vs 생활비
    ui.section("🏛️ 연금 3층으로 받는 돈", "65세부터 한 달에 들어오는 돈 (가정값으로 계산한 예상치)")
    with st.container(key="card-pension"):
        bars = pd.DataFrame([
            {"구분": "필요한 생활비", "항목": "생활비", "금액": life.retire_spending, "순서": 0},
            {"구분": "들어오는 연금", "항목": "1층 국민연금", "금액": national, "순서": 1},
            {"구분": "들어오는 연금", "항목": "2층 퇴직연금", "금액": round(retire_m), "순서": 2},
            {"구분": "들어오는 연금", "항목": "3층 개인연금", "금액": round(private_m), "순서": 3},
        ])
        bar = alt.Chart(bars).mark_bar(cornerRadius=4, height=34).encode(
            y=alt.Y("구분:N", title=None, sort=["필요한 생활비", "들어오는 연금"]),
            x=alt.X("금액:Q", title="만 원 / 월", stack="zero"),
            color=alt.Color("항목:N", scale=alt.Scale(
                domain=["생활비", "1층 국민연금", "2층 퇴직연금", "3층 개인연금"],
                range=["#CBD2E0", ui.BLUE, ui.GREEN, ui.AMBER]), legend=alt.Legend(orient="top", title=None)),
            order="순서:Q", tooltip=["항목", "금액"])
        ui.chart(bar.properties(height=150))
        p1, p2, p3 = st.columns(3)
        p1.metric("1층 국민연금", ch.fmt(national), help=f"{pl.PENSION_AGE}세부터 · 입력한 예상 수령액")
        p2.metric(f"2층 퇴직연금 ({pension['retire_type'] or '없음'})", ch.fmt(retire_m),
                  help=f"은퇴 때 약 {ch.fmt(pension['retire_balance'])} 모임 → {pension['pay_years']}년 동안 나눠 받음")
        p3.metric("3층 개인연금", ch.fmt(private_m),
                  help=f"IRP·연금저축에 매달 {ch.fmt(life.private_monthly)} → 은퇴 때 약 {ch.fmt(pension['private_balance'])}")
        if gap > 0:
            ui.tip(f"연금을 다 합쳐도 한 달 <b>{ch.fmt(gap)}</b>이 모자라요. 이 부분은 모아둔 노후 자금에서 꺼내 써야 해요.", ui.AMBER)
        else:
            ui.tip(f"연금만으로 생활비를 다 채우고 한 달 {ch.fmt(-gap)}이 남아요! 🎉", ui.GREEN)
        if pension["retire_type"]:
            other = "DB" if pension["retire_type"] == "DC" else "DC"
            other_m = pension["db_monthly"] if other == "DB" else pension["dc_monthly"]
            st.caption(f"참고: 퇴직연금이 {other}형이라면 월 {ch.fmt(other_m)} (DB형은 은퇴 직전 월급 × 일한 햇수, "
                       "DC형은 해마다 쌓인 돈을 성향에 맞게 굴린 결과)")
        if life.private_monthly:
            st.caption(f"💸 IRP·연금저축에 매달 {ch.fmt(life.private_monthly)} 넣으면 연말정산에서 해마다 약 "
                       f"{ch.fmt(pension['tax_refund'])}을 돌려받아요 (세액공제 {pension['tax_rate'] * 100:.1f}% 가정).")
    for m in ch.pension_messages(pension, life, gap):
        say(m)

    with st.expander("⚙️ 노후·연금 설정 바꾸기"):
        with st.form("pension_form"):
            c1, c2, c3 = st.columns(3)
            ra = c1.number_input("은퇴 나이", min(age_now + 1, 80), 80, life.retire_age)
            rs = c2.number_input("은퇴 후 한 달 생활비 (만 원)", 0, 10000, int(life.retire_spending), step=10)
            npn = c3.number_input("국민연금 예상 월 수령액 (만 원)", 0, 1000, int(life.pension), step=10,
                                  help="국민연금공단 '내 연금 알아보기'에서 확인할 수 있어요.")
            c1, c2, c3 = st.columns(3)
            ron = c1.checkbox("회사 퇴직연금 있음", life.retire_pension_on)
            rtype = c2.radio("퇴직연금 유형", ["DC", "DB"], index=0 if life.retire_pension_type == "DC" else 1,
                             horizontal=True, help="DB: 회사가 굴리고 은퇴 직전 월급 기준 / DC: 회사가 넣어준 돈을 내가 굴림")
            pm = c3.number_input("IRP·연금저축에 매달 (만 원)", 0, 1000, int(life.private_monthly), step=5)
            if st.form_submit_button("저장하기", type="primary"):
                memory["life"].update({"retire_age": int(ra), "retire_spending": rs, "pension": npn,
                                       "retire_pension_on": ron, "retire_pension_type": rtype, "private_monthly": pm})
                remember()
                st.session_state.flash = ["노후 설정을 저장했어!"]
                st.rerun()

    # 노후 포트폴리오: 연금만으로 모자란 돈을 채우려면 매달 얼마
    need0 = pl.retirement_need(profile, replace(life, private_monthly=0))
    base = max(round(plan.extra), math.ceil(need0["monthly"]), 5)
    _, retire_inv = pl.age_mix(profile.risk, age_now)
    extra = [f"[노후] 은퇴 {life.retire_age}세, 은퇴 후 생활비 월 {ch.fmt(life.retire_spending)}, 국민연금 월 {ch.fmt(national)}"
             f"({pl.PENSION_AGE}세부터), 퇴직연금 {pension['retire_type'] or '없음'} 월 {ch.fmt(retire_m)}, "
             f"개인연금 지금 월 {ch.fmt(life.private_monthly)} 납입 → 월 {ch.fmt(private_m)} 수령",
             f"[노후 자금] 이번 달 노후 배분 {ch.fmt(plan.extra)}, 연금 빼고 은퇴 전까지 매달 더 모아야 할 돈 {ch.fmt(need0['monthly'])}",
             f"[세액공제] IRP+연금저축 연 {pl.PENSION_TAX_LIMIT}만 원까지, 공제율 {pension['tax_rate'] * 100:.1f}%"]
    note = None if base == round(plan.extra) else (f"지금 이번 달 노후 배분은 {ch.fmt(plan.extra)}이라서, 연금으로 모자란 돈을 "
                                                   f"채우는 데 필요한 월 {ch.fmt(base)} 기준으로 짰어요.")
    render_portfolio(idx, "노후 준비", "노후 준비", base, retire_inv, None, extra, note)
    render_concepts("노후 준비")


# ---- ➕ 장기 목표 설정 ----
def render_goal_setup():
    ui.section("➕ 장기 목표 설정", "기한이 1년 넘는 목표를 만들면 평생 플랜에 그 목표만의 페이지가 생겨요")
    kinds = [t for t in pl.GOAL_TYPES if t != "노후 준비"]
    kind = st.pills("어떤 목표야?", kinds, selection_mode="single", default=kinds[0], key="new_goal_kind",
                    format_func=lambda t: f"{pl.GOAL_TYPES[t][0]} {t}") or kinds[0]
    with st.form("new_long_goal", clear_on_submit=True):
        c1, c2 = st.columns(2)
        name = c1.text_input("목표 이름", kind if kind != "기타 장기 목표" else "", placeholder="예: 내 차 마련")
        years = c2.number_input("몇 년 뒤?", 2, 40, 5)
        c1, c2 = st.columns(2)
        target = c1.number_input("집값 (만 원)" if kind == "내 집 마련" else "목표 금액 (만 원)", 100, 1000000,
                                 30000 if kind == "내 집 마련" else 3000, step=100)
        saved = c2.number_input("지금 모은 돈 (만 원)", 0, 1000000, 0, step=10)
        if kind == "내 집 마련":
            st.markdown("**🏦 대출 계획** (가정값)")
            c1, c2, c3, c4 = st.columns(4)
            loan_on = c1.checkbox("대출 받기", life.loan_on)
            ratio = c2.number_input("대출 비율 (%)", 0, 80, round(life.loan_ratio * 100), step=5,
                                    help="실제 한도는 지역·규제(LTV)·소득(DSR)에 따라 달라요.")
            ly = c3.number_input("상환 기간 (년)", 5, 50, life.loan_years, step=5)
            lr = c4.number_input("금리 (연 %)", 0.0, 15.0, round(life.loan_rate * 100, 1), step=0.1)
        if st.form_submit_button("목표 만들기", type="primary"):
            if not name.strip():
                st.error("목표 이름을 적어줘!")
            else:
                add_goal(name.strip(), target, int(years) * 12, saved, kind == "내 집 마련", kind)
                if kind == "내 집 마련":
                    memory["life"].update({"loan_on": loan_on, "loan_ratio": ratio / 100,
                                           "loan_years": int(ly), "loan_rate": round(lr / 100, 4)})
                remember()
                st.session_state.flash = [f"{pl.GOAL_TYPES[kind][0]} '{name.strip()}' 페이지가 생겼어! 위쪽 탭에서 눌러봐."]
                st.rerun()
    st.caption("🌳 노후 준비 페이지는 항상 있어요. 은퇴 나이·연금 설정은 그 페이지에서 바꿀 수 있어요.")

    if long_items:
        st.markdown("**지금 장기 목표**")
        for i, it in enumerate(long_items):
            g = it.goal
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"{pl.GOAL_TYPES[pl.goal_type(g)][0]} **{g.name}** · {ch.fmt(it.price or g.target)} · "
                        f"{ch.years_months(g.months)} 뒤")
            if c2.button("삭제", key=f"del_goal_{i}", width="stretch"):
                delete_goal(g.name)
                remember()
                st.session_state.flash = [f"'{g.name}' 목표를 지웠어. 모아둔 돈은 노후·여유 자금으로 옮겼어."]
                st.rerun()


with tab_life:
    life_tabs = st.tabs(["🗺️ 한눈에 보기"]
                        + [f"{pl.GOAL_TYPES[pl.goal_type(it.goal)][0]} {it.goal.name}" for it in long_items]
                        + ["🌳 노후 준비", "➕ 장기 목표 설정"])
    with life_tabs[0]:
        render_overview()
    for i, it in enumerate(long_items):
        with life_tabs[i + 1]:
            render_goal_page(i, it)
    with life_tabs[len(long_items) + 1]:
        render_retire_page(len(long_items))
    with life_tabs[-1]:
        render_goal_setup()


# ---------------- 🧾 소비: 습관 리포트 + 월간 점검 ----------------
def new_habit_report():
    """동물 친구에게 소비 습관 리포트를 새로 받아 기억에 저장한다."""
    with st.spinner(f"{ch.josa(buddy, '이가')} 결제 시간과 요일을 살펴보는 중..."):
        memory["habit_report"] = hb.make_report(habit_stats, habit_cands, habit_facts, buddy, animal)
    remember()


def render_habits():
    """소비 습관 리포트: 요일×시간대 그래프 → AI 리포트(별명·패턴·절약 효과)"""
    if not habit_stats:
        st.info("결제 '시간'이 있는 소비 내역이 10건 이상 있어야 습관을 분석할 수 있어요.")
        return
    if not memory.get("habit_report"):     # 처음 한 번은 자동으로 만들어준다
        new_habit_report()
    record = memory["habit_report"]
    d = record["data"]

    # 요일 × 시간대 지출 그래프 (색이 진할수록 많이 씀)
    ui.section("🗓️ 언제 돈을 쓸까?", f"{habit_stats['first']} ~ {habit_stats['last']} · "
                                     f"시간이 있는 결제 {habit_stats['timed']}건 · 색이 진할수록 많이 쓴 시간")
    slot_names = [f"{n} {a}~{b}시" for n, a, b in hb.SLOTS]
    heat = pd.DataFrame([{"요일": day, "시간대": f"{n} {a}~{b}시",
                          "금액": round(habit_stats["grid"].get((day, n), 0) / 10000, 1)}
                         for day in hb.DAYS for n, a, b in hb.SLOTS])
    heat_chart = alt.Chart(heat).mark_rect(cornerRadius=6).encode(
        x=alt.X("요일:N", sort=hb.DAYS, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("시간대:N", sort=slot_names, title=None),
        color=alt.Color("금액:Q", scale=alt.Scale(range=["#F3F5FF", ui.BLUE]), legend=alt.Legend(title="만 원")),
        tooltip=["요일", "시간대", alt.Tooltip("금액:Q", title="금액(만 원)")])
    ui.chart(heat_chart.properties(height=260))
    m1, m2, m3 = st.columns(3)
    m1.metric("밤 9시~새벽 결제 비중", f"{habit_stats['late_share']}%")
    m2.metric("가장 많이 쓴 요일", f"{habit_stats['peak_day']}요일")
    m3.metric("가장 많이 쓴 시간대", habit_stats["peak_slot"])

    # AI 리포트 카드
    with st.container(key="card-ai-habit"):
        mode_chip = ui.chip("✨ AI가 직접 분석", ui.BLUE) if record["mode"] == "AI" else ui.chip("기본 모드", ui.MUTED)
        st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<h3 style='margin:0'>{BUDDY_ICON} {buddy}의 소비 습관 리포트</h3>{mode_chip}</div>"
                    f"<div class='small'>{record['created']}</div>", unsafe_allow_html=True)
        if d["persona"]:
            st.markdown(f"<div class='small' style='margin-top:12px'>너의 소비 유형은</div>"
                        f"<div style='font-size:1.6rem;font-weight:800;letter-spacing:-0.02em'>{ui.esc(d['persona'])}</div>",
                        unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:1.1rem;font-weight:700;margin:6px 0 4px'>💬 {ui.esc(d['headline'])}</div>",
                    unsafe_allow_html=True)

        cand_by_key = {c["key"]: c for c in habit_cands}
        for i, ptn in enumerate(d["patterns"]):
            c = cand_by_key.get(ptn["key"])
            if not c:          # 내역이 바뀌어서 후보가 사라진 패턴은 숨김
                continue
            effect = f"월 {ch.fmt(c['save'])} 절약"
            if c["days"]:
                effect += f" → {c['goal']} 약 {c['days']}일 빨리!"
            st.markdown(f"<div class='rec'><div class='rec-name'>{i + 1}. {ui.esc(ptn['title'])}</div>"
                        f"<div class='rec-row'>🔍 {ui.esc(ptn['insight'])}</div>"
                        f"<div class='rec-row'>💡 {ui.esc(ptn['tip'])}</div>"
                        f"<div class='rec-row' style='color:{ui.GREEN};font-weight:700'>💰 {effect}</div></div>",
                        unsafe_allow_html=True)
        if not d["patterns"]:
            ui.tip("눈에 띄게 줄일 습관이 없어! 지금처럼 고르게 쓰면 돼.", ui.GREEN)
        if d["challenge"]:
            say("🏁 이번 주 챌린지: " + d["challenge"])

        # AI가 쓴 숫자가 앱 계산값과 맞는지 (환각 방지)
        if record["mode"] == "AI":
            if record["unknown"]:
                st.warning(f"⚠️ 앱 계산에 없는 숫자가 있어요: {', '.join(record['unknown'])} — 이 부분은 한 번 더 확인해줘.")
            elif record["checked"]:
                st.caption(f"✅ 숫자 검증 통과: AI가 쓴 숫자 {record['checked']}개가 모두 앱 계산과 일치해요.")
        else:
            st.caption("지금은 규칙으로 고른 기본 리포트예요. API 키를 설정하면 AI가 결제 시간·요일을 읽고 "
                       "소비 유형 별명과 습관을 직접 찾아줘요.")
            if record.get("note"):
                st.caption(f"({record['note']})")
        if record["signature"] != hb.signature(habit_facts):
            st.info("리포트를 만든 뒤로 소비 내역이나 목표가 바뀌었어. 다시 분석해볼래?")
        if st.button("🔄 다시 분석하기", type="primary", key="re_habit"):
            new_habit_report()
            st.rerun()

    with st.expander("🔎 AI에게 준 사실 목록 보기 (모든 숫자는 앱이 계산)"):
        st.code(habit_facts, language=None)


with tab_spend:
    st.caption(f"지금 보는 소비 내역: {tx_source}")
    sub_habit, sub_review = st.tabs(["🕒 소비 습관 리포트", "📅 월간 점검"])

    with sub_habit:
        render_habits()

    with sub_review:
        if len(months) < 2:
            st.info("비교하려면 최소 두 달치 소비 내역이 필요해요.")
        else:
            this_month = st.selectbox("점검할 달", months[1:], index=len(months) - 2)
            last_month = months[months.index(this_month) - 1]
            rows = pl.compare_months(tx[last_month], tx[this_month], {})
            total_last = round(sum(tx[last_month].values()) / 10000)
            total_this = round(sum(tx[this_month].values()) / 10000)

            m1, m2, m3 = st.columns(3)
            m1.metric(f"{last_month} 지출", ch.fmt(total_last))
            m2.metric(f"{this_month} 지출", ch.fmt(total_this), delta=f"{total_this - total_last:+}만 원",
                      delta_color="inverse")
            m3.metric("계획한 생활비", ch.fmt(profile.spending))

            bars_df = pd.DataFrame([{"카테고리": r["카테고리"], "달": lbl, "금액": r[key]}
                                    for r in rows for lbl, key in [(last_month, "지난달"), (this_month, "이번 달")]])
            spend_chart = alt.Chart(bars_df).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("카테고리:N", sort=[r["카테고리"] for r in rows], title=None),
                x=alt.X("금액:Q", title="만 원"), yOffset="달:N",
                color=alt.Color("달:N", scale=alt.Scale(range=["#C9D4FF", ui.BLUE]),
                                legend=alt.Legend(orient="top", title=None)),
                tooltip=["카테고리", "달", "금액"])
            ui.chart(spend_chart.properties(height=40 * len(rows) + 40))

            for m in ch.review_messages(rows, profile.spending, total_this,
                                        nearest.alloc if nearest else 0, nearest.goal if nearest else None):
                say(m)

            if this_month not in memory["reviewed_months"]:
                if st.button("이번 달 점검 완료하고 배지 받기", type="primary"):
                    gained = ch.POINTS["monthly_review_ok"] if total_this <= profile.spending else 0
                    memory["points"] += gained
                    memory["reviewed_months"].append(this_month)
                    remember()
                    st.session_state.flash = [f"점검 완료! 🏅 실천 배지 +{gained}"]
                    st.rerun()
            else:
                st.caption("이 달은 이미 점검을 마쳤어요.")



# ---------------- 💬 AI 재무설계사와 상담하기: 채팅만 ----------------
def decide_purchase(pending, choice):
    """'이거 사도 돼?' 뒤에 '참을게' / '살래'라고 답하면 기록하고 답장을 돌려준다."""
    item, price = pending["item"], pending["price"]
    memory["decisions"].append({"item": item, "price": price, "choice": choice})
    if choice == "hold":
        memory["points"] += ch.POINTS["held_back"]
        st.session_state.flash = ["멋지다! 🏅 실천 배지 +1"]
        return f"멋지다! {ch.josa(item, '을를')} 참아서 {ch.fmt(price)}을 지켰어. 실천 배지 하나 줄게 🏅"
    note = "알겠어! 가끔은 나를 위한 선물도 필요하지."
    if nearest:   # 가장 가까운 목표용 상품에서 뺀다 (큰 것부터)
        left = price
        for h in sorted([h for h in memory["holdings"] if h.get("용도") == nearest.goal.name], key=lambda h: -h["금액"]):
            take = min(h["금액"], left)
            h["금액"] -= take
            left -= take
        memory["holdings"] = [h for h in memory["holdings"] if h["금액"] > 0]
        if left < price:
            note += f" 대신 {nearest.goal.name}용으로 모은 돈에서 {ch.fmt(price - left)}을 뺐어."
    return note


with tab_chat:
    history = memory["chat"]
    if not history:
        say(f"안녕 {profile.name}! 나는 너의 AI 재무설계사 {buddy}야. 돈 고민이면 뭐든 물어봐. "
            "IRP·청약·대출 같은 제도도 쉽게 설명해주고, '신발 12만 원 사도 돼?'처럼 물어보면 목표가 며칠 늦어지는지도 계산해줄게.")
    for msg in history[-30:]:
        with st.chat_message(msg["role"], avatar=BUDDY_ICON if msg["role"] == "assistant" else None):
            st.markdown(ui.esc(msg["content"]))
    with st.form("chat_form", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        text = c1.text_input("메시지", placeholder=f"{buddy}에게 물어보기 (예: IRP가 뭐야? / 신발 12만 원 사도 돼?)",
                             label_visibility="collapsed")
        sent = c2.form_submit_button("보내기", type="primary", width="stretch")
    if sent and text.strip():
        q = text.strip()
        pending = memory.get("pending_purchase")
        buy = cs.parse_purchase(q)                       # '○○ 얼마 사도 돼?' 인지
        choice = cs.decision_of(q) if pending and not buy else None
        with st.spinner(f"{ch.josa(buddy, '이가')} 생각하는 중..."):
            if choice:                                   # 직전 '사도 돼?'에 대한 결정
                answer = decide_purchase(pending, choice)
                memory["pending_purchase"] = None
            elif buy and buy[1]:                         # 사도 돼? → 앱이 계산, AI는 그 숫자로 답함
                item, price = buy
                calc = ch.purchase_message(item, price, pl.purchase_impact(price, plan))
                context = (facts + "\n\n[이거 사도 돼? — 앱이 계산한 결과. 이 숫자만 써서 답해]\n" + calc
                           + f"\n[실천 배지] {badges}개")
                answer = llm.reply(q, history, context, buddy, animal, lambda _q: calc)
                answer += "\n\n살 거야, 참을 거야? '참을게' 또는 '살래'라고 말해줘!"
                memory["pending_purchase"] = {"item": item, "price": price}
            elif buy:                                    # 가격을 안 알려줬을 때
                answer = f"{ch.josa(buy[0], '은는')} 얼마짜리야? 가격도 같이 알려줘! (예: {buy[0]} 12만 원 사도 돼?)"
            else:                                        # 일반 상담: 내 사실 목록 + 모든 제도 자료를 근거로
                memory["pending_purchase"] = None
                context = facts + "\n\n" + kn.all_text() + f"\n[실천 배지] {badges}개"
                answer = llm.reply(q, history, context, buddy, animal, lambda x: cs.rule_answer(x, None, plan))
        memory["chat"].append({"role": "user", "content": q})
        memory["chat"].append({"role": "assistant", "content": answer})
        remember()
        st.rerun()
