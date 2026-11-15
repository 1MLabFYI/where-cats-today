# 오늘 어디냥? / Where to, Meow? 🐾

고양이 캐릭터 **허미(모험냥)**와 **냐미(먹방냥)**가 국내외 여행지를 소개하는 인스타그램 릴스를 **매일 자동 제작하고 16:00(KST)에 게시**합니다.

## 하루 흐름

| 시각 (KST) | 워크플로 | 하는 일 |
|---|---|---|
| 09:00 | `generate` | 웹 검색으로 장소 선정 → 대본/정보 → 사진 수집 → TTS → 릴스 렌더 → 릴리스에 업로드 → **검토용 이슈 생성** |
| 09:00~16:00 | (사람, 선택) | 영상 확인. 게시를 막으려면 이슈에 `skip` 라벨 |
| 16:00 | `publish` | ① 전용 웹사이트에 한·영 가이드 페이지 추가 → ② 구글 블로거에 같은 양식으로 게시 → ③ Instagram 릴스 게시(캡션·첫 댓글에 사이트 주소) → ④ 사이트 페이지에 릴스 임베드 → 이슈 닫기 |

사람이 아무것도 하지 않아도 전부 자동으로 진행됩니다. 단계마다 이미 게시된 것은 건너뛰므로 재실행해도 중복 게시되지 않습니다.

## 편성
- 월·수·금·일 **국내편**, 화·목·토 **해외편** (`config/channel.yaml`에서 변경)
- 120일 안에 다룬 장소는 다시 고르지 않음 (`episodes/history.json`)
- 릴스 10장면: 표지 → 허미(왜 지금? + 스팟 3) → 냐미(꼭 먹어볼 메뉴 2, 같이 갈 곳 1) → 여행정보 카드 → 요약 + 시그니처 "허미냐미 냥행기"
- 릴스에는 **식당 이름을 넣지 않음**. 식당은 캡션·블로그에만 나오고, 2차 웹 검색으로 영업 여부를 확인해 확인되지 않은 곳은 뺌

## 설정 (최초 1회)

### 1) 저장소
이 폴더를 GitHub 저장소(Public 권장: 릴리스 영상 URL을 Instagram이 읽어야 함)로 올립니다.

### 2) Secrets (Settings → Secrets and variables → Actions)
| 이름 | 필수 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google AI Studio 무료 키 (장소 선정·대본, 검색 그라운딩) |
| `IG_USER_ID` | ✅ | 새 Instagram 비즈니스 계정 ID |
| `IG_ACCESS_TOKEN` | ✅ | 장기 토큰 (instagram_content_publish, instagram_manage_comments 권한) |
| `PEXELS_API_KEY` | 권장 | 무료. 음식·해외 사진 |
| `TOUR_API_KEY` | 권장 | 공공데이터포털 '한국관광공사_국문 관광정보 서비스' 무료 키. 국내 사진(공공누리 1유형만 사용) |
| `BLOGGER_*` (4개) | 선택 | 구글 블로거 동시 게시 (아래 4번) |

Instagram 로그인 방식으로 토큰을 발급했다면 Variables에 `IG_GRAPH_HOST=graph.instagram.com`을 넣습니다.

### 3) 전용 웹사이트 (GitHub Pages)
1. 저장소 Settings → Pages → Source: **Deploy from a branch**, Branch: `main`, 폴더: `/docs` → Save
2. `config/channel.yaml`의 `site.base_url`에 사이트 주소 입력 (예: `https://아이디.github.io/today-where-nyang`)
3. 개인 도메인(권장, 연 1~2만 원): 도메인 구입 → DNS에 GitHub Pages 연결 → `site.custom_domain`, `site.base_url` 입력
4. [Google Search Console](https://search.google.com/search-console)에 사이트 등록 → 인증 태그 값을 `site.search_console_verification`에 → `sitemap.xml` 제출
5. 애드센스: 글이 20~30개 쌓이면 신청 → 승인 후 `site.adsense`에 client/slot 입력 (광고 코드와 `ads.txt` 자동 삽입)
6. 인스타그램 프로필 링크 = 사이트 홈 (`.../ko/`)

사이트 구성: 홈(국내편·해외편 필터) / 에피소드별 한국어·영어 페이지(허미·냐미 말풍선, 코스, 꼭 먹어볼 메뉴, 맛집 카드, 여행정보 표, 제휴 버튼, 릴스 임베드, 출처) / sitemap·RSS·hreflang·구조화 데이터 자동 생성.

### 4) 구글 블로거 (사이트와 같은 양식으로 동시 게시)
1. blogger.com에서 블로그 생성
2. Google Cloud 콘솔 → 새 프로젝트 → **Blogger API v3** 사용 설정
3. OAuth 동의 화면: 외부 → 게시 상태를 **프로덕션**으로 (테스트 상태면 7일마다 토큰 만료)
4. 사용자 인증 정보 → OAuth 클라이언트 ID → 유형 **데스크톱 앱** → ID·보안 비밀 복사
5. 내 PC에서 `python tools/blogger_auth.py <CLIENT_ID> <CLIENT_SECRET>` → 브라우저에서 허용 → 출력된 값을 Secrets에 저장:
   `BLOGGER_CLIENT_ID`, `BLOGGER_CLIENT_SECRET`, `BLOGGER_REFRESH_TOKEN`, `BLOGGER_BLOG_ID`
6. 영어 글도 올리려면 `blogger.languages: [ko, en]`

> 사이트와 블로거에 같은 글이 올라가면 구글이 둘 중 하나만 검색 결과에 노출할 수 있습니다(중복 콘텐츠). 그래서 블로거 글 하단에 사이트 원문 링크를 넣어 사이트를 원본으로 표시합니다. 애드센스는 **사이트 한 곳에 먼저** 신청하는 것을 권장합니다.

### 5) 배경음악
`assets/bgm/`에 저작권 걱정 없는 음원(mp3/wav)을 여러 개 넣으면 에피소드마다 돌아가며 씁니다. `placeholder_loop.wav`는 임시로 만든 음원이니 교체를 권장합니다. 출처 예: YouTube 오디오 보관함, Pixabay Music(라이선스 조건 확인).

### 6) 첫 실행 (시안)
Actions → `generate` → Run workflow → episode 칸에 `episodes/sample_gangneung.json` → 실행.
실사 사진과 SunHi 음성이 들어간 강릉 시안이 릴리스와 이슈로 나옵니다.
이어서 Actions → `publish` → `now=true`, `site_only=true`로 실행하면 인스타 게시 없이 사이트·블로거만 먼저 확인할 수 있습니다.

## 음성
- 기본: Microsoft Edge 신경망 음성 `ko-KR-SunHiNeural` (무료). 허미는 +18Hz, 냐미는 +32Hz로 피치를 올려 귀엽게 구분합니다 (`src/tts.py`).
- 대체: 오프라인 KSS 음성 (네트워크가 막힐 때만 사용, 음질이 낮음)

## 사진 저작권 원칙
- 국내: TourAPI 공공누리 **1유형**(출처 표시 시 변경·상업 이용 가능)만 사용
- Wikimedia: CC0 / Public Domain / CC BY만 사용 (CC BY-SA 제외)
- Pexels: 무료 라이선스
- 식당 사진, 블로그·구글 사진은 쓰지 않습니다. 출처는 캡션과 블로그에 자동으로 표기합니다.

## 수익화
- 사이트: 구글 애드센스 + 여행 제휴 링크(숙소: 아고다·트립닷컴 / 투어: 마이리얼트립·클룩 / 여행용품: 쿠팡파트너스). 링크는 `config/channel.yaml`의 `affiliates`에 넣습니다.
- 블로거: 블로거 자체 애드센스 연동(블로거 설정 → 수익) + 같은 제휴 링크
- 제휴 링크를 넣은 글에는 대가성 문구를 반드시 표시해야 합니다(공정위 추천·보증 심사지침). 자동으로 들어갑니다.
- 구글은 AI로 대량 생산한 저품질 글을 제재합니다. 페이지마다 구체적 여행정보·출처·캐릭터 코멘트가 들어가도록 설계했지만, 초기에는 가끔 직접 읽고 품질을 점검하세요.
- (선택) 네이버 블로그: 이슈의 `naver_draft.zip`을 붙여넣으면 됩니다. 네이버는 2020년 5월 글쓰기 API를 종료해 자동 게시가 불가합니다.

## 로컬 실행
```bash
pip install -r requirements.txt   # ffmpeg 필요
python src/main.py generate --episode episodes/sample_gangneung.json
SITE_BASE_URL=http://localhost:8000 python src/main.py publish --dir out/2026-11-sample-gangneung --video-url x --site-only
python -m http.server -d docs 8000   # 브라우저에서 http://localhost:8000/ko/
```
