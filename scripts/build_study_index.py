#!/usr/bin/env python3
"""
연재 공부(일일공부 D · 상시공부 C · 지정학 G) 정리 스크립트.

새 회차 파일을 넣은 뒤 한 번 돌리면:
  1) 본문의 [[D42]] · [[C50 WACC]] 같은 위키링크를 GitHub에서 눌리는 상대경로 링크로 바꾸고
  2) 각 파일 맨 아래에 '이전 / 목록 / 다음' 내비게이션을 달고
  3) 일일공부/README.md · 일일공부/상시공부/README.md · 지정학/README.md 인덱스를 새로 만든다.

파일 위치·이름은 건드리지 않는다(자동화가 이 경로에 파일을 추가하므로).
여러 번 돌려도 결과가 같다(idempotent). 아직 파일이 없는 회차를 가리키는 [[..]]는 그대로 남겨 두었다가,
그 파일이 들어온 뒤 다시 돌리면 자동으로 링크가 된다.

사용법:  python3 scripts/build_study_index.py
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D_DIR = "일일공부"
C_DIR = "일일공부/상시공부"
G_DIR = "지정학"

FNAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_([DCG])(\d{2,3})_(.+)\.md$")
NAV_START = "<!-- study-nav:start (scripts/build_study_index.py 자동 생성) -->"
NAV_END = "<!-- study-nav:end -->"
AUTOGEN = "> 🤖 이 문서는 `scripts/build_study_index.py`가 자동 생성합니다. 직접 고치지 말고 스크립트를 다시 돌리세요."

# ── 일일공부 모듈 (파일명 세 번째 토큰 → 모듈 정보). 새 토큰이 나오면 자동으로 뒤에 붙는다.
D_MODULES = {
    "반도체": ("💾", "반도체", ["반도체/"]),
    "2차전지": ("🔋", "2차전지", ["2차전지/"]),
    "전력기기": ("⚡", "AI 인프라 · 전력기기", ["전력기기/", "AI인프라/"]),
    "조선": ("🚢", "조선", ["조선및기자재/"]),
    "방산": ("🛡️", "방산", ["방산/"]),
    "바이오": ("💊", "바이오", ["바이오및제약/"]),
    "자동차": ("🚗", "자동차 · 모빌리티", ["자동차및모빌리티/"]),
    "원자력SMR": ("⚛️", "원자력 · SMR", ["원자력및SMR/"]),
}

# ── 상시공부 카테고리
C_CATEGORIES = {
    "개념": ("🧠", "개념 — 투자 사고의 도구", "회계·밸류에이션·리스크·사이클 등 어디에나 쓰는 프레임"),
    "산업": ("🏭", "산업 — 업종별 돈 버는 구조", "산업마다 다른 '이익이 생기는 지점'과 사이클"),
    "종목": ("🏢", "종목 — 기업 유형의 문법", "지주사·컴파운더·특수상황 등 기업 '유형'별 읽는 법"),
    "지정학": ("🌐", "지정학 — 구조적 테마", "초크포인트·자원·통화 등 장기 구조 (사건 브리핑은 지정학/ 폴더)"),
}
C_DEFAULT_CATEGORY = {1: "종목"}  # 파일명에 카테고리 토큰이 없는 회차

# ── 지정학 테마 (회차 번호 → 테마). 목록에 없는 G48 이후 회차는 '역사 사건' 트랙으로 본다.
G_THEMES = [
    ("history", "🏛️", "역사 사건 → 오늘의 시장 교훈", "G48~ 트랙: 과거 충격 1건을 해부해 '반영 vs 미반영' 메커니즘과 오늘의 판박이를 찾는다"),
    ("mideast", "🛢️", "중동 · 호르무즈 (이란 전쟁 연작)", "2026년 7~8월 이란 전쟁 국면을 따라간 연속 브리핑 — 순서대로 읽으면 한 편의 드라마"),
    ("oil", "⛽", "원유 · 가스 공급망 (중동 외)", "베네수엘라·리비아·모잠비크 — 정권과 내전이 원유·LNG 흐름을 바꾸는 법"),
    ("mineral", "⛏️", "핵심광물 · 자원 무기화", "희토류·리튬·니켈·코발트·우라늄·보크사이트 — 병목은 광산이 아니라 제련소에 있다"),
    ("conflict", "⚔️", "분쟁 · 안보 · 회랑", "전쟁과 국경, 새로 뚫리는 물류 회랑"),
    ("water", "💧", "물 · 식량 무기화", "강물과 곡물이 무기가 될 때"),
    ("tech", "💻", "기술 패권", "미·중 반도체 전쟁"),
]
G_THEME_OF = {
    **{n: "mideast" for n in (1, 2, 5, 6, 7, 8, 9, 10, 11)},
    **{n: "oil" for n in (13, 20, 26, 31, 38)},
    **{n: "mineral" for n in (12, 14, 16, 19, 21, 27, 28, 30, 32, 33, 36, 39, 40, 41, 43, 44, 45, 46)},
    **{n: "conflict" for n in (4, 15, 17, 18, 22, 24, 29, 35, 47)},
    **{n: "water" for n in (23, 34, 37)},
    3: "tech",
}

# ── 섹터별 이어 읽기 지도: (아이콘, 섹터, 심층리포트 폴더, D모듈 토큰, 파일명 키워드)
SECTOR_MAP = [
    ("💾", "반도체", ["반도체/"], "반도체", ["반도체", "EUV", "패키징", "HBM", "CXMT", "희귀가스", "소부장", "주석"]),
    ("🔋", "2차전지 · 배터리 소재", ["2차전지/"], "2차전지", ["2차전지", "리튬", "니켈", "코발트", "흑연", "배터리"]),
    ("⚡", "전력 · AI 인프라", ["전력기기/", "AI인프라/"], "전력기기", ["전력", "데이터센터", "해저케이블", "구리", "산업가스"]),
    ("🚢", "조선 · 해운", ["조선및기자재/", "항공해운및물류/"], "조선", ["조선", "해운", "수주산업", "북극항로", "초크포인트의"]),
    ("🛡️", "방산 · 우주", ["방산/", "우주및위성/"], "방산", ["방산", "NATO", "유럽안보", "우주", "텅스텐"]),
    ("💊", "바이오 · 제약", ["바이오및제약/"], "바이오", ["바이오", "제약", "의약품"]),
    ("🚗", "자동차 · 모빌리티", ["자동차및모빌리티/"], "자동차", ["자동차"]),
    ("⚛️", "원자력 · SMR", ["원자력및SMR/"], "원자력SMR", ["원자력", "우라늄", "SMR"]),
    ("🛢️", "에너지 · 원유 · 정유", ["정유및석유화학/"], None, ["유가", "원유", "석유", "정유", "호르무즈", "이란", "천연가스", "LNG", "1990"]),
    ("🏦", "금융 · 통화 · 매크로", ["금융/", "거시및정책/"], None, ["은행", "보험", "환율", "외환", "통화", "플라자", "닷컴", "버블", "리츠", "기축"]),
    ("🛒", "소비 · 유통 · 플랫폼", ["소비재및K콘텐츠/", "유통및이커머스/", "인터넷및플랫폼/"], None, ["화장품", "리테일", "플랫폼", "구독", "여행", "통신"]),
]

SERIES_README = {"D": f"{D_DIR}/README.md", "C": f"{C_DIR}/README.md", "G": f"{G_DIR}/README.md"}


@dataclass
class Note:
    series: str  # D / C / G
    num: int
    date: str
    token: str  # 파일명 세 번째 토큰(모듈·카테고리·지역)
    path: str  # ROOT 기준 상대경로
    title: str

    @property
    def code(self) -> str:
        return f"{self.series}{self.num:02d}"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def clean_title(h1: str, series: str) -> str:
    t = h1.lstrip("#").strip()
    t = re.sub(r"^\[?[^A-Za-z0-9가-힣\[]*", "", t)  # 앞쪽 이모지·기호
    m = re.search(r"\b[DCG]\d{2,3}\]?", t)
    if m and m.start() < 25:
        t = t[m.end():]
    t = re.sub(r"^\s*[—·:\-–]\s*", "", t).strip()
    if series == "D":
        # "2차전지 ③ ..." / "AI 인프라·전력기기 ② ..." / "자동차·모빌리티 — ..." 같은 모듈 접두어 제거
        t = re.sub(r"^[^—:]{1,20}?[①-⑳]\s*", "", t)
        t = re.sub(r"^\(모듈 \d+ [^)]*\)\s*", "", t)
        t = re.sub(r"^[^—:\"']{1,14}\s—\s", "", t)
    if series == "C":
        t = re.sub(r"^(개념|산업|종목|지정학)\s*—\s*", "", t)
    return t.strip()


def short(t: str, n: int = 95) -> str:
    t = t.replace("|", "／")
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def scan() -> dict[str, list[Note]]:
    notes: dict[str, list[Note]] = {"D": [], "C": [], "G": []}
    for d in (D_DIR, C_DIR, G_DIR):
        for f in sorted(os.listdir(os.path.join(ROOT, d))):
            m = FNAME_RE.match(nfc(f))
            if not m:
                continue
            date, series, num, rest = m.groups()
            token = rest.split("_")[0]
            path = f"{d}/{f}"
            with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
                h1 = next((ln for ln in fh if ln.startswith("# ")), rest)
            notes[series].append(Note(series, int(num), date, token, path, clean_title(h1, series)))
    for s in notes:
        notes[s].sort(key=lambda n: (n.num, n.date))
        seen: dict[int, Note] = {}
        for n in notes[s]:
            if n.num in seen:
                print(f"⚠️  {n.code} 번호 중복: {seen[n.num].path} / {n.path}")
            seen.setdefault(n.num, n)
    return notes


def link(target: str, frm_dir: str) -> str:
    rel = os.path.relpath(target, frm_dir)
    if not rel.startswith("."):
        rel = "./" + rel
    return url_path(rel)


def url_path(p: str) -> str:
    """한글은 그대로 두고(GitHub가 처리), 마크다운 링크를 깨뜨리는 문자만 인코딩."""
    return p.replace("%", "%25").replace(" ", "%20").replace("(", "%28").replace(")", "%29")


def missing_numbers(ns: list[Note]) -> list[str]:
    have = {n.num for n in ns}
    if not have:
        return []
    return [f"{ns[0].series}{i:02d}" for i in range(1, max(have) + 1) if i not in have]


# ─────────────────────────────── 1) 위키링크 → 상대경로 링크
WIKI_RE = re.compile(r"\[\[([^\]\n]{1,80})\]\]")
CODE_IN_WIKI = re.compile(r"(?<![A-Za-z])([DCG])(\d{2,3})(?!\d)")


def convert_wikilinks(text: str, frm_dir: str, by_code: dict[str, Note]) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        inner = m.group(1)
        if inner.startswith("모듈"):
            count += 1
            return f"[{inner}]({link(SERIES_README['D'], frm_dir)})"
        cm = CODE_IN_WIKI.search(inner)
        if not cm:
            return m.group(0)
        note = by_code.get(f"{cm.group(1)}{int(cm.group(2)):02d}")
        if not note:
            return m.group(0)  # 아직 저장소에 없는 회차 → 들어오면 다음 실행 때 연결
        count += 1
        label = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", inner).replace("_", " ")
        return f"[{label}]({link(note.path, frm_dir)})"

    return WIKI_RE.sub(repl, text), count


# ─────────────────────────────── 2) 이전 / 목록 / 다음 내비게이션
def nav_block(n: Note, prev: Note | None, nxt: Note | None) -> str:
    frm = os.path.dirname(n.path)
    parts = [f"⬅️ 이전 [{prev.code} · {short(prev.title, 40)}]({link(prev.path, frm)})" if prev else "⬅️ 이전 없음"]
    parts.append(f"📚 [{ {'D': '일일공부', 'C': '상시공부', 'G': '지정학'}[n.series] } 목록]({link(SERIES_README[n.series], frm)})")
    parts.append(f"[{nxt.code} · {short(nxt.title, 40)}]({link(nxt.path, frm)}) 다음 ➡️" if nxt else "다음 회차 준비 중 ➡️")
    return f"{NAV_START}\n\n---\n\n{' &nbsp;|&nbsp; '.join(parts)}\n\n{NAV_END}\n"


def process_notes(notes: dict[str, list[Note]]) -> None:
    by_code = {n.code: n for s in notes.values() for n in reversed(s)}  # 중복 시 앞 번호 파일 우선
    total_links = 0
    for s, ns in notes.items():
        for i, n in enumerate(ns):
            p = os.path.join(ROOT, n.path)
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            orig = text
            text = re.sub(re.escape(NAV_START) + r".*?" + re.escape(NAV_END) + r"\n?", "", text, flags=re.S).rstrip() + "\n"
            text, c = convert_wikilinks(text, os.path.dirname(n.path), by_code)
            total_links += c
            prev = ns[i - 1] if i > 0 else None
            nxt = ns[i + 1] if i + 1 < len(ns) else None
            text = text + "\n" + nav_block(n, prev, nxt)
            if text != orig:
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
    print(f"🔗 위키링크 변환 {total_links}개")


# ─────────────────────────────── 3) 인덱스 README
def table(ns: list[Note], frm: str, with_token: bool = False) -> list[str]:
    head = "| # | 날짜 | 주제 |" + (" 지역·키워드 |" if with_token else "")
    sep = "|---|---|---|" + ("---|" if with_token else "")
    rows = [head, sep]
    for n in ns:
        row = f"| **{n.code}** | {n.date[5:]} | [{short(n.title)}]({link(n.path, frm)}) |"
        if with_token:
            row += f" {n.token} |"
        rows.append(row)
    return rows


def sector_rows(notes: dict[str, list[Note]], frm: str) -> list[str]:
    out = ["| 섹터 | 📖 일일공부 (D) | 🧩 상시공부 (C) | 🌐 지정학 (G) | 📂 심층 리포트 |", "|---|---|---|---|---|"]

    def refs(ns: list[Note]) -> str:
        return " ".join(f"[{n.code}]({link(n.path, frm)})" for n in ns) or "—"

    for icon, name, folders, dtok, kws in SECTOR_MAP:
        ds = [n for n in notes["D"] if n.token == dtok]
        if ds:
            dcell = f"[{ds[0].code}~{ds[-1].code}]({link(SERIES_README['D'], frm)}#{anchor_of_module(dtok)}) ({len(ds)}편)"
        else:
            dcell = "—"
        hit = lambda n: any(k in nfc(os.path.basename(n.path)) for k in kws)  # noqa: E731
        cs = [n for n in notes["C"] if hit(n)]
        gs = [n for n in notes["G"] if hit(n)]
        fcell = " ".join(f"[`{f}`]({link(f, frm)})" for f in folders if os.path.isdir(os.path.join(ROOT, f)))
        out.append(f"| {icon} **{name}** | {dcell} | {refs(cs)} | {refs(gs)} | {fcell} |")
    return out


def gh_anchor(heading: str) -> str:
    """GitHub 헤딩 앵커 규칙: 소문자 → 글자·숫자·공백·하이픈 외 제거 → 공백을 하이픈으로."""
    a = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
    return url_path(a)


def module_heading(tok: str) -> str:
    icon, name, _ = D_MODULES.get(tok, ("📘", tok, []))
    return f"{icon} 모듈 {list(module_order).index(tok) + 1} — {name}"


def anchor_of_module(tok: str) -> str:
    return gh_anchor(module_heading(tok))


module_order: dict[str, None] = {}


def build_d_readme(notes: dict[str, list[Note]]) -> str:
    frm = D_DIR
    ds, cs, gs = notes["D"], notes["C"], notes["G"]
    for n in ds:
        module_order.setdefault(n.token, None)
    L = [
        "# 📚 공부 아카이브 — 일일공부 · 상시공부 · 지정학",
        "",
        AUTOGEN,
        "",
        "시황이 아니라 **재사용 가능한 지식·프레임**을 쌓는 세 개의 연재입니다. 파일은 날짜순으로 쌓이지만,",
        "**읽을 때는 아래처럼 '모듈 · 카테고리 · 테마'로 묶어서** 보면 됩니다. 각 글 맨 아래에 이전/다음 링크가 있어 순서대로 넘겨 읽을 수 있어요.",
        "",
        "| 연재 | 무엇을 쌓나 | 분량 | 바로가기 |",
        "|---|---|---|---|",
        f"| 📖 **일일공부 (D)** | 섹터 하나를 8~10편 모듈로 정복 — 구조 → 밸류체인 → 밸류에이션 | {len(ds)}편 · {len(module_order)}개 모듈 | [모듈별 목록 ↓](#{gh_anchor('📖 일일공부 (D) — 섹터 모듈')}) |",
        f"| 🧩 **상시공부 (C)** | 개념 · 산업 · 종목유형 · 지정학을 번갈아 — 어디에나 쓰는 사고 도구 | {len(cs)}편 | [상시공부 목록](./상시공부/README.md) |",
        f"| 🌐 **지정학 (G)** | 지역 · 자원 · 역사 사건 브리핑 — 뉴스가 시장에 '얼마나 반영됐나' | {len(gs)}편 | [지정학 목록](../지정학/README.md) |",
        "",
        "---",
        "",
        "## 🧭 섹터별로 이어 읽기",
        "",
        "한 섹터를 공부할 때 세 연재 + 기존 심층 리포트를 한 줄로 모아 봤습니다. (C·G는 파일명 키워드로 자동 매칭)",
        "",
        "<div style=\"overflow-x:auto\">",
        "",
        *sector_rows(notes, frm),
        "",
        "</div>",
        "",
        "> 💡 **추천 순서**: 상시공부 개념편(🧠)으로 도구를 먼저 챙기고 → 일일공부 모듈을 오프너부터 종합편까지 → 같은 섹터의 지정학·심층 리포트로 확장.",
        "",
        "---",
        "",
        "## 📖 일일공부 (D) — 섹터 모듈",
        "",
        "각 모듈은 **오프너(산업 지도) → 밸류체인 각 마디 → 종합·밸류에이션편** 순서입니다. 마지막 '종합편'만 읽어도 모듈의 뼈대가 잡혀요.",
        "",
    ]
    for idx, tok in enumerate(module_order, 1):
        folders = D_MODULES.get(tok, ("📘", tok, []))[2]
        mns = [n for n in ds if n.token == tok]
        L.append(f"### {module_heading(tok)}")
        L.append("")
        fl = " · ".join(f"[`{f}`]({link(f, frm)})" for f in folders if os.path.isdir(os.path.join(ROOT, f)))
        L.append(f"{mns[0].code}~{mns[-1].code} · {len(mns)}편 · {mns[0].date} ~ {mns[-1].date}" + (f" · 심층 리포트: {fl}" if fl else ""))
        L.append("")
        L += table(mns, frm)
        L.append("")
    miss = missing_numbers(ds)
    if miss:
        L += [f"> 🕳️ 저장소에 본문이 없는 회차: {', '.join(miss)} — 파일이 들어오면 자동으로 목록·링크에 반영됩니다.", ""]
    L += [
        "---",
        "",
        "## 📖 학습법",
        "- 하루 10~15분, 개념 프레임을 먼저 잡고 → 대표 종목에 대입.",
        "- 모듈 종합편은 '이 섹터를 언제 사고 언제 파나'의 체크리스트 — 복습용으로 가장 좋습니다.",
        "- 본문의 `D42`·`C50` 같은 교차참조는 링크로 연결돼 있어, 모르는 개념이 나오면 바로 따라가 읽으면 됩니다.",
        "",
        "## 🛠 새 회차를 넣은 뒤",
        "```bash",
        "python3 scripts/build_study_index.py   # 목록·이전/다음·교차링크 갱신",
        "```",
        "",
    ]
    return "\n".join(L)


def build_c_readme(notes: dict[str, list[Note]]) -> str:
    frm = C_DIR
    cs = notes["C"]
    cat = lambda n: n.token if n.token in C_CATEGORIES else C_DEFAULT_CATEGORY.get(n.num, "기타")  # noqa: E731
    L = [
        "# 🧩 상시공부 (C 시리즈)",
        "",
        AUTOGEN,
        "",
        f"개념 · 산업 · 종목유형 · 지정학을 번갈아 다루는 **사고 도구** 모음 — {len(cs)}편. ",
        "어떤 섹터를 보든 다시 꺼내 쓰는 프레임이라, 일일공부(D)·지정학(G) 본문에서 `C18` `C50`처럼 자주 인용됩니다.",
        "",
        "← [공부 아카이브 홈](../README.md) · [지정학](../../지정학/README.md) · 번호 운영 기준: [`_상시공부-인덱스.md`](./_상시공부-인덱스.md)",
        "",
        "| 카테고리 | 편수 |",
        "|---|---|",
    ]
    for key, (icon, name, _) in C_CATEGORIES.items():
        L.append(f"| {icon} [{name}](#{gh_anchor(f'{icon} {name}')}) | {sum(cat(n) == key for n in cs)} |")
    L.append("")
    for key, (icon, name, desc) in C_CATEGORIES.items():
        ns = [n for n in cs if cat(n) == key]
        if not ns:
            continue
        L += ["---", "", f"## {icon} {name}", "", f"_{desc}_", "", *table(ns, frm), ""]
    others = [n for n in cs if cat(n) not in C_CATEGORIES]
    if others:
        L += ["## 기타", "", *table(others, frm), ""]
    miss = missing_numbers(cs)
    if miss:
        L += [f"> 🕳️ 저장소에 본문이 없는 회차: {', '.join(miss)}", ""]
    return "\n".join(L)


def build_g_readme(notes: dict[str, list[Note]]) -> str:
    frm = G_DIR
    gs = notes["G"]
    theme = lambda n: G_THEME_OF.get(n.num, "history" if n.num >= 48 else "conflict")  # noqa: E731
    L = [
        "# 🌐 지정학 (G 시리즈)",
        "",
        AUTOGEN,
        "",
        f"지역 · 자원 · 역사 사건 브리핑 {len(gs)}편. 핵심 질문은 늘 하나 — **\"이 사건은 시장에 얼마나 반영됐나, 과잉인가 미반영인가?\"**",
        "",
        "← [공부 아카이브 홈](../일일공부/README.md) · [상시공부](../일일공부/상시공부/README.md) · 트랙 운영 지침: [`_트랙-가이드.md`](./_트랙-가이드.md)",
        "",
        "| 테마 | 편수 | 한 줄 |",
        "|---|---|---|",
    ]
    for key, icon, name, desc in G_THEMES:
        c = sum(theme(n) == key for n in gs)
        if c:
            L.append(f"| {icon} [{name}](#{gh_anchor(f'{icon} {name}')}) | {c} | {desc} |")
    L.append("")
    for key, icon, name, desc in G_THEMES:
        ns = [n for n in gs if theme(n) == key]
        if not ns:
            continue
        L += ["---", "", f"## {icon} {name}", "", f"_{desc}_", "", *table(ns, frm, with_token=True), ""]
    refs = sorted(f for f in os.listdir(os.path.join(ROOT, G_DIR)) if nfc(f).startswith("참고_"))
    if refs:
        L += ["---", "", "## 📎 참고 배경지식", ""]
        L += [f"- [{nfc(f)[3:-3].replace('_', ' ')}]({link(f'{G_DIR}/{f}', frm)})" for f in refs]
        L.append("")
    miss = missing_numbers(gs)
    if miss:
        L += [
            f"> 🕳️ 저장소에 본문이 없는 회차: {', '.join(miss)} — 일부는 클라우드 프로젝트 용량 문제로 채팅으로만 전달됐습니다(요약은 [`_트랙-가이드.md`](./_트랙-가이드.md) 완료 목록 참고).",
            "",
        ]
    return "\n".join(L)


def main() -> None:
    notes = scan()
    print(f"📄 D {len(notes['D'])} · C {len(notes['C'])} · G {len(notes['G'])}")
    process_notes(notes)
    for path, content in (
        (SERIES_README["D"], build_d_readme(notes)),
        (SERIES_README["C"], build_c_readme(notes)),
        (SERIES_README["G"], build_g_readme(notes)),
    ):
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"📝 {path}")


if __name__ == "__main__":
    main()
