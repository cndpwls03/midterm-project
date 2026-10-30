"""
classifier.py — 카드 승인 문자 / 카드 내역 자동 분류
붙여넣은 카드 문자에서 날짜·시간·가게(내용)·금액을 뽑고, 카테고리를 붙입니다.

두 가지 모드가 있어요.
1) AI 모드: API 키(Gemini 또는 Claude)가 있으면 AI에게 여러 줄을 한 번에 묶어 보내고 JSON으로 답을 받음
2) 기본 모드: API 키가 없으면 정규식(글자 패턴)으로 값을 뽑고, 키워드 규칙으로 카테고리를 정함

어떤 경우에도 앱이 멈추지 않도록, AI 답이 이상하면 '미분류'로 처리합니다.
"""
import datetime
import json
import re

import llm

CATEGORIES = ["식비", "배달", "카페", "쇼핑", "교통", "문화·여가", "기타"]
UNKNOWN = "미분류"
BATCH_SIZE = 25   # AI에 한 번에 보낼 줄 수 (호출 횟수를 줄이기 위해 묶어서 보냄)

# ---------------------------------------------------------------
# 1. 기본 모드 — 키워드 규칙
#    위에서부터 차례로 확인해요. 순서가 중요해요.
#    예) '쿠팡이츠'는 '쿠팡'(쇼핑)보다 먼저 '배달'로 잡혀야 함
# ---------------------------------------------------------------
KEYWORDS = [
    ("배달", ["배달의민족", "배민", "쿠팡이츠", "요기요", "땡겨요", "배달"]),
    ("카페", ["스타벅스", "투썸", "이디야", "메가MGC", "메가커피", "빽다방", "컴포즈", "폴바셋",
             "할리스", "커피빈", "블루보틀", "카페", "커피"]),
    ("교통", ["티머니", "캐시비", "택시", "카카오T", "코레일", "KTX", "SRT", "지하철", "버스",
             "주유", "GS칼텍스", "SK에너지", "S-OIL", "주차", "하이패스", "고속도로"]),
    ("문화·여가", ["CGV", "메가박스", "롯데시네마", "영화", "넷플릭스", "유튜브", "티빙", "왓챠",
                "디즈니", "멜론", "스포티파이", "인터파크", "티켓", "공연", "전시", "노래방", "PC방", "볼링"]),
    ("식비", ["GS25", "CU ", "씨유", "세븐일레븐", "이마트24", "미니스톱", "편의점", "이마트",
             "홈플러스", "롯데마트", "마트", "김밥", "분식", "식당", "도시락", "한솥", "맥도날드",
             "버거킹", "롯데리아", "맘스터치", "서브웨이", "치킨", "피자", "국밥", "베이커리",
             "파리바게뜨", "뚜레쥬르"]),
    ("쇼핑", ["쿠팡", "무신사", "지그재그", "에이블리", "29CM", "올리브영", "다이소", "11번가",
             "G마켓", "옥션", "유니클로", "ZARA", "자라", "H&M", "백화점", "아울렛"]),
    ("기타", ["병원", "의원", "약국", "치과", "통신", "SKT", "LG U+", "보험", "관리비", "수수료"]),
]


def rule_category(text: str) -> str:
    """가게 이름(또는 문자 전체)에 키워드가 있으면 그 카테고리, 없으면 '미분류'"""
    padded = text + " "   # 'CU ' 처럼 띄어쓰기로 끝나는 키워드도 잡히게
    for category, words in KEYWORDS:
        if any(w in padded for w in words):
            return category
    return UNKNOWN


# ---------------------------------------------------------------
# 2. 문자에서 날짜·시간·금액·가게 이름 뽑기 (정규식)
# ---------------------------------------------------------------
CARD_WORDS = [
    "Web발신", "신한카드", "신한체크", "신한", "KB국민카드", "KB국민", "국민카드", "삼성카드", "현대카드",
    "롯데카드", "하나카드", "우리카드", "NH농협카드", "NH농협", "농협카드", "BC카드", "비씨카드",
    "카카오뱅크", "토스뱅크카드", "토스뱅크", "씨티카드", "체크카드", "체크", "승인취소", "승인",
    "일시불", "결제", "사용", "님",
]
AMOUNT_RE = re.compile(r"(-?[\d,]+)\s*원")
TIME_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
DATE_RES = [
    re.compile(r"(?<!\d)(20\d{2})[./-](\d{1,2})[./-](\d{1,2})(?!\d)"),   # 2026/10/22
    re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일"),                     # 10월24일
    re.compile(r"(?<![\d,])(\d{1,2})[/.-](\d{1,2})(?![\d,])"),          # 10/24
]


def extract_amount(text: str):
    """금액(원)을 찾는다. '누적 312,400원', '잔액 ...원'은 건너뛴다. 취소 건은 음수로."""
    for m in AMOUNT_RE.finditer(text):
        before = text[max(0, m.start() - 4):m.start()]
        if "누적" in before or "잔액" in before:
            continue
        try:
            value = int(m.group(1).replace(",", ""))
        except ValueError:
            continue
        return -abs(value) if "취소" in text else value
    return None


def extract_date(text: str, year: int):
    """날짜를 'YYYY-MM-DD'로. 연도가 없으면 올해(year)로 채운다."""
    for i, pattern in enumerate(DATE_RES):
        m = pattern.search(text)
        if not m:
            continue
        if i == 0:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            y, mo, d = year, int(m.group(1)), int(m.group(2))
        try:
            return datetime.date(y, mo, d).isoformat()
        except ValueError:
            continue   # 13월처럼 말이 안 되는 날짜는 건너뜀
    return ""


def extract_time(text: str) -> str:
    m = TIME_RE.search(text)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return ""


def extract_merchant(text: str) -> str:
    """카드사·승인·이름·날짜·시간·금액을 지우고 남은 글자를 가게 이름으로 본다."""
    s = re.sub(r"\[[^\]]*\]", " ", text)                  # [신한카드] 같은 대괄호
    s = re.sub(r"(누적|잔액)\s*-?[\d,]+\s*원", " ", s)      # 누적 금액
    s = AMOUNT_RE.sub(" ", s)
    s = TIME_RE.sub(" ", s)
    for pattern in DATE_RES:
        s = pattern.sub(" ", s)
    s = re.sub(r"\S\*\S?", " ", s)                         # 홍*동 같은 가린 이름
    s = re.sub(r"\(\d{3,4}\)", " ", s)                     # (1234) 같은 카드 번호
    for word in CARD_WORDS:
        s = s.replace(word, " ")
    return re.sub(r"\s+", " ", s).strip(" ,.-:")


def parse_line_rule(line: str, year: int) -> dict:
    """기본 모드: 한 줄을 정규식 + 키워드로 정리"""
    merchant = extract_merchant(line)
    return {
        "날짜": extract_date(line, year),
        "시간": extract_time(line),
        "내용": merchant,
        "금액": extract_amount(line),
        "카테고리": rule_category(merchant or line),
        "원문": line,
    }


# ---------------------------------------------------------------
# 3. AI 모드 — AI에게 여러 줄을 한 번에 보내 JSON으로 받기
# ---------------------------------------------------------------
SYSTEM_PROMPT = f"""너는 카드 승인 문자를 가계부 항목으로 정리하는 도우미야.
사용자가 번호를 붙인 카드 문자 여러 줄을 보내면, 줄마다 JSON 객체 하나를 만들어서
JSON 배열 하나로만 답해. 설명 문장이나 코드 블록 표시는 쓰지 마.

각 객체의 필드:
- "id": 입력 줄 번호 (정수)
- "date": "YYYY-MM-DD". 문자에 연도가 없으면 연도 자리는 "????"로 둬. 날짜가 없으면 "".
- "time": "HH:MM" (24시간제). 없으면 "".
- "merchant": 가게 이름만 (카드사, '승인', 사람 이름, 누적 금액은 빼기)
- "amount": 결제 금액(원, 정수). '누적'이나 '잔액' 금액이 아니라 이번 결제 금액. 취소 건은 음수.
- "category": 아래 목록 중 정확히 하나. 판단이 어려우면 "{UNKNOWN}".

카테고리 기준:
- 식비: 마트·편의점·식당·빵집 등 먹거리를 직접 산 것
- 배달: 배달 앱으로 시킨 음식
- 카페: 커피·음료·디저트 가게
- 쇼핑: 온라인 쇼핑, 옷, 화장품, 생활용품
- 교통: 대중교통, 택시, 기차, 주유, 주차, 공유 자전거
- 문화·여가: 영화, 공연, 책, 구독 서비스(OTT·음악), 운동, 노래방
- 기타: 병원·약국, 통신비, 보험, 그 밖의 것"""


def _ai_batch(lines, year):
    """줄 묶음을 AI에 한 번 보내고, 줄 번호별 결과 딕셔너리를 돌려준다. (실패하면 llm.LLMError)"""
    numbered = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    text = llm.complete(SYSTEM_PROMPT, [{"role": "user", "content": numbered}], max_tokens=8000, json_mode=True)
    return _parse_ai_json(text)


def _parse_ai_json(text):
    """AI 답에서 JSON 배열을 찾아 {줄 번호: 객체}로. 깨져 있으면 빈 딕셔너리."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        return {}
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    result = {}
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            try:
                result[int(item.get("id"))] = item
            except (TypeError, ValueError):
                continue
    return result


def _merge_ai(line, item, year):
    """
    AI가 준 값을 검사해서 정리한다.
    - 카테고리가 목록에 없으면 '미분류'
    - 금액·날짜·시간이 이상하면 정규식으로 뽑은 값으로 대신함
    """
    base = parse_line_rule(line, year)
    if item is None:                                  # AI 답에 이 줄이 없거나 JSON이 깨짐
        return {**base, "카테고리": UNKNOWN}

    category = item.get("category")
    amount = item.get("amount")
    if not isinstance(amount, int):
        try:
            amount = int(str(amount).replace(",", ""))
        except (TypeError, ValueError):
            amount = base["금액"]

    # 날짜: 월·일은 AI 답을 쓰고, 연도는 문자에 있을 때만 인정 (없으면 올해)
    date = base["날짜"]
    m = re.match(r"^(\d{4}|\?{4})-(\d{1,2})-(\d{1,2})$", str(item.get("date", "")))
    if m:
        has_year = bool(DATE_RES[0].search(line))
        y = int(m.group(1)) if has_year and m.group(1).isdigit() else year
        try:
            date = datetime.date(y, int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass

    time = str(item.get("time") or "")
    if not re.match(r"^\d{2}:\d{2}$", time):
        time = base["시간"]

    return {
        "날짜": date,
        "시간": time,
        "내용": str(item.get("merchant") or base["내용"]).strip(),
        "금액": amount,
        "카테고리": category if category in CATEGORIES else UNKNOWN,
        "원문": line,
    }


# ---------------------------------------------------------------
# 4. 바깥에서 쓰는 함수
# ---------------------------------------------------------------
def ai_available() -> bool:
    return llm.api_available()


def classify_lines(lines, mode="auto", year=None):
    """
    여러 줄을 분류한다.
    mode: "auto"(키가 있으면 AI) / "ai" / "rule"
    돌려주는 값: {"rows": [...], "mode": "AI" 또는 "기본", "warnings": [...]}
    """
    year = year or datetime.date.today().year
    lines = [ln.strip() for ln in lines if ln.strip()]
    use_ai = mode == "ai" or (mode == "auto" and ai_available())

    if not use_ai:
        return {"rows": [parse_line_rule(ln, year) for ln in lines], "mode": "기본", "warnings": []}

    rows, warnings = [], []
    for start in range(0, len(lines), BATCH_SIZE):
        batch = lines[start:start + BATCH_SIZE]
        try:
            answers = _ai_batch(batch, year)
        except Exception as e:   # 네트워크 오류 등 → 이 묶음만 기본 모드로
            reason = str(e) if isinstance(e, llm.LLMError) else type(e).__name__
            warnings.append(f"AI 연결 오류로 {len(batch)}건은 기본 모드로 분류했어요. ({reason})")
            rows += [parse_line_rule(ln, year) for ln in batch]
            continue
        if not answers:
            warnings.append(f"AI 답을 읽지 못해서 {len(batch)}건을 '미분류'로 두었어요.")
        rows += [_merge_ai(ln, answers.get(i + 1), year) for i, ln in enumerate(batch)]
    return {"rows": rows, "mode": "AI", "warnings": warnings}


def classify_text(text, mode="auto", year=None):
    """붙여넣은 글 전체(여러 줄)를 분류"""
    return classify_lines(text.splitlines(), mode=mode, year=year)
