"""
memory.py — 캐릭터의 '기억' 저장소
가입 정보, 목표, 캐릭터 모습, 지난달 약속, 포인트, 대화를 data/memory.json 파일에 저장해서
앱을 껐다 켜도 머니가 기억하게 만듭니다.
"""
import json
import os

MEMORY_PATH = os.path.join(os.path.dirname(__file__), "data", "memory.json")

DEFAULT = {
    "profile": None,       # 가입 정보 (이름, 나이, 직업, 월급, 투자 성향 등) — 없으면 가입 화면부터
    "goals": [],           # 목표 목록 [{"name", "target", "saved", "months", "is_asset", "done"}]
    "life": None,          # 은퇴·자녀 계획
    "avatar": None,        # 동물 친구 꾸미기 정보 (이름·동물·옷·머리 장식 등)
    "advice": None,        # 동물 친구의 가장 최근 AI 조언 (실천 체크 포함)
    "advice_history": [],  # 지난 조언 기록 (최근 10개)
    "holdings": None,      # 내 포트폴리오: 가입한 상품 [{"상품", "금액"(만 원), "용도"(비상금/목표 이름/노후·여유 자금)}]
    "portfolios": {},      # 장기 목표별 AI 추천 포트폴리오 {목표 이름: 추천 기록}
    "habit_report": None,  # 가장 최근 소비 습관 리포트 (AI 또는 기본 모드)
    "points": 0,           # 실천 배지 수
    "promises": {},        # (12차에서 약속 기능을 빼서 지금은 안 씀)
    "reviewed_months": [], # 이미 점검을 끝낸 달 (포인트 중복 지급 방지)
    "decisions": [],       # "이거 사도 돼?" 선택 기록 (채팅에서 '참을게'·'살래')
    "pending_purchase": None,  # 채팅에서 방금 물어본 '사도 돼?' (다음 답이 참을게/살래인지 보려고)
    "chat": [],            # 대화 기록 [{"role": "user"/"assistant", "content": ..., "topic": 상담 주제}]
}


def load():
    if not os.path.exists(MEMORY_PATH):
        return json.loads(json.dumps(DEFAULT))
    with open(MEMORY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for key, value in DEFAULT.items():   # 새 항목이 생겨도 오류 없이 동작
        data.setdefault(key, json.loads(json.dumps(value)))
    return data


def save(data):
    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def reset():
    save(json.loads(json.dumps(DEFAULT)))


# ---------------------------------------------------------------
# 내 소비 내역 (카드 내역 붙여넣기로 분류한 것) — data/my_spending.csv
# 열: 날짜, 카테고리, 내용, 금액(원), 시간
#   기존 예시 데이터(sample_spending.csv)와 같은 열에 '시간'만 추가했어요.
#   시간은 다음에 만들 '요일·시간대별 소비 습관' 기능에서 쓸 예정이에요.
# ---------------------------------------------------------------
import csv  # noqa: E402

SPENDING_PATH = os.path.join(os.path.dirname(__file__), "data", "my_spending.csv")
SPENDING_COLUMNS = ["날짜", "카테고리", "내용", "금액", "시간"]


def load_spending_rows():
    """저장된 내 소비 내역을 줄 목록으로 읽는다. 파일이 없으면 빈 목록."""
    if not os.path.exists(SPENDING_PATH):
        return []
    with open(SPENDING_PATH, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save_spending(rows):
    """
    새 소비 내역을 파일 끝에 추가한다. 이미 똑같은 건(날짜·시간·내용·금액이 같음)은 건너뛴다.
    (추가한 건수, 중복이라 건너뛴 건수)를 돌려준다.
    """
    existing = load_spending_rows()
    seen = {(r["날짜"], r.get("시간", ""), r["내용"], str(r["금액"])) for r in existing}
    new_rows, skipped = [], 0
    for r in rows:
        key = (r["날짜"], r.get("시간", ""), r["내용"], str(int(r["금액"])))
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        new_rows.append({"날짜": r["날짜"], "카테고리": r["카테고리"], "내용": r["내용"],
                         "금액": int(r["금액"]), "시간": r.get("시간", "")})

    all_rows = existing + new_rows
    all_rows.sort(key=lambda r: (r["날짜"], r.get("시간", "")))   # 날짜·시간 순서로 정렬
    os.makedirs(os.path.dirname(SPENDING_PATH), exist_ok=True)
    with open(SPENDING_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SPENDING_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    return len(new_rows), skipped


def reset_spending():
    """내 소비 내역 파일을 지운다 → 앱은 다시 예시 데이터를 사용"""
    if os.path.exists(SPENDING_PATH):
        os.remove(SPENDING_PATH)
