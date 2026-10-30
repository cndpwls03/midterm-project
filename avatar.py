"""
avatar.py — 내 동물 친구 캐릭터 그리기 (SVG 그림)
- 동물(곰·토끼·고양이·강아지·판다·햄스터·펭귄)을 고르고, 털 색·눈·옷·머리 장식·안경·목 장식으로 꾸며요.
- 나이(age)가 들면: 털 색이 살짝 연해지고, 45세부터 흰 눈썹, 60세부터 돋보기 안경이 생겨요.
  (아프거나 약해지는 연출은 하지 않아요)
- 자산 단계(level 0~5)가 오르면 부자 아이템이 늘어나요:
  0 기본 → 1 동전 → 2 돼지 저금통 → 3 돈주머니 → 4 금목걸이 → 5 왕관과 금빛 배경

SVG는 도형을 글자로 적은 그림 형식이라, 이미지 파일 없이 코드만으로 캐릭터를 그릴 수 있어요.
그림은 '뒤에 있는 것부터' 차례로 겹쳐 그려요: 배경 → 귀 → 몸·옷 → 얼굴 → 눈·코·입 → 장식
"""
import math

# ---------------------------------------------------------------
# 1. 꾸미기 선택지
# ---------------------------------------------------------------
ANIMALS = {   # 동물 이름: (아이콘, 기본 털 색)
    "곰": ("🐻", "#B98560"),
    "토끼": ("🐰", "#F7F4EF"),
    "고양이": ("🐱", "#F0B27A"),
    "강아지": ("🐶", "#EED3AE"),
    "판다": ("🐼", "#FFFFFF"),
    "햄스터": ("🐹", "#F2A65A"),
    "펭귄": ("🐧", "#3A4A63"),
}
FUR_COLORS = {
    "기본": None,          # 동물마다 정해진 기본 색
    "갈색": "#B98560",
    "크림": "#EED3AE",
    "회색": "#A9A9B6",
    "흰색": "#F7F4EF",
    "분홍": "#F6C1CF",
    "주황": "#F0A35E",
}
EYE_STYLES = ["반짝눈", "웃는 눈", "동글눈"]
OUTFITS = ["티셔츠", "후드티", "줄무늬 티", "멜빵바지", "원피스", "니트 조끼"]
HEADWEAR = ["없음", "리본 머리띠", "꽃 머리띠", "하트 머리띠", "베레모", "비니"]
GLASSES = ["없음", "동그란 안경", "선글라스"]
NECKWEAR = ["없음", "나비넥타이", "스카프"]

DEFAULT_LOOK = {
    "name": "머니",          # 내가 지어준 친구 이름 (이 친구가 조언·상담을 해줘요)
    "animal": "곰",
    "fur": "기본",
    "eyes": "반짝눈",
    "cheek": True,
    "outfit": "후드티",
    "cloth": "#8FB8FF",     # 옷 색
    "head": "리본 머리띠",
    "glasses": "없음",
    "neck": "없음",
    "accent": "#FF7EB0",    # 머리띠·목 장식 색
}

BACKGROUNDS = ["#EEF2F7", "#E8F5E9", "#E3F2FD", "#EDE7F6", "#FFF6D9", "#FFE8A3"]
GOLD = "#F2B632"
INK = "#3A2A22"                 # 입·코 선 색
PINK = "#F7A8BC"                # 귀 안쪽·코 분홍
EYE_X, EYE_Y = (96, 144), 132   # 눈 위치
BODY = "M66,280 C66,222 88,204 120,204 C152,204 174,222 174,280 Z"


# ---------------------------------------------------------------
# 2. 색 도우미
# ---------------------------------------------------------------
def _mix(c1, c2, t):
    """두 색을 t 비율(0~1)로 섞는다."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def _light(c, t=0.3):
    return _mix(c, "#FFFFFF", t)


def _dark(c, t=0.2):
    return _mix(c, "#000000", t)


def age_soften(age):
    """나이가 들수록 털 색을 살짝 연하게 하는 정도 (40세부터)"""
    if age < 40:
        return 0.0
    return min((age - 40) / 40, 1.0) * 0.35


def fur_color(look):
    base = FUR_COLORS.get(look.get("fur"))
    return base or ANIMALS.get(look["animal"], ANIMALS["곰"])[1]


# ---------------------------------------------------------------
# 3. 부위별 그리기
# ---------------------------------------------------------------
def _defs(fur, level):
    bg = BACKGROUNDS[level]
    return (
        "<defs>"
        f'<radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0%" stop-color="{_light(bg, 0.65)}"/>'
        f'<stop offset="100%" stop-color="{bg}"/></radialGradient>'
        # 얼굴: 왼쪽 위가 밝아서 동글동글 입체감
        f'<radialGradient id="fur" cx="40%" cy="32%" r="75%"><stop offset="0%" stop-color="{_light(fur, 0.35)}"/>'
        f'<stop offset="65%" stop-color="{fur}"/><stop offset="100%" stop-color="{_dark(fur, 0.07)}"/></radialGradient>'
        '<radialGradient id="blush"><stop offset="0%" stop-color="#FF8FA3" stop-opacity="0.6"/>'
        '<stop offset="100%" stop-color="#FF8FA3" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="bodyclip"><path d="{BODY}"/></clipPath>'
        "</defs>"
    )


def _background(level):
    out = '<rect x="0" y="0" width="240" height="280" rx="28" fill="url(#bg)"/>'
    if level >= 3:   # 반짝이
        for x, y, r in [(30, 44, 7), (212, 40, 9), (24, 150, 5), (216, 140, 6)]:
            out += (f'<path d="M{x},{y - r} Q{x},{y} {x + r},{y} Q{x},{y} {x},{y + r} '
                    f'Q{x},{y} {x - r},{y} Q{x},{y} {x},{y - r} Z" fill="#FFFFFF"/>')
    return out


def _ears(animal, fur, line):
    s = f'stroke="{line}" stroke-width="2.5"'
    if animal in ("곰", "판다"):
        ear = "#2B2B2B" if animal == "판다" else fur
        inner = "#4A4A4A" if animal == "판다" else _light(fur, 0.4)
        return "".join(f'<circle cx="{x}" cy="72" r="24" fill="{ear}" {s}/>'
                       f'<circle cx="{x}" cy="74" r="13" fill="{inner}"/>' for x in (66, 174))
    if animal == "토끼":
        return "".join(f'<g transform="rotate({rot} {x} 50)"><ellipse cx="{x}" cy="50" rx="17" ry="42" fill="{fur}" {s}/>'
                       f'<ellipse cx="{x}" cy="54" rx="8" ry="30" fill="{PINK}"/></g>'
                       for x, rot in ((92, -12), (148, 12)))
    if animal == "고양이":
        return (f'<path d="M58,104 L68,40 L112,74 Z" fill="{fur}" {s} stroke-linejoin="round"/>'
                f'<path d="M182,104 L172,40 L128,74 Z" fill="{fur}" {s} stroke-linejoin="round"/>'
                f'<path d="M71,92 L76,58 L101,76 Z" fill="{PINK}"/><path d="M169,92 L164,58 L139,76 Z" fill="{PINK}"/>')
    if animal == "햄스터":
        return "".join(f'<circle cx="{x}" cy="76" r="16" fill="{fur}" {s}/><circle cx="{x}" cy="78" r="8" fill="{PINK}"/>'
                       for x in (74, 166))
    return ""   # 강아지 귀는 얼굴 위에, 펭귄은 귀 없음


def _dog_ears(fur, line):
    ear = _dark(fur, 0.25)
    return "".join(f'<ellipse cx="{x}" cy="132" rx="20" ry="40" fill="{ear}" stroke="{line}" stroke-width="2.5" '
                   f'transform="rotate({rot} {x} 132)"/>' for x, rot in ((54, 18), (186, -18)))


def _outfit(kind, cloth):
    """옷: 몸통 위에 덮어 그림. (옷 그림, 팔 색)을 돌려준다. 팔 색이 None이면 털 색(민소매)."""
    dark = _dark(cloth, 0.15)
    if kind == "후드티":
        return (f'<path d="{BODY}" fill="{cloth}"/>'
                f'<path d="M84,212 Q120,236 156,212 Q152,198 120,198 Q88,198 84,212 Z" fill="{dark}"/>'
                '<path d="M112,218 L110,242 M128,218 L130,242" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round"/>'
                '<circle cx="110" cy="244" r="3" fill="#FFFFFF"/><circle cx="130" cy="244" r="3" fill="#FFFFFF"/>'
                f'<rect x="94" y="252" width="52" height="22" rx="10" fill="{dark}"/>'), cloth
    if kind == "줄무늬 티":
        stripes = "".join(f'<rect x="60" y="{y}" width="120" height="9" fill="#FFFFFF" fill-opacity="0.85"/>'
                          for y in (220, 240, 260))
        return (f'<path d="{BODY}" fill="{cloth}"/><g clip-path="url(#bodyclip)">{stripes}</g>'
                f'<path d="M102,207 Q120,220 138,207" stroke="{dark}" stroke-width="3" fill="none"/>'), cloth
    if kind == "멜빵바지":
        return (f'<path d="{BODY}" fill="#FFFFFF"/>'
                f'<g clip-path="url(#bodyclip)"><rect x="60" y="240" width="120" height="50" fill="{cloth}"/></g>'
                f'<rect x="95" y="205" width="11" height="40" fill="{cloth}"/><rect x="134" y="205" width="11" height="40" fill="{cloth}"/>'
                '<circle cx="100.5" cy="241" r="3.5" fill="#FFD43B"/><circle cx="139.5" cy="241" r="3.5" fill="#FFD43B"/>'
                f'<rect x="108" y="252" width="24" height="15" rx="4" fill="{dark}"/>'), "#FFFFFF"
    if kind == "원피스":
        return (f'<path d="M58,280 C64,236 84,206 120,206 C156,206 176,236 182,280 Z" fill="{cloth}"/>'
                '<path d="M102,206 Q108,222 120,212 Q132,222 138,206 Z" fill="#FFFFFF"/>'
                f'<rect x="76" y="238" width="88" height="6" fill="{dark}"/>'
                f'<path d="M120,241 L110,234 L110,248 Z M120,241 L130,234 L130,248 Z" fill="{dark}"/>'), None
    if kind == "니트 조끼":
        diamonds = "".join(f'<path d="M{x},{y - 9} L{x + 7},{y} L{x},{y + 9} L{x - 7},{y} Z" fill="{dark}"/>'
                           for x, y in ((96, 252), (144, 252), (120, 268)))
        return (f'<path d="{BODY}" fill="#FFFFFF"/>'
                f'<g clip-path="url(#bodyclip)"><path d="M56,200 L104,204 L120,242 L136,204 L184,200 L184,284 L56,284 Z" '
                f'fill="{cloth}"/>{diamonds}</g>'), "#FFFFFF"
    # 기본: 티셔츠
    return (f'<path d="{BODY}" fill="{cloth}"/>'
            f'<path d="M102,207 Q120,220 138,207" stroke="{dark}" stroke-width="3" fill="none"/>'), cloth


def _arms(arm_color, fur, line):
    color = arm_color or fur
    return "".join(f'<ellipse cx="{x}" cy="246" rx="15" ry="24" fill="{color}" stroke="{line}" stroke-width="2" '
                   f'transform="rotate({rot} {x} 246)"/><circle cx="{px}" cy="266" r="11" fill="{fur}" '
                   f'stroke="{line}" stroke-width="2"/>' for x, rot, px in ((70, 20, 64), (170, -20, 176)))


def _face_marks(animal, fur):
    """동물별 얼굴 무늬: 판다 눈 패치, 펭귄 흰 얼굴, 곰·강아지·햄스터 주둥이"""
    if animal == "판다":
        return "".join(f'<ellipse cx="{x}" cy="{EYE_Y + 2}" rx="17" ry="22" fill="#2B2B2B" '
                       f'transform="rotate({rot} {x} {EYE_Y})"/>' for x, rot in ((EYE_X[0], 35), (EYE_X[1], -35)))
    if animal == "펭귄":
        return ('<ellipse cx="100" cy="142" rx="34" ry="40" fill="#FFFFFF"/>'
                '<ellipse cx="140" cy="142" rx="34" ry="40" fill="#FFFFFF"/>')
    if animal in ("곰", "강아지", "햄스터"):
        return f'<ellipse cx="120" cy="160" rx="27" ry="20" fill="{_light(fur, 0.55)}"/>'
    return ""


def _eyes(style):
    """반짝눈 / 웃는 눈 / 동글눈"""
    out = ""
    for x in EYE_X:
        y = EYE_Y
        if style == "웃는 눈":
            out += (f'<path d="M{x - 9},{y + 3} Q{x},{y - 9} {x + 9},{y + 3}" stroke="#1F1A17" stroke-width="4" '
                    'fill="none" stroke-linecap="round"/>')
        elif style == "동글눈":
            out += (f'<circle cx="{x}" cy="{y}" r="6" fill="#1F1A17"/>'
                    f'<circle cx="{x + 2}" cy="{y - 2}" r="2" fill="#FFFFFF"/>')
        else:   # 반짝눈
            out += (f'<ellipse cx="{x}" cy="{y}" rx="8.5" ry="10.5" fill="#1F1A17"/>'
                    f'<circle cx="{x + 3}" cy="{y - 4}" r="3.4" fill="#FFFFFF"/>'
                    f'<circle cx="{x - 3}" cy="{y + 4}" r="1.6" fill="#FFFFFF"/>')
    return out


def _nose_mouth(animal):
    if animal == "펭귄":   # 부리
        return '<path d="M108,150 Q120,142 132,150 Q120,166 108,150 Z" fill="#F59F00" stroke="#D9480F" stroke-width="1.5"/>'
    mouth = (f'<path d="M110,163 Q115,169 120,163 Q125,169 130,163" stroke="{INK}" stroke-width="2.4" '
             'fill="none" stroke-linecap="round"/>')
    if animal in ("곰", "강아지", "판다"):
        return (f'<ellipse cx="120" cy="153" rx="9" ry="6.5" fill="{INK}"/>'
                '<ellipse cx="117" cy="151" rx="3" ry="1.8" fill="#FFFFFF" fill-opacity="0.7"/>' + mouth)
    nose = f'<path d="M114,153 Q120,149 126,153 Q120,160 114,153 Z" fill="{PINK}" stroke="{_dark(PINK, 0.2)}" stroke-width="1"/>'
    whiskers = ('<path d="M70,152 L92,155 M70,162 L92,160 M170,152 L148,155 M170,162 L148,160" '
                f'stroke="{_mix(INK, "#FFFFFF", 0.4)}" stroke-width="1.6" stroke-linecap="round"/>')
    return nose + mouth + whiskers


def _hamster_cheeks():
    return ('<ellipse cx="74" cy="158" rx="20" ry="16" fill="#FFF3E2"/>'
            '<ellipse cx="166" cy="158" rx="20" ry="16" fill="#FFF3E2"/>')


def _heart(x, y, color):
    """(x, y)가 위쪽 가운데인 작은 하트"""
    return (f'<path d="M{x},{y + 4} C{x - 4},{y - 4} {x - 14},{y} {x},{y + 14} '
            f'C{x + 14},{y} {x + 4},{y - 4} {x},{y + 4} Z" fill="{color}"/>')


def _headwear(kind, accent):
    dark = _dark(accent, 0.2)

    def band(color):   # 머리띠 둥근 띠
        return f'<path d="M58,106 Q120,40 182,106" stroke="{color}" stroke-width="7" fill="none" stroke-linecap="round"/>'

    if kind == "리본 머리띠":
        return (band(accent)
                + f'<path d="M150,70 L132,58 L134,82 Z M150,70 L168,58 L166,82 Z" fill="{accent}" '
                  f'stroke="{dark}" stroke-width="1.5" stroke-linejoin="round"/>'
                + f'<circle cx="150" cy="70" r="6" fill="{dark}"/>')
    if kind == "꽃 머리띠":
        flowers = ""
        for cx, cy in ((84, 84), (120, 73), (156, 84)):
            for k in range(5):
                a = math.radians(k * 72 - 90)
                flowers += f'<circle cx="{cx + 7 * math.cos(a):.1f}" cy="{cy + 7 * math.sin(a):.1f}" r="6" fill="{accent}"/>'
            flowers += f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="#FFD43B"/>'
        return band("#8CCB7E") + flowers
    if kind == "하트 머리띠":   # 머리띠 위로 용수철 더듬이 + 하트
        out = band(dark)
        for x, side in ((100, -1), (140, 1)):
            out += (f'<path d="M{x},76 Q{x + side * 10},56 {x + side * 4},36" stroke="{dark}" '
                    'stroke-width="2.5" fill="none" stroke-linecap="round"/>')
            out += _heart(x + side * 4, 24, accent)
        return out
    if kind == "베레모":
        return (f'<ellipse cx="108" cy="72" rx="56" ry="20" fill="{accent}" transform="rotate(-10 108 72)"/>'
                f'<rect x="104" y="46" width="6" height="10" rx="3" fill="{dark}"/>')
    if kind == "비니":
        return (f'<path d="M50,112 C50,42 190,42 190,112 Z" fill="{accent}"/>'
                f'<rect x="48" y="98" width="144" height="18" rx="9" fill="{dark}"/>'
                f'<circle cx="120" cy="46" r="14" fill="#FFFFFF" stroke="{dark}" stroke-width="2"/>')
    return ""


def _glasses(kind):
    if kind == "동그란 안경":
        return ("".join(f'<circle cx="{x}" cy="{EYE_Y}" r="16" fill="#FFFFFF" fill-opacity="0.15" '
                        'stroke="#3A3A3A" stroke-width="3"/>' for x in EYE_X)
                + f'<path d="M112,{EYE_Y} Q120,{EYE_Y - 5} 128,{EYE_Y}" stroke="#3A3A3A" stroke-width="3" fill="none"/>')
    if kind == "선글라스":
        return ("".join(f'<rect x="{x - 18}" y="{EYE_Y - 12}" width="36" height="24" rx="11" fill="#2B2B2B"/>'
                        f'<path d="M{x - 10},{EYE_Y - 5} L{x - 2},{EYE_Y - 5}" stroke="#FFFFFF" stroke-opacity="0.6" '
                        'stroke-width="3" stroke-linecap="round"/>' for x in EYE_X)
                + f'<path d="M114,{EYE_Y - 4} L126,{EYE_Y - 4}" stroke="#2B2B2B" stroke-width="4"/>')
    return ""


def _neckwear(kind, accent):
    dark = _dark(accent, 0.2)
    if kind == "나비넥타이":
        return (f'<path d="M120,210 L103,201 L103,219 Z M120,210 L137,201 L137,219 Z" fill="{accent}" '
                f'stroke="{dark}" stroke-width="1.5" stroke-linejoin="round"/><circle cx="120" cy="210" r="4.5" fill="{dark}"/>')
    if kind == "스카프":
        return (f'<path d="M86,202 Q120,222 154,202 L154,212 Q120,234 86,212 Z" fill="{accent}"/>'
                f'<path d="M128,216 L142,248 L131,252 L119,220 Z" fill="{dark}"/>')
    return ""


def _aging(age, has_glasses):
    """45세부터 흰 눈썹, 60세부터 돋보기 안경 (원래 안경이 없을 때만)"""
    out = ""
    if age >= 45:
        out += "".join(f'<path d="M{x - 9},{EYE_Y - 20} Q{x},{EYE_Y - 25} {x + 9},{EYE_Y - 20}" stroke="#E9E9E9" '
                       'stroke-width="4.5" fill="none" stroke-linecap="round"/>' for x in EYE_X)
    if age >= 60 and not has_glasses:
        out += ("".join(f'<path d="M{x - 15},{EYE_Y + 2} Q{x},{EYE_Y + 20} {x + 15},{EYE_Y + 2} Z" fill="#FFFFFF" '
                        'fill-opacity="0.2" stroke="#B08D57" stroke-width="2.5"/>' for x in EYE_X)
                + f'<path d="M111,{EYE_Y + 3} L129,{EYE_Y + 3}" stroke="#B08D57" stroke-width="2.5"/>')
    return out


def _coin(cx, cy, r=10):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{GOLD}" stroke="#C98A0B" stroke-width="1.8"/>'
            f'<text x="{cx}" y="{cy + r * 0.38:.1f}" font-size="{r * 1.1:.0f}" text-anchor="middle" '
            'font-weight="bold" fill="#A86B00" font-family="sans-serif">₩</text>')


def _riches(level):
    """부자 아이템: 1 동전 → 2 돼지 저금통 → 3 돈주머니 → 4 금목걸이·동전 더미"""
    out = ""
    if level >= 1:
        out += _coin(214, 264)
    if level >= 2:   # 돼지 저금통
        out += ('<ellipse cx="208" cy="236" rx="22" ry="16" fill="#FFB3C7" stroke="#F28AA8" stroke-width="2"/>'
                '<path d="M196,224 L200,214 L206,224 Z" fill="#FFB3C7" stroke="#F28AA8" stroke-width="1.5"/>'
                '<ellipse cx="229" cy="238" rx="6" ry="5" fill="#FF9AB5" stroke="#F28AA8" stroke-width="1.5"/>'
                '<circle cx="216" cy="232" r="2" fill="#5A3A3A"/>'
                '<rect x="200" y="221" width="12" height="3" rx="1.5" fill="#E07A98"/>')
    if level >= 3:   # 돈주머니
        out += ('<path d="M18,274 Q10,246 28,236 L24,226 L44,226 L40,236 Q58,246 50,274 Z" fill="#D9A441" '
                'stroke="#B07A1F" stroke-width="2"/><path d="M24,232 L44,232" stroke="#8C5E14" stroke-width="3"/>'
                '<text x="34" y="262" font-size="16" text-anchor="middle" font-weight="bold" fill="#7A4E0B" '
                'font-family="sans-serif">₩</text>')
    if level >= 4:   # 금목걸이
        out += f'<path d="M96,208 Q120,240 144,208" stroke="{GOLD}" stroke-width="4" fill="none"/>' + _coin(120, 230, 8)
    return out


def _crown():
    return ('<g transform="translate(0,14)">'
            f'<path d="M86,44 L94,16 L107,34 L120,8 L133,34 L146,16 L154,44 Z" fill="{GOLD}" '
            'stroke="#C98A0B" stroke-width="2" stroke-linejoin="round"/>'
            '<circle cx="120" cy="30" r="4" fill="#E64980"/><circle cx="100" cy="36" r="3" fill="#4C6FFF"/>'
            '<circle cx="140" cy="36" r="3" fill="#12B886"/></g>')


# ---------------------------------------------------------------
# 4. 전체 캐릭터 그리기
# ---------------------------------------------------------------
def draw(look: dict, age: int, level: int, size: int = 240) -> str:
    """꾸미기 정보(look), 나이(age), 자산 단계(level)로 캐릭터 SVG 문자열을 만든다."""
    look = {**DEFAULT_LOOK, **(look or {})}
    if look["animal"] not in ANIMALS:          # 예전 사람 캐릭터 정보가 남아 있으면 기본 동물로
        look["animal"] = DEFAULT_LOOK["animal"]
    level = max(0, min(int(level), 5))
    animal = look["animal"]
    fur = _mix(fur_color(look), "#FFFFFF", age_soften(age))   # 나이가 들면 털이 살짝 연해짐
    line = "#C9C9C9" if animal == "판다" else _dark(fur, 0.22)
    outfit_svg, arm_color = _outfit(look.get("outfit"), look.get("cloth") or DEFAULT_LOOK["cloth"])
    accent = look.get("accent") or DEFAULT_LOOK["accent"]

    parts = [
        _defs(fur, level),
        _background(level),
        _ears(animal, fur, line),
        f'<path d="{BODY}" fill="{fur}" stroke="{line}" stroke-width="2.5"/>',   # 몸
        outfit_svg,
        _arms(arm_color, fur, line),
        _neckwear(look.get("neck"), accent),
        f'<ellipse cx="120" cy="128" rx="72" ry="64" fill="url(#fur)" stroke="{line}" stroke-width="2.5"/>',  # 얼굴
    ]
    if animal == "햄스터":
        parts.append(_hamster_cheeks())
    parts.append(_face_marks(animal, fur))
    if animal == "강아지":
        parts.append(_dog_ears(fur, line))
    if look.get("cheek"):
        parts.append('<ellipse cx="76" cy="160" rx="14" ry="9" fill="url(#blush)"/>'
                     '<ellipse cx="164" cy="160" rx="14" ry="9" fill="url(#blush)"/>')
    parts += [
        _eyes(look.get("eyes")),
        _nose_mouth(animal),
        _glasses(look.get("glasses")),
        _aging(age, look.get("glasses") not in (None, "없음")),
        _headwear(look.get("head"), accent),
        _riches(level),
    ]
    if level >= 5:
        parts.append(_crown())

    height = round(size * 280 / 240)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 280" '
            f'width="{size}" height="{height}">' + "".join(parts) + "</svg>")
