"""구글 블로거 자동 게시 (Blogger API v3, OAuth 리프레시 토큰)
env: BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN, BLOGGER_BLOG_ID
본문은 사이트와 같은 article_html()을 사용 (이미지는 사이트 주소로 연결).
"""
import os
import requests
import webgen

API = 'https://www.googleapis.com/blogger/v3'


def enabled():
    return webgen.CFG['blogger'].get('enabled') and all(os.environ.get(k) for k in (
        'BLOGGER_CLIENT_ID', 'BLOGGER_CLIENT_SECRET', 'BLOGGER_REFRESH_TOKEN', 'BLOGGER_BLOG_ID'))


def access_token():
    r = requests.post('https://oauth2.googleapis.com/token', timeout=30, data=dict(
        client_id=os.environ['BLOGGER_CLIENT_ID'], client_secret=os.environ['BLOGGER_CLIENT_SECRET'],
        refresh_token=os.environ['BLOGGER_REFRESH_TOKEN'], grant_type='refresh_token'))
    r.raise_for_status()
    return r.json()['access_token']


STYLE = ('<style>.talk{display:flex;gap:10px;align-items:flex-start;margin:16px 0}.talk p{border-radius:14px;padding:8px 12px;margin:0}'
         '.talk.hermi p{border:2px solid #1E5BC6}.talk.nyami p{border:2px solid #E0445A}.tw{overflow-x:auto}'
         'table{border-collapse:collapse;width:100%}th,td{border:1px solid #eee;padding:6px 8px;text-align:left}'
         '.btn{display:inline-block;background:#E0445A;color:#fff!important;text-decoration:none;padding:8px 16px;border-radius:20px;margin:4px}'
         '.shop{border-left:5px solid #E0445A;background:#fff8ee;border-radius:10px;padding:8px 12px;margin:8px 0}'
         '.shop b,.shop span{display:block}.small{font-size:12px;color:#888}</style>')


def post(ep):
    """에피소드를 블로거에 게시 → {lang: url}"""
    tok = access_token()
    out = {}
    for lang in webgen.CFG['blogger'].get('languages', ['ko']):
        title = webgen.L(ep.get('blog', {}), 'title', lang) or ep['place_ko']
        body = STYLE + webgen.article_html(ep, lang, webgen.url(f"img/{ep['id']}"), for_blogger=True)
        labels = [ep['place_ko'] if lang == 'ko' else ep['place_en'],
                  ('국내여행' if lang == 'ko' else 'Korea') if ep['region'] == 'domestic' else ('해외여행' if lang == 'ko' else 'World'),
                  '오늘어디냥' if lang == 'ko' else 'WhereToMeow']
        r = requests.post(f"{API}/blogs/{os.environ['BLOGGER_BLOG_ID']}/posts/", timeout=60,
                          headers={'Authorization': f'Bearer {tok}'},
                          json={'kind': 'blogger#post', 'title': title, 'content': body, 'labels': labels})
        if r.status_code >= 300:
            raise RuntimeError(f'Blogger {r.status_code}: {r.text[:400]}')
        out[lang] = r.json().get('url')
    return out
