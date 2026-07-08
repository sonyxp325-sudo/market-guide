# 주식 모니터링 체크리스트 (Phase 1)

`watchlist.json`(내 논리·설정) + pykrx/yfinance(데이터) → `checklist.output.json`(B카드 출력).
매일 장 마감 후 GitHub Action이 자동 실행 → 결과를 커밋. 그 raw URL을 Claude에게 주면 판정·해설.

## 파일 구성
- `watchlist.json` — 종목 등록 + 투자 논리 아카이브(입력). 논리 필드는 전부 선택.
- `build_checklist.py` — 데이터 수집·지표 계산·신호등·확신도·진정 체크리스트 → 출력 생성.
- `checklist.output.json` — 매일 생성되는 결과(B카드). (예시: `checklist.output.example.json`)
- `.github/workflows/checklist.yml` — 자동 실행 스케줄.
- `requirements.txt` — 의존성.

## 로컬 실행
```bash
pip install -r requirements.txt
python build_checklist.py         # -> checklist.output.json 생성
```

## 자동화 (GitHub)
1. 이 파일들을 레포(예: market-guide)에 넣고 push.
2. Actions 탭에서 `daily-checklist` 활성화. `Run workflow`로 수동 테스트.
3. 스케줄: 한국장 마감(06:40 UTC) + 미국장 마감(21:30 UTC) 자동 실행.
   - cron은 UTC이고 GitHub 부하로 수 분~수십 분 지연될 수 있음(중장기엔 무관).
   - 겨울(미국 표준시)엔 미국장 크론을 `30 22`로 조정.
4. 생성된 `checklist.output.json`의 raw URL을 Claude에게 전달 → 판정.

## 설정 메모
- **현금 비중**: `watchlist.json`의 `meta`에 `"cash_krw": 3968000` 추가하면 현금% 자동 계산.
- **KRX 계정(선택)**: pykrx 일부 수급데이터가 계정을 요구하면, 레포 Secrets에
  `KRX_ID` / `KRX_PW`를 등록. 대부분의 공개 데이터는 계정 없이도 동작.
- **종목 추가**: `holdings`에 블록 추가. 티커만 넣어도 됨(논리는 Claude와 대화로 채우기).

## 4개 층 판정 (Phase 1 자동화 범위)
| 층 | 소스 | 상태 |
|---|---|---|
| technical | ta(RSI·SMA) | ✅ 완전 자동 |
| supply_demand | pykrx 외국인/기관 순매매 | ✅ 한국 자동 / 미국 제한 |
| macro | 지수 등락(KOSPI·NASDAQ) | ✅ 자동 (VKOSPI는 Phase 2) |
| fundamental | yfinance 밸류 숫자 | 🟡 표시만 (심층판단 Phase 3/4) |

확신도 = 신호 일치도 × 데이터 신뢰도. (확정 종가=high, yfinance 지연=mid)

## 로드맵
- **Phase 1 (현재)**: 수급+기술+매크로 자동, 진정 체크리스트, B카드 출력.
- **Phase 2**: 보조지표(볼린저·거래량·이평 크로스), VKOSPI·환율·SOX 매크로.
- **Phase 3**: 펀더멘털 층(밸류 대시·실적 캘린더·서프라이즈).
- **Phase 4**: `narrate()`를 Claude/Gemini API로 교체 → 근거 자연어 서술 자동화.
  (지금은 규칙 기반 템플릿. 크레딧은 이 단계에서만 사용.)
- **Phase 5**: 백테스트(과거 데이터로 규칙 검증).

## 정직한 한계
- yfinance·pykrx 수급은 **장마감 후 확정값** 기준(장중 실시간 아님) — 우리 원칙과 일치.
- RSI는 계산 방식(단순/지수) 차이로 소스마다 다를 수 있으나, 여기선 한 방식으로 고정 → 매일 일관.
- 정밀 실시간 진입가는 반드시 MTS 화면과 대조.
- **확신도는 '규칙 부합도'이지 '수익 보장'이 아님.** 최종 방아쇠는 사람이.
