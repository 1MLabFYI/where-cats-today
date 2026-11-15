"""전용 웹사이트 생성기 (GitHub Pages: docs/ 폴더)
  - docs/data/<id>.json    : 에피소드 원본 (사이트 데이터베이스 역할)
  - docs/img/<id>/...      : 페이지용 이미지
  - docs/ko/<id>/, docs/en/<id>/ : 한·영 가이드 페이지
  - docs/ko/, docs/en/     : 목록(홈) / docs/index.html : 언어 자동 이동
  - sitemap.xml, robots.txt, feed.xml(ko/en), ads.txt, CNAME, .nojekyll
같은 본문(article_html)을 Blogger 게시에도 그대로 사용한다.
"""
import datetime as dt, glob, html, json, os, shutil
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
CFG = yaml.safe_load(open(os.path.join(ROOT, 'config', 'channel.yaml'), encoding='utf8'))
S = CFG['site']
e = html.escape

SEC_PHOTO = [2, 3, 4, 5, 7]  # 본문 섹션 ↔ 릴스 장면 사진 (스팟 3 + 먹거리 + 같이 갈 곳)

T = {  # UI 문구
    'ko': dict(home='홈', dom='국내편', ovs='해외편', all='전체', route="허미의 여행 코스", eat="냐미의 꼭 먹어봐야 할 메뉴",
               where='냐미가 찜한 맛집', info='여행 정보 한눈에', addr='위치', best='베스트 시기', go='가는 법', tip='꿀팁',
               name='이름', menu='대표 메뉴', hours='영업시간', prep='여행 준비', stay='숙소 최저가 보기', tour='투어·입장권 보기',
               goods='여행 준비물 보기', reel='릴스로 보기', photo='사진', src='참고 자료', more='다른 여행지', ai='캐릭터는 AI로 제작되었습니다.',
               check='영업시간·요금은 변동될 수 있으니 방문 전 꼭 확인하세요.', other='English', other_lang='en',
               hello_h='안녕! 모험냥 허미야. 오늘은 {p}(으)로 떠나볼까냥?', hello_n='먹방냥 냐미는 맛있는 거 담당이다냥!',
               desc='고양이 여행 크리에이터 허미·냐미가 소개하는 국내·해외 여행지 가이드',
               ig='인스타그램에서 매일 오후 4시 새 여행지!', placeholder='[제휴 링크 자리]'),
    'en': dict(home='Home', dom='Korea', ovs='World', all='All', route="Hermi's route", eat="Nyami's must-eats",
               where='Where to eat', info='Travel info at a glance', addr='Where', best='Best time', go='Getting there', tip='Tip',
               name='Name', menu='Signature', hours='Hours', prep='Plan your trip', stay='Find hotel deals', tour='Tours & tickets',
               goods='Travel essentials', reel='Watch the reel', photo='Photos', src='Sources', more='More destinations',
               ai='Characters are AI-generated.', check='Hours and prices may change — please check before visiting.',
               other='한국어', other_lang='ko', hello_h="Hi! I'm Hermi the adventure cat. Shall we go to {p} today?",
               hello_n="I'm Nyami, in charge of all things delicious, meow!",
               desc='Travel guides to Korea and beyond, hosted by two travel-loving cats, Hermi & Nyami.',
               ig='New destination every day at 4 PM (KST) on Instagram!', placeholder='[affiliate link]'),
}


def L(d, key, lang):
    """다국어 필드 꺼내기: key_lang → key_ko → key"""
    return d.get(f'{key}_{lang}') or d.get(f'{key}_ko') or d.get(key) or ''


def base():
    return (os.environ.get('SITE_BASE_URL') or S.get('base_url') or '').rstrip('/')


def url(path):
    return f"{base()}/{path.lstrip('/')}"


def page_url(ep, lang):
    return url(f"{lang}/{ep['id']}/")


# ---------- 데이터 추가 ----------
def add_episode(ep_json, img_dir):
    """generate 단계가 만든 사이트 이미지 + 에피소드를 docs/에 등록"""
    ep = json.load(open(ep_json, encoding='utf8'))
    os.makedirs(os.path.join(DOCS, 'data'), exist_ok=True)
    old = os.path.join(DOCS, 'data', ep['id'] + '.json')
    if os.path.exists(old):
        prev = json.load(open(old, encoding='utf8'))
        for k in ('ig_permalink', 'blogger_urls', 'published_at'):
            if prev.get(k):
                ep[k] = prev[k]
    dst = os.path.join(DOCS, 'img', ep['id'])
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(img_dir, dst)
    ep['images'] = sorted(os.listdir(dst))
    ep.setdefault('published_at', dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z')
    json.dump(ep, open(os.path.join(DOCS, 'data', ep['id'] + '.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    return ep


def set_permalink(ep_id, permalink, blogger_urls=None):
    p = os.path.join(DOCS, 'data', ep_id + '.json')
    ep = json.load(open(p, encoding='utf8'))
    if permalink:
        ep['ig_permalink'] = permalink
    if blogger_urls:
        ep['blogger_urls'] = blogger_urls
    json.dump(ep, open(p, 'w', encoding='utf8'), ensure_ascii=False, indent=1)


def all_eps():
    eps = [json.load(open(f, encoding='utf8')) for f in glob.glob(os.path.join(DOCS, 'data', '*.json'))]
    return sorted(eps, key=lambda x: (x.get('date', ''), x['id']), reverse=True)


# ---------- 공통 조각 ----------
def ad(slot):
    c = S.get('adsense', {})
    if not (c.get('client') and c.get(slot)):
        return ''
    return (f'<div class="ad"><ins class="adsbygoogle" style="display:block" data-ad-client="{c["client"]}" '
            f'data-ad-slot="{c[slot]}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


def head(title, desc, lang, canonical, alt=None, og_img=None, jsonld=None):
    c = S.get('adsense', {})
    gsc = S.get('search_console_verification')
    alts = ''.join(f'<link rel="alternate" hreflang="{l}" href="{u}">' for l, u in (alt or {}).items())
    return f'''<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canonical}">{alts}
<meta property="og:type" content="article"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{canonical}">
{f'<meta property="og:image" content="{og_img}">' if og_img else ''}
<meta name="twitter:card" content="summary_large_image">
{f'<meta name="google-site-verification" content="{e(gsc)}">' if gsc else ''}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Jua&family=Noto+Sans+KR:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{url('assets/style.css')}">
<link rel="alternate" type="application/rss+xml" href="{url(f'{lang}/feed.xml')}">
{f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={c["client"]}" crossorigin="anonymous"></script>' if c.get('client') else ''}
{f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>' if jsonld else ''}
</head><body>'''


def header(lang, other_href):
    t = T[lang]
    return f'''<header class="top"><a class="logo" href="{url(lang + '/')}"><span>오늘 어디냥?</span><small>Where to, Meow?</small></a>
<nav><a href="{url(lang + '/')}#domestic">{t['dom']}</a><a href="{url(lang + '/')}#overseas">{t['ovs']}</a>
<a class="lang" href="{other_href}">{t['other']}</a></nav></header>'''


def footer(lang):
    t, c = T[lang], CFG['channel']
    ig = c.get('ig_handle', '').lstrip('@')
    nb = c.get('naver_blog')
    return f'''<footer><img src="{url('assets/hermi_wave.webp')}" alt="Hermi" width="70"><img src="{url('assets/nyami_icecream.webp')}" alt="Nyami" width="70">
<p class="sig">{c['signature_ko']} · {c['signature_en']}</p>
<p>{t['ig']} {f'<a href="https://www.instagram.com/{ig}/">@{ig}</a>' if ig else ''} {f'· <a href="{nb}">Naver Blog</a>' if nb else ''}</p>
<p class="small"><a href="{url('about/')}">About</a> · <a href="{url('privacy/')}">Privacy</a> · <a href="{url('terms/')}">Terms</a></p>
<p class="small">{t['ai']} · © {dt.date.today().year} {c['title_ko']}</p></footer></body></html>'''


# ---------- 본문 (사이트·블로거 공용) ----------
def article_html(ep, lang, img_base, for_blogger=False):
    t, inf, b, af = T[lang], ep['info'], ep.get('blog', {}), CFG['affiliates']
    place = ep['place_ko'] if lang == 'ko' else ep['place_en']
    imgs = ep.get('images', [])
    img = lambda n: f'{img_base}/{n}'
    out = []
    if 'cover.jpg' in imgs:
        out.append(f'<p><img src="{img("cover.jpg")}" alt="{e(place)}" style="max-width:100%;border-radius:16px"></p>')
    out.append(f'''<div class="talk hermi"><img src="{url('assets/hermi_wave.webp')}" alt="허미" width="72">
<p><b>{'허미' if lang == 'ko' else 'Hermi'}</b> {e(t['hello_h'].format(p=place))}</p></div>''')
    out.append(f'<p class="lead">{e(L(b, "intro", lang))}</p>')
    if not for_blogger:
        out.append(ad('slot_top'))
    if ep.get('ig_permalink'):
        out.append(f'<blockquote class="instagram-media" data-instgrm-permalink="{e(ep["ig_permalink"])}" data-instgrm-version="14" '
                   f'style="max-width:420px;margin:16px auto"><a href="{e(ep["ig_permalink"])}">{t["reel"]}</a></blockquote>'
                   '<script async src="https://www.instagram.com/embed.js"></script>')
    out.append(f'<h2>🐾 {t["route"]}</h2>')
    secs = b.get('sections', [])
    for i, s in enumerate(secs):
        pic = f'p{SEC_PHOTO[i]:02d}.webp' if i < len(SEC_PHOTO) else ''
        if pic in imgs:
            out.append(f'<figure><img src="{img(pic)}" alt="{e(L(s, "heading", lang))}" loading="lazy" style="max-width:100%;border-radius:12px"></figure>')
        out.append(f'<h3>📍 {e(L(s, "heading", lang))}</h3><p>{e(L(s, "body", lang))}</p>')
        if i == len(secs) // 2 and not for_blogger:
            out.append(ad('slot_mid'))
    out.append(f'''<h2>🍦 {t["eat"]}</h2><div class="talk nyami"><img src="{url('assets/nyami_icecream.webp')}" alt="냐미" width="72">
<p><b>{'냐미' if lang == 'ko' else 'Nyami'}</b> {e(t['hello_n'])}</p></div><ul class="eat">''' +
               ''.join(f'<li>{e(m["ko"] if lang == "ko" else m["en"])}</li>' for m in ep['must_eat']) + '</ul>')
    if ep.get('restaurants'):
        cards = ''.join(f'<div class="shop"><b>{e(L(r, "name", lang))}</b><span>🍴 {e(L(r, "menu", lang))}</span>'
                        f'<span>📍 {e(L(r, "address", lang))}</span>' + (f'<span>🕒 {e(L(r, "hours", lang))}</span>' if L(r, "hours", lang) else '')
                        + '</div>' for r in ep['restaurants'])
        out.append(f'<h2>🍽 {t["where"]}</h2><div class="shops">{cards}</div>')
    lg = 'ko' if lang == 'ko' else 'en'
    out.append(f'<h2>🗺 {t["info"]}</h2><div class="tw"><table class="info">' + ''.join(
        f'<tr><th>{k}</th><td>{e(v)}</td></tr>' for k, v in [(t['addr'], inf[f'address_{lg}']), (t['best'], inf[f'best_{lg}']),
                                                           (t['go'], inf[f'transport_{lg}']), (t['tip'], inf[f'tip_{lg}'])]) + '</table></div>')
    links = [(t['stay'], af.get('stay')), (t['tour'], af.get('tour')), (t['goods'], af.get('goods'))]
    if any(u for _, u in links) or not for_blogger:
        out.append(f'<h2>✈️ {t["prep"]}</h2><div class="cta">' + ''.join(
            f'<a class="btn" href="{e(u)}" rel="sponsored noopener" target="_blank">{e(x)} →</a>' if u
            else f'<span class="btn off">{e(x)} {t["placeholder"]}</span>' for x, u in links if u or not for_blogger) + '</div>')
        if any(u for _, u in links):
            out.append(f'<p class="small">{e(af["disclosure"])}</p>')
    out.append(f'<p>{e(L(b, "closing", lang))}</p>')
    if not for_blogger:
        out.append(ad('slot_bottom'))
    if for_blogger and CFG['blogger'].get('link_to_site') and base():
        out.append(f'<p>👉 <a href="{page_url(ep, "ko")}">한국어 가이드</a> · <a href="{page_url(ep, "en")}">English guide</a></p>')
    cr = ep.get('credits', [])
    out.append(f'<p class="small">{t["check"]}<br>{t["photo"]}: {e("; ".join(cr)) if cr else "-"}<br>'
               + (f'{t["src"]}: ' + ' '.join(f'<a href="{e(u)}" rel="nofollow">[{i + 1}]</a>' for i, u in enumerate(ep.get('sources', [])[:8]))
                  if ep.get('sources') else '') + '</p>')
    return '\n'.join(x for x in out if x)


# ---------- 페이지 ----------
def build_page(ep, lang, eps):
    t = T[lang]
    title = L(ep.get('blog', {}), 'title', lang) or f"{ep['place_ko']}"
    place = ep['place_ko'] if lang == 'ko' else ep['place_en']
    desc = f"{place} — {ep['hook_ko'] if lang == 'ko' else ep.get('hook_en', '')}. {L(ep.get('blog', {}), 'intro', lang)[:110]}"
    canon = page_url(ep, lang)
    alt = {'ko': page_url(ep, 'ko'), 'en': page_url(ep, 'en'), 'x-default': page_url(ep, 'ko')}
    og = url(f"img/{ep['id']}/cover.jpg")
    ld = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title[:110], 'image': [og],
          'datePublished': ep.get('date'), 'inLanguage': lang, 'author': {'@type': 'Organization', 'name': 'Where to, Meow?'},
          'about': {'@type': 'TouristDestination', 'name': place}}
    other = page_url(ep, t['other_lang'])
    more = [x for x in eps if x['id'] != ep['id']][:4]
    cards = ''.join(card(x, lang) for x in more)
    body = article_html(ep, lang, url(f"img/{ep['id']}"))
    badge = t['dom'] if ep['region'] == 'domestic' else t['ovs']
    return (head(f"{title} | 오늘 어디냥?", desc, lang, canon, alt, og, ld) + header(lang, other) +
            f'''<main class="post"><p class="crumb"><a href="{url(lang + '/')}">{t['home']}</a> › {badge}</p>
<h1>{e(title)}</h1><p class="meta"><span class="badge {ep['region']}">{badge}</span> {ep.get('date', '')}</p>
<article>{body}</article>
{f'<section class="more"><h2>{t["more"]}</h2><div class="grid">{cards}</div></section>' if cards else ''}</main>''' + footer(lang))


def card(ep, lang):
    t = T[lang]
    place = ep['place_ko'] if lang == 'ko' else ep['place_en']
    hook = ep['hook_ko'] if lang == 'ko' else ep.get('hook_en', '')
    badge = t['dom'] if ep['region'] == 'domestic' else t['ovs']
    return (f'<a class="card" data-region="{ep["region"]}" href="{page_url(ep, lang)}">'
            f'<img src="{url("img/" + ep["id"] + "/thumb.webp")}" alt="{e(place)}" loading="lazy">'
            f'<span class="badge {ep["region"]}">{badge}</span><b>{e(place)}</b><small>{e(hook)}</small></a>')


def build_index(lang, eps):
    t = T[lang]
    cards = ''.join(card(x, lang) for x in eps)
    return (head('오늘 어디냥? Where to, Meow? — ' + t['desc'], t['desc'], lang, url(lang + '/'),
                 {'ko': url('ko/'), 'en': url('en/')}, url(f"img/{eps[0]['id']}/cover.jpg") if eps else None) +
            header(lang, url(t['other_lang'] + '/')) +
            f'''<main><section class="hero"><img src="{url('assets/hermi_wave.webp')}" alt="Hermi" width="120">
<div><h1>오늘 어디냥?<small>Where to, Meow?</small></h1><p>{t['desc']}</p></div>
<img src="{url('assets/nyami_icecream.webp')}" alt="Nyami" width="120"></section>
<div class="filters"><button data-f="all" class="on">{t['all']}</button><button data-f="domestic" id="domestic">{t['dom']}</button>
<button data-f="overseas" id="overseas">{t['ovs']}</button></div>{ad('slot_top')}
<div class="grid">{cards}</div></main>
<script>const b=[...document.querySelectorAll('.filters button')];function f(x){{b.forEach(y=>y.classList.toggle('on',y.dataset.f==x));
document.querySelectorAll('.grid .card').forEach(c=>c.style.display=(x=='all'||c.dataset.region==x)?'':'none')}}
b.forEach(y=>y.onclick=()=>f(y.dataset.f));if(location.hash)f(location.hash.slice(1));</script>''' + footer(lang))


def feed(lang, eps):
    items = ''.join(f'''<item><title>{e(L(x.get('blog', {}), 'title', lang))}</title><link>{page_url(x, lang)}</link>
<guid>{page_url(x, lang)}</guid><pubDate>{x.get('date', '')}</pubDate></item>''' for x in eps[:30])
    return (f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>오늘 어디냥? Where to, Meow?</title>'
            f'<link>{url(lang + "/")}</link><description>{e(T[lang]["desc"])}</description>{items}</channel></rss>')


# ---------- 개인정보처리방침 / 이용약관 / 소개 ----------
EFFECTIVE = '2026-11-15'


def contact_line():
    c = CFG['channel']
    em = c.get('contact_email')
    ig = c.get('ig_handle', '').lstrip('@')
    parts = []
    if em:
        parts.append(f'<a href="mailto:{e(em)}">{e(em)}</a>')
    if ig:
        parts.append(f'<a href="https://www.instagram.com/{ig}/">Instagram @{ig} (DM)</a>')
    return ' · '.join(parts) or '-'


def legal_page(title, body):
    return (head(f'{title} | 오늘 어디냥?', title, 'ko', url(title_slug[title] + '/')) + header('ko', url('en/')) +
            f'<main class="post"><h1>{title}</h1><article>{body}</article></main>' + footer('ko'))


title_slug = {'개인정보처리방침 · Privacy Policy': 'privacy', '이용약관 · Terms of Service': 'terms', '소개 · About': 'about'}


def privacy_html():
    return f"""<p class="small">시행일 Effective date: {EFFECTIVE}</p>
<h2>1. 수집하는 개인정보</h2><p>'오늘 어디냥? (Where to, Meow?)'(이하 '사이트')는 회원가입, 댓글, 문의 양식 등을 운영하지 않으며 방문자의 이름·연락처 등 개인정보를 직접 수집하지 않습니다.</p>
<h2>2. 쿠키 및 제3자 서비스</h2><p>사이트는 다음 제3자 서비스를 이용할 수 있으며, 이들 서비스가 쿠키 등을 통해 정보를 처리할 수 있습니다.</p>
<ul><li><b>GitHub Pages</b>(호스팅): 접속 기록(IP 주소 등)이 보안 목적으로 처리될 수 있습니다.</li>
<li><b>Google AdSense</b>(광고, 적용 시): Google 및 파트너는 쿠키를 사용해 방문 기록에 기반한 광고를 게재할 수 있습니다. 맞춤 광고는 <a href="https://adssettings.google.com">Google 광고 설정</a>에서 해제할 수 있습니다.</li>
<li><b>Google Fonts, Instagram 임베드</b>: 글꼴·게시물 표시를 위해 해당 서비스에 접속 정보가 전달될 수 있습니다.</li>
<li><b>제휴 링크</b>(아고다, 마이리얼트립, 클룩, 쿠팡파트너스 등): 링크를 통해 이동하면 해당 업체 정책이 적용됩니다.</li></ul>
<h2>3. Google API 서비스 이용</h2><p>사이트 운영자는 자신이 소유한 Blogger 블로그에 여행 가이드 글을 게시하기 위해서만 Google API(Blogger API)를 사용합니다. 이 과정에서 제3자 사용자의 Google 계정 정보에 접근하거나 이를 수집·저장·공유하지 않습니다. Google API로부터 받은 정보의 사용은 <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API 서비스 사용자 데이터 정책</a>(제한적 사용 요건 포함)을 준수합니다.</p>
<h2>4. 문의</h2><p>개인정보 관련 문의: {contact_line()}</p>
<hr><h2>Privacy Policy (English)</h2>
<p>'Where to, Meow?' does not operate sign-ups, comments or contact forms and does not directly collect personal information.
Third-party services may process data via cookies: GitHub Pages (hosting logs), Google AdSense (if enabled; you can opt out of personalized ads at <a href="https://adssettings.google.com">Google Ads Settings</a>), Google Fonts, Instagram embeds, and affiliate partners whose own policies apply once you leave this site.
The operator uses the Google Blogger API solely to publish posts to the operator's own blog and does not access, collect, store or share any other user's Google data. Use of information received from Google APIs adheres to the <a href="https://developers.google.com/terms/api-services-user-data-policy">Google API Services User Data Policy</a>, including the Limited Use requirements.
Contact: {contact_line()}</p>"""


def terms_html():
    af = CFG['affiliates']['disclosure']
    return f"""<p class="small">시행일 Effective date: {EFFECTIVE}</p>
<h2>1. 콘텐츠 성격</h2><p>사이트의 여행지·맛집·교통·시기 정보는 공개 자료를 바탕으로 작성한 참고용 정보입니다. 영업시간·요금·운행 정보는 변동될 수 있으므로 방문 전 반드시 공식 채널에서 확인하시기 바랍니다. 정보 이용으로 발생한 손해에 대해 운영자는 책임지지 않습니다.</p>
<h2>2. AI 활용 고지</h2><p>캐릭터 '허미'와 '냐미'는 AI로 제작되었으며, 원고 작성과 장소 선정에 AI가 활용됩니다. 운영자는 정확성을 위해 출처 확인 절차를 두고 있으나 오류가 있을 수 있습니다.</p>
<h2>3. 저작권</h2><p>캐릭터·디자인·원고의 저작권은 운영자에게 있으며 무단 복제·배포를 금합니다. 사진은 한국관광공사(공공누리 제1유형), Wikimedia Commons(CC0·CC BY), Pixabay·Pexels 등 이용이 허락된 자료를 출처와 함께 사용합니다. 권리 침해가 의심되면 아래로 알려주시면 신속히 조치하겠습니다.</p>
<h2>4. 제휴 링크</h2><p>{e(af)}</p>
<h2>5. 문의</h2><p>{contact_line()}</p>
<hr><h2>Terms of Service (English)</h2>
<p>Travel information on this site is for reference only; hours, prices and schedules may change, so please verify with official sources before visiting. The operator is not liable for losses arising from use of the information.
The characters Hermi and Nyami are AI-generated, and AI assists with writing and destination selection.
Characters, design and text are owned by the operator. Photos are used under their licenses (KTO KOGL Type 1, Wikimedia CC0/CC BY, Pixabay, Pexels) with credits. Some links are affiliate links and the operator may earn a commission.
Contact: {contact_line()}</p>"""


def about_html():
    return f"""<div class="talk hermi"><img src="{url('assets/hermi_wave.webp')}" alt="허미" width="72"><p><b>허미 (모험냥)</b> 여행지를 계획하고 코스·시기·가는 법을 소개해요.</p></div>
<div class="talk nyami"><img src="{url('assets/nyami_icecream.webp')}" alt="냐미" width="72"><p><b>냐미 (먹방냥)</b> 꼭 먹어봐야 할 메뉴와 함께 들르면 좋은 곳을 알려줘요.</p></div>
<p>'오늘 어디냥? (Where to, Meow?)'는 두 고양이 캐릭터가 매일 국내·해외 여행지를 한국어·영어로 소개하는 여행 가이드입니다. 인스타그램 릴스와 함께 운영됩니다.</p>
<p>Where to, Meow? is a bilingual (Korean/English) travel guide where two cats introduce a new destination in Korea and beyond every day.</p>
<p>문의 Contact: {contact_line()}</p>"""


def build_legal(w):
    for t, f in (('개인정보처리방침 · Privacy Policy', privacy_html), ('이용약관 · Terms of Service', terms_html), ('소개 · About', about_html)):
        w(f'{title_slug[t]}/index.html', legal_page(t, f()))


def build():
    eps = all_eps()
    w = lambda p, s: (os.makedirs(os.path.dirname(os.path.join(DOCS, p)), exist_ok=True),
                      open(os.path.join(DOCS, p), 'w', encoding='utf8').write(s))
    os.makedirs(os.path.join(DOCS, 'assets'), exist_ok=True)
    for f in glob.glob(os.path.join(ROOT, 'assets', 'site', '*')):
        shutil.copy(f, os.path.join(DOCS, 'assets'))
    for lang in ('ko', 'en'):
        for ep in eps:
            w(f'{lang}/{ep["id"]}/index.html', build_page(ep, lang, eps))
        w(f'{lang}/index.html', build_index(lang, eps))
        w(f'{lang}/feed.xml', feed(lang, eps))
    w('index.html', f'''<!DOCTYPE html><meta charset="utf-8"><title>오늘 어디냥? Where to, Meow?</title>
<link rel="canonical" href="{url('ko/')}"><script>location.replace((navigator.language||'ko').startsWith('ko')?'ko/':'en/')</script>
<a href="ko/">한국어</a> · <a href="en/">English</a>''')
    build_legal(w)
    urls = [url('ko/'), url('en/'), url('about/'), url('privacy/'), url('terms/')] + [page_url(x, l) for x in eps for l in ('ko', 'en')]
    w('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
      ''.join(f'<url><loc>{u}</loc></url>' for u in urls) + '</urlset>')
    w('robots.txt', f'User-agent: *\nAllow: /\nSitemap: {url("sitemap.xml")}\n')
    open(os.path.join(DOCS, '.nojekyll'), 'w').close()
    cl = S.get('adsense', {}).get('client', '')
    if cl:
        w('ads.txt', f'google.com, {cl.replace("ca-", "")}, DIRECT, f08c47fec0942fa0\n')
    if S.get('custom_domain'):
        w('CNAME', S['custom_domain'] + '\n')
    return len(eps)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == 'add':
        add_episode(sys.argv[2], sys.argv[3])
    print('pages for', build(), 'episodes')
