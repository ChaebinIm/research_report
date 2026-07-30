# -*- coding: utf-8 -*-
"""
수급 리포트 생성기 (클라우드 실행 · 결정론적)
입력: 수급데이터/<주차>/netbuy_by_ticker.csv  (로컬 pykrx 수집 스크립트가 생성)
출력: 거시및정책 아님 → 수급/주간수급리뷰/<주차>_수급리뷰.md

CSV 스키마(컬럼):
  기준일, market, investor, window, 티커, 종목명, 순매수거래대금, 순매수거래량
  - 순매수거래대금: 원(KRW) 단위 정수(양수=순매수, 음수=순매도)
  - window ∈ {1주, 2주, 1달, 3달}

숫자는 전부 이 스크립트가 pandas로 계산(LLM 산술 배제) → 정확도 보장.
"""
import sys, os
import pandas as pd

WINDOWS = ["1주", "2주", "1달", "3달"]
INVESTORS_MAIN = ["외국인", "기관합계", "개인"]
INVESTORS_INST = ["연기금", "금융투자", "투신", "보험", "사모", "은행", "기타금융"]

# ─────────────────────────────────────────────────────────────
# 세부 섹터 매핑 (최대한 자세히 — 예: 반도체를 메모리/파운드리/소부장/후공정으로 분리)
# 미매핑 티커는 "기타"로. 필요시 계속 추가.
SUBSECTOR = {
    # 반도체 — 메모리
    "005930": "반도체·메모리", "000660": "반도체·메모리",
    # 반도체 — 파운드리/비메모리/팹리스
    "000990": "반도체·비메모리", "240810": "반도체·비메모리", "357780": "반도체·비메모리",
    "108320": "반도체·비메모리", "196490": "반도체·비메모리",
    # 반도체 — 소부장(장비/소재/부품)
    "042700": "반도체·소부장", "240810_x": "반도체·소부장", "058470": "반도체·소부장",
    "140860": "반도체·소부장", "336260": "반도체·소부장", "089030": "반도체·소부장",
    "294870": "반도체·소부장", "005290": "반도체·소부장", "064760": "반도체·소부장",
    "036930": "반도체·소부장", "000660_x": "반도체·소부장",
    # 반도체 — 후공정/패키징/테스트
    "086390": "반도체·후공정", "038460": "반도체·후공정", "046890": "반도체·후공정",
    "093370": "반도체·후공정",
    # 2차전지 — 셀
    "373220": "2차전지·셀", "096770": "2차전지·셀", "006400": "2차전지·셀",
    # 2차전지 — 양극재
    "247540": "2차전지·양극재", "066970": "2차전지·양극재", "003670": "2차전지·양극재",
    "020150": "2차전지·양극재",
    # 2차전지 — 음극재/동박/소재
    "005490_x": "2차전지·소재", "058430": "2차전지·소재", "021240_x": "2차전지·소재",
    # 방산
    "012450": "방산", "047810": "방산", "079550": "방산", "064350": "방산", "272210": "방산",
    # 조선·기자재
    "329180": "조선", "042660": "조선", "010140": "조선", "010620": "조선", "017960": "조선기자재",
    "042700_x": "조선기자재",
    # 전력기기·전선
    "267260": "전력기기", "298040": "전력기기", "010120": "전력기기", "006260": "전력기기",
    "103590": "전력기기", "001440": "전선",
    # 자동차·부품
    "005380": "자동차", "000270": "자동차", "012330": "자동차부품", "018880": "자동차부품",
    "204320": "자동차부품",
    # 바이오·제약
    "207940": "바이오·CDMO", "068270": "바이오·바이오시밀러", "196170": "바이오·신약",
    "302440": "바이오·신약", "326030": "바이오·신약", "000100": "제약", "128940": "제약",
    # 인터넷·플랫폼
    "035420": "인터넷·플랫폼", "035720": "인터넷·플랫폼", "376300": "인터넷·플랫폼",
    # 게임·엔터·콘텐츠
    "036570": "게임", "251270": "게임", "259960": "게임", "352820": "엔터", "041510": "엔터",
    "122870": "엔터",
    # 금융
    "105560": "은행/금융지주", "055550": "은행/금융지주", "086790": "은행/금융지주",
    "316140": "은행/금융지주", "323410": "인터넷은행/핀테크", "377300": "인터넷은행/핀테크",
    "005830": "보험", "032830": "보험", "071050": "증권", "016360": "증권",
    # 철강·소재
    "005490": "철강", "004020": "철강", "010130": "비철금속", "103140": "비철금속",
    # 원자력/SMR
    "034020": "원자력·발전", "052690": "원자력·발전",
    # 로봇
    "108490": "로봇", "056080": "로봇", "454910": "로봇",
    # 통신
    "017670": "통신", "030200": "통신", "032640": "통신",
    # 화학·정유
    "051910": "화학", "011170": "화학", "010950": "정유", "096770_x": "정유",
    # 지주·기타 대형
    "003550": "지주", "034730": "지주", "000880": "지주",
    # 소비재·유통·식품
    "003230": "음식료", "097950": "음식료", "271560": "음식료", "004370": "음식료",
    "282330": "유통", "023530": "유통",
}
def subsector(ticker, name):
    return SUBSECTOR.get(str(ticker), "기타")

# ─────────────────────────────────────────────────────────────
def eok(v):  # 원 → 억원
    return v / 1e8

def bar(v, unit, maxb=14):
    n = min(int(round(abs(v) / unit)), maxb) if unit > 0 else 0
    ch = "█" if v >= 0 else "▒"
    return ch * max(n, 1)

def textbar_block(rows, valcol="억원", namecol="종목명", topn=8):
    """rows: list of (name, value_in_eok). 상위 순매수/하위(순매도) 함께."""
    if not rows:
        return "```\n(데이터 없음)\n```"
    rows = sorted(rows, key=lambda x: x[1], reverse=True)
    top = rows[:topn]
    bot = rows[-topn:] if len(rows) > topn else []
    sel = top + [r for r in bot if r not in top]
    maxabs = max(abs(v) for _, v in sel) or 1
    unit = maxabs / 14
    lines = []
    for name, v in sorted(sel, key=lambda x: x[1], reverse=True):
        lines.append(f"{v:>10,.0f}  {bar(v, unit):<14}  {name}")
    return "```\n" + "\n".join(lines) + "\n```"

def accel_label(net_1w, net_1m):
    """1주 순매수 vs 직전 3주 평균으로 가속/감속 판정."""
    prior3w_avg = (net_1m - net_1w) / 3.0
    if abs(prior3w_avg) < 1e7 and abs(net_1w) < 1e7:
        return "→ 중립"
    if net_1w > prior3w_avg * 1.15:
        return "▲ 가속(순매수 속도↑)" if net_1w >= 0 else "▲ 순매도 완화"
    if net_1w < prior3w_avg * 0.85:
        return "▼ 감속(속도↓)" if net_1w >= 0 else "▼ 순매도 가속"
    return "→ 유지"

# ── 눈에 띄는 변화 자동 감지 (방향전환·급가속) ──────────────────
def weekly_paces(n1, n2, n1m, n3):
    """각 기간을 '주당 순매수 속도'로 환산 (3달=13주, 1달≈4.3주, 1주=1주)."""
    return {"3달": n3 / 13.0, "1달": n1m / 4.3, "1주": float(n1)}

def _detect(pairs, min_eok):
    """pairs: list of (label, {window:net}). 방향전환/급가속 감지."""
    items = []
    for label, nets in pairs:
        n1, n2, n1m, n3 = nets.get("1주", 0), nets.get("2주", 0), nets.get("1달", 0), nets.get("3달", 0)
        prior = (n1m - n1) / 3.0
        rev = (n1 > 0 > n1m) or (n1 < 0 < n1m)
        surge = (n1 * prior > 0) and abs(n1) > max(2 * abs(prior), min_eok * 1e8)
        if (rev and min(abs(eok(n1)), abs(eok(n1m))) > min_eok) or surge:
            kind = "🔄 방향전환" if rev else "⚡ 급가속"
            items.append((abs(eok(n1) - eok(prior)), label, kind, weekly_paces(n1, n2, n1m, n3)))
    items.sort(key=lambda x: -x[0])
    return items

def detect_notable_stocks(df, investors=("외국인", "기관합계"), min_eok=100, topn=6):
    res = []
    for inv in investors:
        sub = df[df.investor == inv]
        pairs = []
        for (tk, nm), g in sub.groupby(["티커", "종목명"]):
            nets = {w: float(g[g.window == w]["순매수거래대금"].sum()) for w in WINDOWS}
            pairs.append((f"{nm} ({inv})", nets))
        res += _detect(pairs, min_eok)
    res.sort(key=lambda x: -x[0])
    return res[:topn]

def detect_notable_sectors(df, investors=("외국인", "기관합계"), min_eok=200, topn=5):
    res = []
    for inv in investors:
        sub = df[df.investor == inv].copy()
        if sub.empty:
            continue
        sub["섹터"] = [subsector(t, n) for t, n in zip(sub["티커"], sub["종목명"])]
        pairs = []
        for sec, g in sub.groupby("섹터"):
            if sec == "기타":
                continue
            nets = {w: float(g[g.window == w]["순매수거래대금"].sum()) for w in WINDOWS}
            pairs.append((f"{sec} ({inv})", nets))
        res += _detect(pairs, min_eok)
    res.sort(key=lambda x: -x[0])
    return res[:topn]

def render_notable(items, empty_msg):
    if not items:
        return [f"*{empty_msg}*"]
    allv = [v for *_, paces in items for v in paces.values()]
    maxabs = max((abs(eok(v)) for v in allv), default=1) or 1
    unit = maxabs / 12
    lines = ["주간 순매수 '속도' 궤적 (억원/주, 위→아래 = 3달→1달→1주)  [█ 순매수 · ▒ 순매도]", ""]
    for score, label, kind, paces in items:
        lines.append(f"- {kind} · **{label}**")
        lines.append("```")
        for hz in ["3달", "1달", "1주"]:
            v = eok(paces[hz])
            lines.append(f"  {hz:<3} {v:>8,.0f}  {bar(v, unit)}")
        lines.append("```")
    return lines

# ─────────────────────────────────────────────────────────────
def build(df):
    base_date = df["기준일"].iloc[0] if len(df) else "?"
    out = []
    out.append(f"# 💧 주간 수급 리뷰 (KRX 실측)\n")
    out.append(f"> **기준일**: {base_date} · 데이터 출처: **KRX 공식(pykrx)** · 계산: 결정론적 스크립트(LLM 산술 배제)")
    out.append(f"> 순매수 = 순매수거래대금(억원), 양수=순매수/음수=순매도. 기간: 1주·2주·1달·3달 누적.\n")

    # 시장 전체 투자자별 순매수 (티커 합산)
    out.append("## 1. 📊 투자자별 시장 순매수 요약 (기간별 누적, 억원)\n")
    out.append("| 투자자 | 1주 | 2주 | 1달 | 3달 | 속도(1주 vs 직전3주평균) |")
    out.append("|---|---:|---:|---:|---:|---|")
    inv_order = INVESTORS_MAIN + INVESTORS_INST
    net_by_inv_win = {}
    for inv in inv_order:
        row = [inv]
        vals = {}
        for w in WINDOWS:
            s = df[(df.investor == inv) & (df.window == w)]["순매수거래대금"].sum()
            vals[w] = s
            row.append(f"{eok(s):,.0f}")
        net_by_inv_win[inv] = vals
        row.append(accel_label(vals.get("1주", 0), vals.get("1달", 0)))
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append("*※ '기관합계'는 아래 세부기관(연기금·금융투자·투신·보험·사모·은행·기타금융)의 합과 일치해야 함 → 검증 노트 참조.*\n")

    # 투자자별 상세 (외국인/기관합계/연기금/개인 등)
    focus = ["외국인", "기관합계", "연기금", "금융투자", "투신", "개인"]
    for inv in focus:
        sub = df[df.investor == inv]
        if sub.empty:
            continue
        out.append(f"\n## 🔎 {inv}\n")
        # 1주 상위/하위 종목
        d1 = sub[sub.window == "1주"]
        rows = [(r["종목명"], eok(r["순매수거래대금"])) for _, r in d1.iterrows()]
        out.append(f"**{inv} · 1주 순매수 상위/하위 종목 (억원)**  [█ 순매수 · ▒ 순매도]")
        out.append(textbar_block(rows, topn=8))
        # 세부섹터 집계 (1주)
        if not d1.empty:
            d1 = d1.copy()
            d1["섹터"] = [subsector(t, n) for t, n in zip(d1["티커"], d1["종목명"])]
            sec = d1.groupby("섹터")["순매수거래대금"].sum().sort_values(ascending=False)
            sec = sec[sec.index != "기타"]
            secrows = [(k, eok(v)) for k, v in sec.items()]
            out.append(f"\n**{inv} · 1주 세부섹터별 순매수 (억원)**")
            out.append(textbar_block(secrows, topn=10))
        # 기간별 누적 + 속도
        vals = net_by_inv_win.get(inv, {})
        out.append(f"\n**{inv} · 기간별 누적 순매수**: "
                   f"1주 {eok(vals.get('1주',0)):,.0f} · 2주 {eok(vals.get('2주',0)):,.0f} · "
                   f"1달 {eok(vals.get('1달',0)):,.0f} · 3달 {eok(vals.get('3달',0)):,.0f} 억원 "
                   f"→ **{accel_label(vals.get('1주',0), vals.get('1달',0))}**")

    # 세부섹터 하이라이트 (외국인+기관합계 1주)
    out.append("\n## 2. 🧩 세부섹터 하이라이트 (외국인·기관 1주, 억원)\n")
    for inv in ["외국인", "기관합계"]:
        d1 = df[(df.investor == inv) & (df.window == "1주")].copy()
        if d1.empty:
            continue
        d1["섹터"] = [subsector(t, n) for t, n in zip(d1["티커"], d1["종목명"])]
        sec = d1.groupby("섹터")["순매수거래대금"].sum().sort_values(ascending=False)
        sec = sec[sec.index != "기타"]
        buy = sec.head(3); sell = sec.tail(3)
        bstr = ", ".join(f"{k} +{eok(v):,.0f}" for k, v in buy.items())
        sstr = ", ".join(f"{k} {eok(v):,.0f}" for k, v in sell.items())
        out.append(f"- **{inv}** — 순매수 상위: {bstr} / 순매도 상위: {sstr}")
    out.append("\n예: 반도체를 **메모리 vs 비메모리 vs 소부장 vs 후공정**으로 분리해 집계 → 같은 '반도체'라도 자금이 어느 하위섹터로 갔는지 구분됩니다.\n")

    # 눈에 띄는 변화 (자동 감지)
    out.append("\n## 3. 🚨 눈에 띄는 변화 (자동 감지: 방향전환·급가속)\n")
    out.append("**종목 단위**")
    out.extend(render_notable(detect_notable_stocks(df), "임계값(±100억)을 넘는 종목 급변 없음."))
    out.append("\n**세부섹터 단위**")
    out.extend(render_notable(detect_notable_sectors(df), "임계값(±200억)을 넘는 섹터 급변 없음."))

    # 검증 노트
    out.append("\n## 🔍 검증 노트\n")
    checks = []
    for w in WINDOWS:
        inst_sum = df[(df.investor.isin(INVESTORS_INST)) & (df.window == w)]["순매수거래대금"].sum()
        inst_total = df[(df.investor == "기관합계") & (df.window == w)]["순매수거래대금"].sum()
        diff = eok(inst_sum - inst_total)
        ok = abs(inst_sum - inst_total) < max(abs(inst_total) * 0.02, 1e8)
        checks.append(f"- {w}: 세부기관 합계 {eok(inst_sum):,.0f} vs 기관합계 {eok(inst_total):,.0f} (차이 {diff:,.0f}억) → {'✅ 일치' if ok else '⚠️ 불일치 — 데이터 재확인'}")
    out.append("**세부기관 합 = 기관합계 정합성 체크** (억원)")
    out.extend(checks)
    out.append("\n*이 리포트는 KRX 공식 데이터를 결정론적 스크립트로 집계한 것이며, 투자 권유가 아닙니다.*")
    return "\n".join(out)

def main():
    csv = sys.argv[1] if len(sys.argv) > 1 else "netbuy_by_ticker.csv"
    outp = sys.argv[2] if len(sys.argv) > 2 else "수급리뷰.md"
    df = pd.read_csv(csv, dtype={"티커": str})
    df["순매수거래대금"] = pd.to_numeric(df["순매수거래대금"], errors="coerce").fillna(0)
    md = build(df)
    with open(outp, "w", encoding="utf-8") as f:
        f.write(md)
    print("생성 완료:", outp, "| rows:", len(df))

if __name__ == "__main__":
    main()
