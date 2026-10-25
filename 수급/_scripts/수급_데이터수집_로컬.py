# -*- coding: utf-8 -*-
"""
수급 데이터 수집 (로컬 맥북 실행 · pykrx)
- KRX 공식 데이터를 투자자 세부유형 × 시장 × 기간별로 종목 순매수 수집
- ★ 호출량 조절: 호출 간 딜레이(RATE_SLEEP) + 실패 시 지수 백오프 재시도
- 결과 CSV를 research_report 리포에 커밋/푸시 → 클라우드가 이어받아 분석·리포트

사전 준비:
  pip install pykrx pandas
  (혹시 데이터가 비면) 무료 KRX 계정으로 환경변수: export KRX_ID=... KRX_PW=...

실행: python3 수급_데이터수집_로컬.py
"""
import os, sys, time, datetime, subprocess
import pandas as pd
from pykrx import stock

# ── 설정 ─────────────────────────────────────────────
REPO_DIR = os.path.expanduser("~/Desktop/python_projects/research_report")
RATE_SLEEP = 0.8          # ★ 호출 간 최소 딜레이(초) — KRX 부담 완화
MAX_RETRY  = 3            # 실패 시 재시도 횟수
BACKOFF    = 2.0          # 지수 백오프 배수
MARKETS    = ["KOSPI", "KOSDAQ"]
INVESTORS  = ["외국인", "기관합계", "연기금", "금융투자", "투신",
              "보험", "사모", "은행", "기타금융", "개인"]
WINDOWS    = {"1주": 7, "2주": 14, "1달": 31, "3달": 93}   # 캘린더일

def latest_bday():
    return stock.get_nearest_business_day_in_a_week()  # YYYYMMDD

def fetch_one(fromdate, todate, market, investor):
    """호출 1건 + 재시도/백오프."""
    delay = RATE_SLEEP
    for attempt in range(1, MAX_RETRY + 1):
        try:
            df = stock.get_market_net_purchases_of_equities_by_ticker(
                fromdate, todate, market, investor)
            return df
        except Exception as e:
            if attempt == MAX_RETRY:
                print(f"  ! 실패({market}/{investor}) {e} — 건너뜀")
                return None
            wait = delay * (BACKOFF ** (attempt - 1))
            print(f"  … 재시도 {attempt}/{MAX_RETRY} ({wait:.1f}s): {e}")
            time.sleep(wait)

def collect():
    todate = latest_bday()
    td = datetime.datetime.strptime(todate, "%Y%m%d").date()
    iso = td.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    rows = []
    ncall = 0
    for market in MARKETS:
        for win, days in WINDOWS.items():
            fromdate = (td - datetime.timedelta(days=days)).strftime("%Y%m%d")
            for inv in INVESTORS:
                ncall += 1
                print(f"[{ncall}] {market} · {inv} · {win} ({fromdate}~{todate})")
                df = fetch_one(fromdate, todate, market, inv)
                time.sleep(RATE_SLEEP)                 # ★ 매 호출 후 딜레이
                if df is None or df.empty:
                    continue
                df = df.reset_index()  # 티커가 인덱스
                tick_col = df.columns[0]
                for _, r in df.iterrows():
                    rows.append({
                        "기준일": todate, "market": market, "investor": inv, "window": win,
                        "티커": str(r[tick_col]).zfill(6), "종목명": r.get("종목명", ""),
                        "순매수거래대금": int(r.get("순매수거래대금", 0)),
                        "순매수거래량": int(r.get("순매수거래량", 0)),
                    })
    out = pd.DataFrame(rows)
    return week, todate, out

def git(*args):
    return subprocess.run(["git", "-C", REPO_DIR, *args],
                          capture_output=True, text=True)

def main():
    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        print("리포 경로 확인:", REPO_DIR); sys.exit(1)
    week, todate, df = collect()
    if df.empty:
        print("수집 데이터 없음 — KRX 계정(KRX_ID/KRX_PW) 필요할 수 있음. 중단.")
        sys.exit(2)
    outdir = os.path.join(REPO_DIR, "수급", "데이터", week)
    os.makedirs(outdir, exist_ok=True)
    outcsv = os.path.join(outdir, "netbuy_by_ticker.csv")
    df.to_csv(outcsv, index=False, encoding="utf-8-sig")
    print("저장:", outcsv, "| rows:", len(df))
    # git 커밋/푸시 (사용자 로컬 자격증명 사용)
    git("pull", "--rebase")
    git("add", os.path.join("수급", "데이터", week))
    r = git("commit", "-m", f"data: {week} 수급 원자료(KRX/pykrx) 수집")
    print(r.stdout or r.stderr)
    p = git("push")
    print(p.stdout or p.stderr)
    print("완료 — 클라우드 토요일 작업이 이 데이터를 이어받아 리포트를 생성합니다.")

if __name__ == "__main__":
    main()
