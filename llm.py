"""
llm.py — AI 연결부 (앱의 모든 AI 기능이 여기 complete() 하나로 AI를 부릅니다)

어떤 AI를 쓰나
- GEMINI_API_KEY(또는 GOOGLE_API_KEY)가 있으면 Google Gemini (무료 사용량 있음)
- ANTHROPIC_API_KEY('sk-ant-'로 시작)가 있으면 Claude
- 둘 다 없으면 AI 없이 규칙 기반 '기본 모드'로 동작합니다.

AI 서버가 붐비거나(503·429) 응답이 늦으면 잠깐 쉬었다가 다시 시도하고,
그래도 안 되면 다음 모델로 넘어갑니다. 끝까지 실패하면 LLMError를 내고,
각 기능은 그걸 받아 기본 모드로 대신 답합니다. (앱이 멈추지 않게)
"""
import os
import time

import requests

# Claude
MODEL = "claude-haiku-5-5"
# Gemini: 앞 모델이 붐비면 다음 모델로. (2026-10-28 기준, 무료 키로 확인한 모델)
# - gemini-flash-lite-latest: 가장 빠름(1~2초), 최신 Flash-Lite로 자동 연결
# - gemini-3.5-flash: 조금 느리지만 더 똑똑함 (생각은 짧게 하도록 설정)
GEMINI_MODELS = [
    ("gemini-flash-lite-latest", {}),
    ("gemini-3.5-flash", {"thinkingConfig": {"thinkingLevel": "low"}}),
]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 60        # 한 번 기다리는 최대 시간 (초)
RETRY_WAIT = 2      # 붐빌 때 다시 시도하기 전 쉬는 시간 (초)


class LLMError(Exception):
    """AI 호출이 끝까지 실패했을 때 (화면에 보여줄 짧은 이유를 담음)"""


# ---------------------------------------------------------------
# 1. 어떤 AI를 쓸 수 있는지
# ---------------------------------------------------------------
def _gemini_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _claude_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return key if key.startswith("sk-ant-") else None   # 다른 회사 키를 잘못 넣은 경우는 무시


def provider():
    """'Gemini' / 'Claude' / None(기본 모드)"""
    if _gemini_key():
        return "Gemini"
    if _claude_key():
        try:
            import anthropic  # noqa: F401
            return "Claude"
        except ImportError:
            return None
    return None


def api_available():
    return provider() is not None


def key_problem():
    """키를 잘못 넣은 것 같으면 안내 문구, 괜찮으면 None (사이드바에 표시)"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and not key.startswith("sk-ant-") and not _gemini_key():
        return "ANTHROPIC_API_KEY에 Claude 키가 아닌 값이 들어 있어요. Gemini 키라면 GEMINI_API_KEY로 저장해줘."
    return None


# ---------------------------------------------------------------
# 2. AI에게 글 받기 — 모든 AI 기능이 이 함수를 씀
# ---------------------------------------------------------------
def complete(system, messages, max_tokens=4000, json_mode=False):
    """
    system: AI의 역할·규칙 설명
    messages: [{"role": "user" 또는 "assistant", "content": 글}, ...]
    json_mode: True면 JSON 형식으로만 답하게 함 (조언·추천·분류용)
    돌려주는 값: AI가 쓴 글 (실패하면 LLMError)
    """
    who = provider()
    if who == "Gemini":
        return _gemini(system, messages, max_tokens, json_mode)
    if who == "Claude":
        return _claude(system, messages, max_tokens)
    raise LLMError("API 키가 없어요")


def _gemini(system, messages, max_tokens, json_mode):
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages]
    last = "AI 연결 오류"
    for model, extra in GEMINI_MODELS:
        config = {"maxOutputTokens": max_tokens, **extra}
        if json_mode:
            config["responseMimeType"] = "application/json"
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": config}
        for attempt in range(2):          # 모델마다 최대 2번 시도
            try:
                r = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": _gemini_key()},
                                  json=body, timeout=TIMEOUT)
            except requests.RequestException as e:
                last = f"AI 응답이 늦어요 ({type(e).__name__})"
                continue
            if r.status_code in (429, 500, 503):      # 붐빔·일시 오류 → 잠깐 쉬고 다시
                last = "AI 서버가 붐벼요" if r.status_code != 429 else "무료 사용량을 잠깐 다 썼어요"
                time.sleep(RETRY_WAIT)
                continue
            if r.status_code in (401, 403):
                raise LLMError("API 키를 확인해줘 (인증 오류)")
            if not r.ok:
                last = f"AI 오류 ({r.status_code})"
                break                                 # 이 모델은 포기하고 다음 모델로
            try:
                cand = r.json()["candidates"][0]
                text = "".join(p.get("text", "") for p in cand["content"]["parts"] if not p.get("thought"))
            except (KeyError, IndexError, ValueError):
                last = "AI 답이 비어 있어요"
                break
            if text.strip():
                return text.strip()
            last = "AI 답이 비어 있어요"
            break
    raise LLMError(last)


def _claude(system, messages, max_tokens):
    import anthropic
    try:
        response = anthropic.Anthropic().messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages])
    except Exception as e:   # 네트워크·키 오류
        raise LLMError(f"AI 연결 오류 ({type(e).__name__})") from e
    # 응답에는 생각(thinking) 블록이 먼저 올 수 있어서, 글(text) 블록만 모은다
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise LLMError("AI 답이 비어 있어요")
    return text


# ---------------------------------------------------------------
# 3. 상담 탭 대화
# ---------------------------------------------------------------
SYSTEM_TEMPLATE = """너는 '{name}'라는 이름의 귀여운 {animal} 모습을 한 재무설계 친구야. 사용자의 오랜 친구처럼 반말로, 쉽고 따뜻하게 말해.
아래는 사용자의 현재 재무 상황, 지금 상담 주제의 제도 자료, 그리고 네가 기억하는 내용이야.

{context}

규칙:
- 특정 주식 종목이나 특정 금융사 상품을 사라고 권하지 마. 제도(IRP, 청약통장 등)와 상품 유형(예적금, ETF 등), 비중까지만 말해.
- 제도의 조건(나이, 한도, 공제율 등)은 [제도 자료]에 있는 것만 말해. 자료에 없거나 바뀌었을 수 있는 건 '공식 안내에서 확인해줘'라고 해.
- 사용자 숫자는 위 정보에 있는 것만 쓰고, 모르는 건 모른다고 말해.
- 어려운 말은 쉬운 말로 풀어서, 가능하면 사용자 상황(나이·월급·목표)과 연결해서 설명해.
- 수익률은 가정일 뿐 보장되지 않는다는 점을 필요할 때 짚어줘.
- 5~6문장 이내로 답해."""


def reply(user_text, history, context, name="머니", animal="곰", rule_fn=None):
    """
    대화 답변. API 키가 있으면 AI, 없으면 rule_fn(질문) 또는 기본 규칙으로 답한다.
    rule_fn: 기본 모드에서 제도 설명을 찾아 답하는 함수 (consult.rule_answer)
    """
    fallback = (rule_fn or _rule_reply)
    if not api_available():
        return fallback(user_text)
    messages = [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    messages.append({"role": "user", "content": user_text})
    try:
        return complete(SYSTEM_TEMPLATE.format(name=name, animal=animal, context=context), messages)
    except LLMError as e:   # 실패해도 앱이 멈추지 않게 기본 답변으로
        return f"({e} — 기본 답변으로 대신할게)\n" + fallback(user_text)


def _rule_reply(text):
    """API 없이 쓰는 간단한 답변 규칙"""
    if any(k in text for k in ["사도 돼", "살까", "사고 싶"]):
        return "가격도 같이 말해줘! 예: '신발 12만 원 사도 돼?' 그러면 목표가 며칠 늦어지는지 계산해줄게."
    if any(k in text for k in ["얼마", "저축", "모아"]):
        return "'💰 이번 달 플랜' 탭에 목표마다 매달 얼마씩 넣으면 좋을지 정리해뒀어."
    if any(k in text for k in ["힘들", "망했", "많이 썼"]):
        return "괜찮아, 한 달 삐끗했다고 끝나는 거 아니야. '🧾 소비' 탭의 소비 습관 리포트에서 줄일 곳 하나만 찾아보자."
    if any(k in text for k in ["주식", "종목", "코인"]):
        return "특정 종목은 내가 골라줄 수 없어. 대신 네 성향에 맞는 투자 비중은 '🗺️ 평생 플랜'에 있어!"
    if any(k in text for k in ["카드", "내역", "습관"]):
        return "'🧾 소비' 탭의 소비 습관 리포트에서 언제 돈을 많이 쓰는지 볼 수 있어!"
    if any(k in text for k in ["은퇴", "노후", "연금", "평생", "결혼", "집"]):
        return "'🗺️ 평생 플랜' 탭에서 장기 목표를 누르면 목표별 포트폴리오와 꼭 알아야 할 제도를 볼 수 있어!"
    return "응응, 듣고 있어! (지금은 기본 대화 모드야. AI 대화를 켜려면 README를 봐줘)"
