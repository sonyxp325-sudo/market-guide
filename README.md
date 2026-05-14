# 시장 과열도 가이드 - 세팅 가이드

PC로 30분 정도 한 번만 세팅하면, 그 다음부터는 폰에서 매일 22시 이후 열어보기만 하면 돼요.

## 준비물

- GitHub 계정 (없으면 [github.com/signup](https://github.com/signup) 에서 무료 가입, 5분)
- PC 웹 브라우저

## 1단계: 저장소 만들기 (5분)

1. [github.com/new](https://github.com/new) 접속
2. **Repository name**: `market-guide` (다른 이름도 OK, 기억하기 쉬운 걸로)
3. **Public** 선택 (Private이면 GitHub Pages 무료가 안 됨)
4. **Add a README file** 체크 ✅
5. **Create repository** 클릭

## 2단계: 파일 4개 업로드 (10분)

저장소 페이지에서 **Add file → Upload files** 클릭. 아래 4개 파일을 정확한 폴더 구조로 올려야 해요:

```
저장소 루트/
├── index.html                        ← 그대로 루트에
├── scripts/
│   └── fetch_data.py                 ← scripts 폴더 안에
└── .github/
    └── workflows/
        └── update.yml                ← .github/workflows 폴더 안에
```

**팁:** 폴더는 자동으로 만들어져요. 업로드할 때 파일 이름란에 `scripts/fetch_data.py` 처럼 슬래시(`/`)로 경로를 적으면 폴더가 생겨요. 또는 PC에서 폴더째 드래그앤드롭하면 한 번에 올라가요.

모두 올리고 **Commit changes** 클릭.

## 3단계: Actions 권한 켜기 (3분, 가장 자주 놓치는 부분!)

저장소 페이지 → **Settings** 탭 → 왼쪽 메뉴 **Actions → General**

맨 아래쪽 **Workflow permissions** 섹션:
- ✅ **Read and write permissions** 선택
- ✅ **Allow GitHub Actions to create and approve pull requests** 체크
- **Save** 클릭

> 이걸 안 하면 매일 자동 실행은 되는데 `data/` 폴더에 커밋을 못 해서 결과가 안 쌓여요.

## 4단계: 첫 실행 (2분)

자동 실행은 매일 22시지만, 지금 바로 한 번 돌려서 확인해볼 수 있어요.

저장소 → **Actions** 탭 → 왼쪽에 **Update Market Data** 선택 → 오른쪽 **Run workflow** 버튼 → **Run workflow** 확인

1~2분 후 새로고침해서 ✅ 초록색 체크 뜨면 성공. 빨간색이면 클릭해서 로그 확인.

성공하면 저장소에 `data/market.json` 파일이 생겼을 거예요.

## 5단계: GitHub Pages 켜기 (3분)

폰에서 깔끔한 URL로 열려면 GitHub Pages를 켜야 해요.

저장소 → **Settings** → 왼쪽 **Pages**
- **Source**: Deploy from a branch
- **Branch**: `main` / `(root)` 선택 → **Save**

1~2분 후 페이지 상단에 URL이 떠요:
`https://본인username.github.io/market-guide/`

이 URL이 본인 도구 주소예요.

## 6단계: 폰에서 사용 (2분)

1. 폰 브라우저로 위 URL 접속
2. 저장소 입력란에 `본인username/market-guide` 입력 → 불러오기
3. 데이터 뜨면 성공!

**홈 화면에 추가:**
- **iOS Safari**: 공유 버튼 → "홈 화면에 추가"
- **Android Chrome**: 메뉴 → "홈 화면에 추가"

이제 홈 화면 아이콘 = 본인만의 시장 온도계.

---

## 운영

- 매일 한국시간 **22:00** (UTC 13:00) 자동 실행
- 미국 시장 마감이 한국시간 새벽 5시(서머타임 기준)/6시라, 22시 시점이면 최신 종가 반영됨
- 점수가 안 바뀌면 커밋도 안 일어남 (정상)

## 트러블슈팅

**Actions가 빨간색 X로 뜸**
- Actions 탭에서 실패한 실행 클릭 → 어떤 단계에서 실패했는지 로그 확인
- `Permission denied` → 3단계의 권한 설정 안 했을 가능성

**폰에서 "로딩 실패"가 뜸**
- 저장소 주소 다시 확인 (`username/repo-name`)
- Actions가 한 번이라도 성공했는지 확인 (Actions 탭)
- 저장소가 Public인지 확인

**데이터가 어제 거임**
- 22시 직후엔 아직 실행 중일 수 있음. 22:05쯤 새로고침
- 미국 시장 휴일이면 전날 데이터 그대로

## 비용

- GitHub 계정: 무료
- GitHub Actions: 월 2000분 무료 (우리는 월 1~2분 사용)
- GitHub Pages: 무료
- **총 비용: 0원, 평생**
