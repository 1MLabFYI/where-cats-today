"""여행지 선정 + 대본 생성 (Gemini API, Google 검색 그라운딩).
GEMINI_API_KEY 필요. 무료 등급으로 하루 1편은 충분.
"""
import datetime as dt, json, os, re, time
import requests, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = yaml.safe_load(open(os.path.join(ROOT, 'config', 'channel.yaml'), encoding='utf8'))
HIST = os.path.join(ROOT, 'episodes', 'history.json')
MODEL = os.environ.get('GEMINI_MODEL', '')          # 비우면 사용 가능한 최신 flash 모델 자동 선택
API = 'https://generativelanguage.googleapis.com/v1beta'
_models = {}


def pick_model(kind='flash'):
    """구글이 구형 모델을 막아도 멈추지 않도록, 키로 쓸 수 있는 모델 목록에서 최신 버전을 고른다.
    kind='flash'(대본) / 'lite'(사진 판별)"""
    if kind == 'flash' and MODEL:
        return MODEL
    if kind == 'lite' and os.environ.get('GEMINI_VISION_MODEL'):
        return os.environ['GEMINI_VISION_MODEL']
    if kind in _models:
        return _models[kind]
    r = requests.get(f'{API}/models', params={'key': os.environ['GEMINI_API_KEY'], 'pageSize': 1000}, timeout=60)
    names = [m['name'].split('/')[-1] for m in r.json().get('models', [])
             if 'generateContent' in m.get('supportedGenerationMethods', [])]

    def ver(n):
        m = re.match(r'gemini-(\d+(?:\.\d+)?)-', n)
        return float(m.group(1)) if m else 0

    ok = [n for n in names if re.fullmatch(r'gemini-\d+(\.\d+)?-flash' + ('-lite' if kind == 'lite' else ''), n)]
    if not ok and kind == 'lite':
        return pick_model('flash')
    if not ok:  # 정식 이름이 없으면 preview/latest 포함 flash 중 최신
        ok = [n for n in names if 'flash' in n and 'lite' not in n and 'image' not in n and 'tts' not in n and 'live' not in n]
    best = sorted(ok, key=lambda n: (ver(n), n))[-1]
    print(f'Gemini 모델 자동 선택({kind}): {best}')
    _models[kind] = best
    return best


def gemini(prompt, search=True, temperature=0.8):
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': temperature}}
    if search:
        body['tools'] = [{'google_search': {}}]
    for a in range(4):
        model = pick_model('flash')
        r = requests.post(f'{API}/models/{model}:generateContent', params={'key': os.environ['GEMINI_API_KEY']},
                          json=body, timeout=180)
        if r.status_code == 200:
            c = r.json()['candidates'][0]
            txt = ''.join(p.get('text', '') for p in c['content']['parts'])
            srcs = [g['web']['uri'] for g in c.get('groundingMetadata', {}).get('groundingChunks', []) if 'web' in g]
            return txt, srcs
        print('gemini', model, r.status_code, r.text[:300])
        if r.status_code == 404:          # 모델 단종 → 목록 다시 받아 즉시 재시도
            _models.pop('flash', None)
            if MODEL:
                raise RuntimeError(f'GEMINI_MODEL={MODEL} 사용 불가. Variables에서 지우거나 바꾸세요.')
            continue
        if r.status_code in (400, 401, 403):
            raise RuntimeError(f'Gemini 키/요청 오류 {r.status_code}')
        time.sleep(20 * (a + 1))
    raise RuntimeError('Gemini 호출 실패')


def parse_json(txt):
    m = re.search(r'```(?:json)?\s*(\{.*\})\s*```', txt, re.S) or re.search(r'(\{.*\})', txt, re.S)
    return json.loads(m.group(1))


def region_for(date):
    return 'domestic' if date.weekday() in CFG['schedule']['domestic'] else 'overseas'


def history():
    return json.load(open(HIST, encoding='utf8')) if os.path.exists(HIST) else []


EXAMPLE = json.load(open(os.path.join(ROOT, 'episodes', 'sample_gangneung.json'), encoding='utf8'))
for k in ('id', 'sources'):
    EXAMPLE.pop(k, None)

PROMPT = """너는 인스타그램 여행 릴스 채널 '오늘 어디냥? (Where to, Meow?)'의 기획 작가다.
타깃: 20~40대 한국인 및 아시아인. 고양이 캐릭터 2마리가 진행한다.
- 허미(모험냥): 여행지 계획·소개 (명소, 동선, 시기, 여행정보). 말끝에 가끔 '~냥'.
- 냐미(먹방냥): 꼭 먹어봐야 할 메뉴, 디저트, 함께 들르면 좋은 곳. 말끝에 '~냥'.

[오늘] {today} (KST) / 편성: {region_ko}
[게시 예정일 기준 시기] {season_hint}
[최근 다룬 장소 — 반복 금지] {recent}
{region_rule}

1단계: 웹 검색으로 '지금 시기에 가기 좋은 곳', '최근 SNS에서 화제/바이럴인 곳', '과거 같은 시기 인기 여행지'를 조사해
가장 반응이 좋을 장소 1곳(도시/지역 단위)을 고른다. 축제·개화·단풍·눈·일몰 등 시기성이 있으면 우선.
2단계: 아래 JSON 형식과 똑같은 구조로 에피소드를 만든다.

규칙:
- scenes는 정확히 10개: [0]=cover, [1..4]=허미 talk(왜 지금? + 핵심 스팟 2~3곳), [5..6]=냐미 talk(꼭 먹어봐야 할 메뉴 — 식당 이름은 절대 넣지 말 것, [6]의 subtitle에는 '맛집 정보는 캡션 확인'을 포함),
  [7]=냐미 talk(함께 가면 좋은 곳), [8]=info, [9]=summary(summary 3줄).
- subtitle: 한국어, 최대 2줄(줄바꿈 \\n), 한 줄 18자 이내. 이모지 금지.
- subtitle_en: subtitle의 자연스러운 영어 버전, 최대 2줄(\n), 한 줄 34자 이내.
- narration: subtitle과 같은 뜻의 자연스러운 구어체 1~2문장(40자 이내). 숫자·연도·기호는 한글로 풀어 쓴다(예: 2026년→이천이십육 년, KTX→케이티엑스).
- label_ko/label_en: 장면 제목(스팟 이름 등). pose는 다음 중에서만: 허미 {hermi_poses} / 냐미 {nyami_poses}
- photo_query: 무료 사진 검색용 영어 키워드. 명소는 '명소 영문명 + 도시명 + 국가명'(국내편은 반드시 'South Korea' 포함),
  음식은 '음식 영문명 + korean food'처럼 그 나라 음식임이 드러나게. photo_kind: place|food
- photo_query_ko: (국내편 명소 장면만) 한국관광공사 검색용 '정확한 장소 한글 고유명사' 하나. 예: '안목해변', '오죽헌'.
  '같이 가면 좋은 곳'처럼 일반 문구 금지. cover/[1]/info/summary 장면은 대표 명소 이름.
- info: 주소(국문/영문), 베스트 시기, 가는 법(한국 출발 기준 항공·KTX 등), 꿀팁 — 모두 검색으로 확인된 사실만.
- restaurants: 실제 영업 중인 식당/시장 2~3곳 (name, menu, address, hours, name_en, menu_en, address_en, hours_en,
  source=확인한 웹페이지 URL). 확인 불가하면 빼라.
- must_eat: 꼭 먹어봐야 할 메뉴 2~3개 (ko/en).
- hook_ko는 15자 이내 임팩트 문구, hook_en은 짧은 영어.
- blog: 웹사이트 가이드 원고(한국어·영어 병기, 영어는 번역투가 아닌 자연스러운 여행 가이드 문체).
  {{"title_ko": 검색 잘 되는 제목(지역명+여행코스+맛집 키워드), "title_en": 영어 SEO 제목, "intro_ko"/"intro_en": 3~4문장,
  "sections": [{{"heading_ko","heading_en","body_ko","body_en": 각 4~6문장(볼거리·팁·소요시간·주의점)}} ... 5개],
  "closing_ko"/"closing_en": 2~3문장}}
  sections 5개는 순서대로 scenes[2],[3],[4] 스팟, [5] 먹거리, [7] 같이 갈 곳과 맞춘다(그 장면 사진이 들어감). 구체적 사실·팁 위주로, 뻔한 미사여구 금지.
- sources: 참고한 URL 목록.
JSON만 출력.

형식 예시(내용은 예시일 뿐, 그대로 쓰지 말 것):
{example}
"""


def season_hint(date):
    m = date.month
    return f'{date.year}년 {m}월 (다음 2~4주 안에 가기 좋은 곳 위주)'


def make_episode(date=None, region=None):
    date = date or (dt.datetime.utcnow() + dt.timedelta(hours=9)).date()
    region = region or region_for(date)
    h = history()
    cutoff = (date - dt.timedelta(days=CFG['schedule']['avoid_repeat_days'])).isoformat()
    recent = ', '.join(f"{x['place_ko']}" for x in h if x['date'] >= cutoff) or '없음'
    rule = ('[국내편] 대한민국 안의 여행지. 서울만 반복하지 말고 전국 고르게.' if region == 'domestic' else
            f"[해외편] 해외 여행지. {CFG['schedule']['overseas_focus']}. 한국 출발 항공편 정보 포함.")
    p = PROMPT.format(today=date.isoformat(), region_ko='국내편' if region == 'domestic' else '해외편',
                      season_hint=season_hint(date), recent=recent, region_rule=rule,
                      hermi_poses=', '.join(CFG['characters']['hermi']['poses']),
                      nyami_poses=', '.join(CFG['characters']['nyami']['poses']),
                      example=json.dumps(EXAMPLE, ensure_ascii=False))
    last = None
    for _ in range(3):
        try:
            txt, srcs = gemini(p)
            ep = parse_json(txt)
            validate(ep)
            ep['region'] = region
            ep['id'] = f'{date.isoformat()}-{re.sub(r"[^a-z0-9]+", "-", ep["place_en"].lower()).strip("-")}'
            ep['date'] = date.isoformat()
            ep['sources'] = list(dict.fromkeys(ep.get('sources', []) + srcs))
            return verify_restaurants(ep)
        except Exception as e:
            last = e; print('재시도:', e)
    raise RuntimeError(f'에피소드 생성 실패: {last}')


def validate(ep):
    sc = ep['scenes']
    assert len(sc) == 10, 'scenes != 10'
    assert sc[0]['type'] == 'cover' and sc[8]['type'] == 'info' and sc[9]['type'] == 'summary'
    poses = CFG['characters']['hermi']['poses'] + CFG['characters']['nyami']['poses']
    for s in sc[1:8]:
        assert s['type'] == 'talk' and s['speaker'] in ('hermi', 'nyami')
        if s.get('pose') not in poses:
            s['pose'] = CFG['characters'][s['speaker']]['poses'][0]
        s['subtitle'] = s['subtitle'][:44]
        s['subtitle_en'] = (s.get('subtitle_en') or '')[:80]
        for name in [r.get('name', '') for r in ep.get('restaurants', [])]:
            if name and name in s['subtitle']:
                raise ValueError('릴스 자막에 식당명이 들어감')
    sc[8].setdefault('pose', 'hermi_point'); sc[8].setdefault('speaker', 'hermi')
    assert len(sc[9].get('summary', [])) >= 3
    b = ep.get('blog', {})
    assert b.get('title_ko') and b.get('title_en') and len(b.get('sections', [])) >= 4, 'blog 원고 부족'
    for k in ('address_ko', 'address_en', 'best_ko', 'best_en', 'transport_ko', 'transport_en', 'tip_ko', 'tip_en'):
        assert ep['info'].get(k), f'info.{k} 누락'


def verify_restaurants(ep):
    """식당 영업 여부 2차 검증 (검색 그라운딩). 확인 안 되면 제외."""
    if not ep.get('restaurants'):
        return ep
    q = ('다음 식당/시장들이 현재(오늘 기준) 영업 중인지, 주소가 맞는지 웹 검색으로 확인해라. '
         'JSON 배열만 출력: [{"name":..., "ok": true/false, "address": 확인된 주소, "hours": 확인된 영업시간}]\n'
         + json.dumps(ep['restaurants'], ensure_ascii=False))
    try:
        txt, _ = gemini(q, temperature=0.1)
        arr = json.loads(re.search(r'\[.*\]', txt, re.S).group(0))
        ok = {a['name']: a for a in arr if a.get('ok')}
        kept = []
        for r in ep['restaurants']:
            if r['name'] in ok:
                r['address'] = ok[r['name']].get('address') or r['address']
                r['hours'] = ok[r['name']].get('hours') or r.get('hours', '')
                kept.append(r)
        ep['restaurants'] = kept
    except Exception as e:
        print('식당 검증 실패(원본 유지 안 함):', e)
        ep['restaurants'] = []
    return ep


def save_history(ep):
    h = history()
    h.append({'date': ep['date'], 'region': ep['region'], 'place_ko': ep['place_ko'], 'place_en': ep['place_en']})
    json.dump(h, open(HIST, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
