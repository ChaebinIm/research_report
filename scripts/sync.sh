#!/usr/bin/env bash
# =============================================================
#  research_report 동기화 헬퍼
#  - 레포 루트(이 스크립트가 있는 폴더)의 모든 변경을 커밋·푸시한다.
#
#  사용법:
#    ./sync.sh                       # 커밋 메시지 자동 생성(날짜+파일명)
#    ./sync.sh "상시공부: C50 WACC"   # 커밋 메시지 직접 지정
#
#  준비(최초 1회):
#    chmod +x sync.sh
#  ※ 인증은 로컬 git 자격증명(깃 로그인/자격증명 관리자)을 사용한다.
#     이 스크립트에 토큰을 절대 적어 넣지 말 것(레포에 새어 나감).
# =============================================================
set -euo pipefail

# 스크립트가 놓인 폴더(=레포 루트)로 이동 → 어디서 실행해도 동작
cd "$(dirname "$0")"

# git 레포인지 확인
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "❌ 여기는 git 저장소가 아닙니다. research_report 폴더 안에 두고 실행하세요."
  exit 1
fi

# 변경사항 스테이징
git add -A

# 올릴 변경이 없으면 조용히 종료
if git diff --cached --quiet; then
  echo "✅ 변경된 파일이 없습니다. 올릴 내용이 없어요."
  exit 0
fi

# 커밋 메시지 결정
if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
  MSG="$1"
else
  FILES=$(git diff --cached --name-only | sed 's#.*/##' | paste -sd', ' -)
  MSG="자료 업데이트 $(date +%F): ${FILES}"
fi

echo "📝 커밋 메시지: ${MSG}"
git commit -m "${MSG}"

echo "⬆️  푸시 중..."
git push

echo "🎉 완료! GitHub(ChaebinIm/research_report)에 반영됐습니다."
