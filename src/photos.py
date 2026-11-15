"""무료 라이선스 실사 사진 수집 (출처 자동 기록).
순서: 국내 명소 → 한국관광공사 TourAPI(공공누리 1유형만) → Wikimedia Commons(CC0/PD/CC BY) → Pixabay → Pexels
      음식      → Pixabay → Pexels → Wikimedia Commons
(Pixabay/Pexels 키는 있는 것만 사용. 둘 다 없어도 동작)
식당 사진은 사용하지 않는다(저작권). 음식은 일반 음식 사진만.
"""
import io, os, re
import requests
from PIL import Image

UA = {'User-Agent': 'TodayWhereNyang/1.0 (instagram travel channel; contact via github)'}
OK_LIC = re.compile(r'^(cc0|public domain|pd|cc by \d|cc-by-\d|cc by-\d|cc by \d\.\d)', re.I)


def _get_img(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert('RGB')
    return im if min(im.size) >= 700 else None


def tourapi(query_ko):
    key = os.environ.get('TOUR_API_KEY')
    if not key:
        return []
    r = requests.get('https://apis.data.go.kr/B551011/KorService2/searchKeyword2', params=dict(
        serviceKey=key, MobileOS='ETC', MobileApp='TodayWhereNyang', _type='json', keyword=query_ko,
        numOfRows=10, arrange='Q'), timeout=30)
    try:
        items = r.json()['response']['body']['items']['item']
    except Exception:
        return []
    out = []
    for it in items if isinstance(items, list) else [items]:
        if it.get('firstimage') and it.get('cpyrhtDivCd', 'Type1') == 'Type1':
            out.append((it['firstimage'], '한국관광공사 (공공누리 제1유형)', 'TOURAPI korea ' + it.get('title', '')))
    return out


def commons(query):
    r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=30, params=dict(
        action='query', format='json', generator='search', gsrsearch=f'filetype:bitmap {query}',
        gsrnamespace=6, gsrlimit=15, prop='imageinfo', iiprop='url|extmetadata|size', iiextmetadatafilter='LicenseShortName|Artist|ImageDescription|Categories', iiurlwidth=1600))
    out = []
    for p in sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda x: x.get('index', 99)):
        ii = p['imageinfo'][0]
        md = ii.get('extmetadata', {})
        lic = md.get('LicenseShortName', {}).get('value', '')
        if not OK_LIC.match(lic) or 'SA' in lic.upper().split():
            continue  # CC BY-SA는 2차 저작물 의무가 있어 제외
        if ii.get('width', 0) < 1000:
            continue
        artist = re.sub('<[^>]+>', '', md.get('Artist', {}).get('value', '')).strip()[:60]
        meta = ' '.join([p.get('title', ''), md.get('ImageDescription', {}).get('value', ''), md.get('Categories', {}).get('value', '')])
        out.append((ii.get('thumburl') or ii['url'], f'{artist} / {lic} / Wikimedia Commons', re.sub('<[^>]+>', ' ', meta)))
    return out


def pexels(query):
    key = os.environ.get('PEXELS_API_KEY')
    if not key:
        return []
    r = requests.get('https://api.pexels.com/v1/search', headers={'Authorization': key}, timeout=30,
                     params=dict(query=query, orientation='portrait', per_page=10))
    return [(p['src']['large2x'], f"{p['photographer']} / Pexels", p.get('alt', '')) for p in r.json().get('photos', [])]


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f'{fn.__name__} 실패:', str(e)[:120]); return []


def pixabay(query):
    """Pixabay: 상업적 이용 가능, 출처 표기 의무 없음(표기는 함). 핫링크 금지 → 내려받아 사용"""
    key = os.environ.get('PIXABAY_API_KEY')
    if not key:
        return []
    out = []
    for orient in ('vertical', 'all'):
        r = requests.get('https://pixabay.com/api/', timeout=30, params=dict(
            key=key, q=query[:100], image_type='photo', orientation=orient, safesearch='true',
            per_page=20, order='popular', min_width=1000))
        out += [(h['largeImageURL'], f"{h.get('user', '')} / Pixabay", h.get('tags', '')) for h in r.json().get('hits', [])]
        if len(out) >= 5:
            break
    return out


# ---------- 중복 사진 거르기 (파일 주소가 달라도 같은/거의 같은 사진) ----------
def dhash(im, n=8):
    g = im.convert('L').resize((n + 1, n), Image.LANCZOS)
    px = list(g.getdata())
    return sum(1 << i for i in range(n * n) if px[(i // n) * (n + 1) + i % n] > px[(i // n) * (n + 1) + i % n + 1])


def is_dup(h, hashes, th=12):
    return any(bin(h ^ x).count('1') <= th for x in hashes)


# ---------- 엉뚱한 사진 거르기 ----------
KR_WORDS = ('korea', 'korean', 'seoul', 'busan', 'jeju', 'gangwon', 'gyeong', 'jeolla', 'chungcheong', 'incheon', 'daegu', 'gwangju')


def _tokens(*xs):
    t = set()
    for x in xs:
        for w in re.findall(r'[a-z]{4,}', (x or '').lower()):
            if w not in ('beach', 'street', 'lake', 'market', 'park', 'temple', 'city', 'travel', 'south', 'food', 'korean'):
                t.add(w)
    return t


def meta_ok(ep, sc, meta):
    """1차: 사진 설명/태그로 거르기 (국내편 명소 사진은 한국·지명 단서가 있어야 통과)"""
    m = (meta or '').lower()
    if 'TOURAPI' in (meta or ''):
        return True
    if sc.get('photo_kind') == 'food':
        return True                       # 음식은 2차(이미지 판별)에서 거름
    keys = _tokens(ep['place_en'], sc.get('label_en'), sc.get('photo_query'))
    if ep['region'] == 'domestic':
        return any(k in m for k in KR_WORDS) or any(k in m for k in keys)
    return any(k in m for k in keys | _tokens(ep.get('country_en', '')))


def vision_ok(im, ep, sc):
    """2차: Gemini가 이미지를 직접 보고 장면에 맞는지 판정 (키 없으면 통과)"""
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        return True
    import base64, json as _j
    sm = im.copy(); sm.thumbnail((512, 512))
    buf = io.BytesIO(); sm.save(buf, 'JPEG', quality=80)
    where = '대한민국(한국)' if ep['region'] == 'domestic' else ep.get('country_ko', '') or ep['place_en']
    best = (ep.get('info') or {}).get('best_ko', '')
    season = (f" 이 편은 '{best}' 시기 여행을 소개한다. 계절감이 크게 어긋나면(예: 겨울 여행편인데 벚꽃·꽃밭이 주인공인 사진, 여름편인데 눈 풍경) false."
              if best else '')
    if sc.get('photo_kind') == 'food':
        q = (f"이 사진이 '{sc.get('label_ko') or ''} / {sc.get('photo_query')}' 음식 장면으로 자연스러운가? "
             f"{where} 여행 소개 영상에 쓸 것이다. 다른 나라 음식이 분명하거나, 음식이 아니거나, 사람 얼굴이 크게 나오면 false.")
    else:
        q = (f"이 사진이 {where} {ep['place_ko']}의 '{sc.get('label_ko') or ep['place_ko']}' 소개 장면 배경으로 맞는가? "
             f"누가 봐도 다른 나라 풍경·건축(예: 국내편인데 일본·중국·유럽·동남아 풍경)이거나, 주제와 무관하거나, "
             f"글자·워터마크가 크거나, 사람 얼굴이 크게 나오면 false. 꽃·나무 클로즈업처럼 장소를 알아볼 수 없는 사진도 false." + season)
    body = {'contents': [{'parts': [{'text': q + ' JSON만: {"ok": true/false, "why": "짧게"}'},
                                    {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}]}],
            'generationConfig': {'temperature': 0, 'response_mime_type': 'application/json'}}
    model = os.environ.get('GEMINI_VISION_MODEL', 'gemini-2.5-flash-lite')
    try:
        r = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                          params={'key': key}, json=body, timeout=60)
        txt = r.json()['candidates'][0]['content']['parts'][0]['text']
        res = _j.loads(txt)
        if not res.get('ok'):
            print(f"  ✗ 사진 탈락: {sc.get('label_ko') or sc['type']} — {res.get('why', '')}")
        return bool(res.get('ok'))
    except Exception as e:
        print('  (이미지 판별 실패 → 통과 처리)', str(e)[:80])
        return True


GENERIC = ('왜', '꼭', '같이', '메뉴', '요약', '정보', '추천', '가면', '좋은', '①', '②')


def tour_keyword(ep, sc):
    """관광공사 검색어: 장소 고유명사만 사용 (일반 문구로 검색하면 엉뚱한 사진이 나옴)"""
    k = (sc.get('photo_query_ko') or '').strip()
    if k:
        return k
    lab = sc.get('label_ko') or ''
    if lab and not any(g in lab for g in GENERIC):
        return lab.split('·')[0].strip()
    return ep['place_ko']


def fetch_for_episode(ep, work):
    used, credits, hashes = set(), [], []
    for i, sc in enumerate(ep['scenes']):
        q = sc.get('photo_query') or ep['place_en']
        kr = ep['region'] == 'domestic'
        cands = []
        if sc.get('photo_kind') == 'food':
            cands += _safe(pixabay, q) + _safe(pexels, q) + _safe(commons, q)
        else:
            if kr:
                cands += _safe(tourapi, tour_keyword(ep, sc))
            cands += _safe(commons, q) + _safe(pixabay, q) + _safe(pexels, q)
        fallback = (ep['place_en'] + (' South Korea' if kr else ''))
        cands += _safe(tourapi, ep['place_ko']) if kr else []
        cands += _safe(commons, fallback) + _safe(pixabay, fallback) + _safe(pexels, fallback)  # 최후 대체
        checks = 0
        for url, credit, meta in cands:
            if url in used or not meta_ok(ep, sc, meta):
                continue
            try:
                im = _get_img(url)
            except Exception:
                continue
            if not im:
                continue
            h = dhash(im)
            if is_dup(h, hashes):
                print(f"  ✗ 중복 사진 제외: {sc.get('label_ko') or sc['type']}")
                continue
            if checks < 6:
                checks += 1
                if not vision_ok(im, ep, sc):
                    continue
            else:
                continue                  # 6장 연속 탈락 → 이 장면은 사진 없이(대체 배경)
            im.save(os.path.join(work, f'photo_{i:02d}.jpg'), quality=92)
            used.add(url); credits.append(credit); hashes.append(h)
            break
    return sorted(set(credits))
