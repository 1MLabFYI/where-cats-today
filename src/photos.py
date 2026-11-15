"""무료 라이선스 실사 사진 수집 (출처 자동 기록).
순서: 국내 명소 → 한국관광공사 TourAPI(공공누리 1유형만) → Wikimedia Commons(CC0/PD/CC BY) → Pexels
      음식      → Pexels → Wikimedia Commons
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
            out.append((it['firstimage'], '한국관광공사 (공공누리 제1유형)'))
    return out


def commons(query):
    r = requests.get('https://commons.wikimedia.org/w/api.php', headers=UA, timeout=30, params=dict(
        action='query', format='json', generator='search', gsrsearch=f'filetype:bitmap {query}',
        gsrnamespace=6, gsrlimit=15, prop='imageinfo', iiprop='url|extmetadata|size', iiurlwidth=1600))
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
        out.append((ii.get('thumburl') or ii['url'], f'{artist} / {lic} / Wikimedia Commons'))
    return out


def pexels(query):
    key = os.environ.get('PEXELS_API_KEY')
    if not key:
        return []
    r = requests.get('https://api.pexels.com/v1/search', headers={'Authorization': key}, timeout=30,
                     params=dict(query=query, orientation='portrait', per_page=10))
    return [(p['src']['large2x'], f"{p['photographer']} / Pexels") for p in r.json().get('photos', [])]


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        print(f'{fn.__name__} 실패:', str(e)[:120]); return []


def fetch_for_episode(ep, work):
    used, credits = set(), []
    for i, sc in enumerate(ep['scenes']):
        q = sc.get('photo_query') or ep['place_en']
        cands = []
        if sc.get('photo_kind') == 'food':
            cands += _safe(pexels, q) + _safe(commons, q)
        else:
            if ep['region'] == 'domestic':
                cands += _safe(tourapi, sc.get('label_ko') or ep['place_ko'])
            cands += _safe(commons, q) + _safe(pexels, q)
        cands += _safe(commons, ep['place_en']) + _safe(pexels, ep['place_en'] + ' travel')  # 최후 대체
        for url, credit in cands:
            if url in used:
                continue
            try:
                im = _get_img(url)
            except Exception:
                continue
            if im:
                im.save(os.path.join(work, f'photo_{i:02d}.jpg'), quality=92)
                used.add(url); credits.append(credit)
                break
    return sorted(set(credits))
