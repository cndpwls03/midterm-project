"""
ui.py — 화면 꾸미기 도우미
글꼴·색·카드 모양(CSS)과, 자주 쓰는 화면 조각(캐릭터 카드, 목표 카드 등)을 모아둔 파일이에요.
app.py는 '무엇을 보여줄지', ui.py는 '어떻게 예쁘게 보여줄지'를 담당해요.
"""
import base64
import html

import altair as alt
import streamlit as st

import avatar as av

# 앱 전체에서 쓰는 색
BLUE = "#4C6FFF"
GREEN = "#12B886"
AMBER = "#F59F00"
RED = "#F06565"
MUTED = "#6B7280"

LEVEL_EMOJI = ["🌱", "🌿", "💼", "👔", "💎", "👑"]   # 부자 단계별 아이콘

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap');
.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp input, .stApp textarea, .stApp button, .stApp li {
  font-family: 'Noto Sans KR', -apple-system, 'Apple SD Gothic Neo', sans-serif;
}
#MainMenu, footer {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
.block-container {max-width: 940px; padding-top: 2.2rem; padding-bottom: 4rem;}
h3 {font-weight: 800 !important; letter-spacing: -0.02em;}

/* 탭을 알약 모양 버튼처럼 */
.stTabs [data-orientation="horizontal"]:not([role]) {border: none !important; box-shadow: none !important;}
.stTabs [role="tablist"] {
  gap: 4px; background: #FFFFFF; padding: 6px; border-radius: 16px; border: 1px solid #E6EAF2 !important;
  box-shadow: 0 2px 10px rgba(30,37,50,.04); width: fit-content; max-width: 100%; flex-wrap: wrap;
}
.stTabs [role="tab"] {
  height: 40px; padding: 0 18px; border-radius: 12px; display: flex; align-items: center;
}
.stTabs [role="tab"] p {font-weight: 700; color: #4B5563; font-size: .95rem;}
.stTabs [role="tab"]:hover {background: #F1F4FB;}
.stTabs [role="tab"][aria-selected="true"] {background: #4C6FFF;}
.stTabs [role="tab"][aria-selected="true"] p {color: #FFFFFF !important;}
.stTabs .react-aria-SelectionIndicator {display: none;}
[data-testid="stAppDeployButton"], .stAppDeployButton {display: none !important;}

/* key가 card로 시작하는 st.container → 흰 카드 */
[class*="st-key-card"] {
  background: #FFFFFF; border: 1px solid #E6EAF2; border-radius: 20px;
  padding: 20px 22px; box-shadow: 0 6px 20px rgba(30,37,50,.06);
}
[class*="st-key-card-ai"] {border: 2px solid #C9D4FF; background: linear-gradient(180deg,#F7F9FF 0%,#FFFFFF 60%);}

/* 숫자 카드(metric) */
[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid #E6EAF2; border-radius: 16px; padding: 14px 18px;
}
[data-testid="stMetricLabel"] p {color: #6B7280; font-weight: 600;}
[data-testid="stMetricValue"] {font-weight: 800; letter-spacing: -0.02em;}

/* 버튼·입력 */
.stButton button, .stFormSubmitButton button {border-radius: 12px; font-weight: 700; padding: 0.45rem 1rem;}
[data-testid="stForm"] {background: #FFFFFF; border: 1px solid #E6EAF2; border-radius: 20px; padding: 22px;}
[data-testid="stChatMessage"] {background: #FFFFFF; border: 1px solid #EEF1F6; border-radius: 16px;}
[data-testid="stSidebar"] {background: #FFFFFF; border-right: 1px solid #E6EAF2;}

/* 직접 만든 HTML 조각 */
.hero {display: flex; gap: 22px; align-items: center; flex-wrap: wrap;
  background: linear-gradient(135deg, #EEF2FF 0%, #E7FAF3 100%);
  border-radius: 24px; padding: 18px 26px; margin-bottom: 18px; border: 1px solid #E3E8F7;}
.hero img {border-radius: 20px; box-shadow: 0 8px 24px rgba(76,111,255,.15);}
.hero-text {flex: 1; min-width: 230px;}
.hello {font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; color: #1E2532;}
.sub {color: #6B7280; margin: 2px 0 10px;}
.label {color: #6B7280; font-size: .85rem; margin-top: 12px;}
.big {font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; color: #1E2532;}
.small {color: #6B7280; font-size: .85rem; margin-top: 4px;}
.chip {display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: .8rem;
  font-weight: 700; margin: 2px 4px 2px 0;}
.bar {height: 10px; background: #E5E9F2; border-radius: 999px; overflow: hidden; margin-top: 8px;}
.bar > div {height: 100%; border-radius: 999px;}
.goal {background: #FFFFFF; border: 1px solid #E6EAF2; border-radius: 18px; padding: 16px 18px;
  margin-bottom: 14px; box-shadow: 0 4px 14px rgba(30,37,50,.05);}
.goal-top {display: flex; justify-content: space-between; align-items: center;}
.goal-name {font-weight: 800; font-size: 1.05rem;}
.goal-pct {font-weight: 800; font-size: 1.3rem; color: #4C6FFF;}
.goal-row {display: flex; justify-content: space-between; color: #6B7280; font-size: .85rem; margin-top: 8px;}
.sec {margin: 26px 0 10px;}
.sec h3 {margin: 0; font-size: 1.25rem;}
.sec p {color: #6B7280; margin: 2px 0 0; font-size: .9rem;}
.tip {border-radius: 14px; padding: 12px 14px; margin: 8px 0; font-size: .95rem;}
.rec {background: #FFFFFF; border: 1px solid #E6EAF2; border-radius: 14px; padding: 12px 16px; margin: 10px 0;}
.rec-name {font-weight: 800; font-size: 1.05rem; margin-bottom: 4px;}
.rec-row {color: #374151; font-size: .92rem; margin-top: 3px;}
[class*="st-key-card-topic"] {min-height: 170px;}
.alloc {display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid #F0F2F7;}
.alloc .dot {width: 10px; height: 10px; border-radius: 50%;}
.alloc .name {font-weight: 700; flex: 1;}
.alloc .prod {color: #6B7280; font-size: .8rem;}
.alloc .amt {font-weight: 800;}
</style>
"""


def esc(text) -> str:
    """
    글자 그대로 보이게 바꾼다.
    - '~'는 마크다운에서 취소선(~~)으로 읽혀서 '19~34세'가 줄이 그어지는 문제가 있어 → HTML 기호(&#126;)로 바꿈
    - 줄바꿈은 마크다운에서 무시되므로 줄 끝에 공백 두 칸을 붙여 실제 줄바꿈으로
    """
    return str(text).replace("~", "&#126;").replace("\n", "  \n")


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def avatar_img(look, age, level, width=200):
    """캐릭터 SVG를 <img> 태그로 (HTML 안에 넣을 때 사용)"""
    svg = av.draw(look, age, level)
    b64 = base64.b64encode(svg.encode("utf-8")).decode()
    return f"<img src='data:image/svg+xml;base64,{b64}' width='{width}'>"


def chip(text, color=BLUE):
    return (f"<span class='chip' style='background:{color}1A;color:{color}'>"
            f"{html.escape(str(text))}</span>")


def bar(ratio, color=BLUE):
    pct = max(0, min(ratio, 1)) * 100
    return f"<div class='bar'><div style='width:{pct:.1f}%;background:{color}'></div></div>"


def section(title, subtitle=""):
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(f"<div class='sec'><h3>{title}</h3>{sub}</div>", unsafe_allow_html=True)


def tip(text, color=BLUE):
    """색이 살짝 들어간 안내 상자"""
    st.markdown(f"<div class='tip' style='background:{color}12;border-left:4px solid {color}'>{esc(text)}</div>",
                unsafe_allow_html=True)


def hero(look, age, level, hello, sub, chips_html, total, progress, progress_text):
    """홈 화면 맨 위: 내 캐릭터 + 인사 + 총자산 + 다음 단계까지"""
    st.markdown(
        f"<div class='hero'>{avatar_img(look, age, level, 170)}"
        f"<div class='hero-text'><div class='hello'>{hello}</div><div class='sub'>{sub}</div>"
        f"{chips_html}<div class='label'>총자산</div><div class='big'>{total}</div>"
        f"{bar(progress, GREEN)}<div class='small'>{progress_text}</div></div></div>",
        unsafe_allow_html=True)


def goal_card(name, kind, ratio, saved_text, target_text, monthly_text, eta_text, on_track):
    color = GREEN if on_track else AMBER
    status = chip("기한 안에 가능", GREEN) if on_track else chip("기한보다 늦어요", AMBER)
    return (f"<div class='goal'><div class='goal-top'><div><span class='goal-name'>{html.escape(name)}</span> "
            f"{chip(kind, MUTED)}</div><div class='goal-pct'>{round(ratio * 100)}%</div></div>"
            f"{bar(ratio, color)}"
            f"<div class='goal-row'><span>{saved_text} / {target_text}</span><span>매달 {monthly_text}</span></div>"
            f"<div class='goal-row'><span>{eta_text}</span>{status}</div></div>")


def alloc_rows(rows):
    """이번 달 배분 목록: [(색, 이름, 상품 유형, 금액 글자, 예적금·투자 글자)]"""
    out = ""
    for color, name, product, amount, split in rows:
        out += (f"<div class='alloc'><div class='dot' style='background:{color}'></div>"
                f"<div style='flex:1'><div class='name'>{html.escape(name)}</div>"
                f"<div class='prod'>{html.escape(product)} · {split}</div></div>"
                f"<div class='amt'>{amount}</div></div>")
    st.markdown(out, unsafe_allow_html=True)


def chart(c):
    """Altair 그래프를 앱 스타일(투명 배경, 연한 격자, 같은 글꼴)로 그린다."""
    styled = (c.configure(background="transparent", font="Noto Sans KR")
              .configure_view(strokeWidth=0)
              .configure_axis(gridColor="#EEF1F6", domainColor="#E5E9F2", tickColor="#E5E9F2",
                              labelColor="#6B7280", titleColor="#6B7280", labelFontSize=11))
    st.altair_chart(styled, width="stretch", theme=None)
