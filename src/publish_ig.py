"""Instagram 릴스 게시 (Graph API, 비즈니스/크리에이터 계정)
env: IG_USER_ID, IG_ACCESS_TOKEN, (선택) IG_GRAPH_HOST=graph.facebook.com | graph.instagram.com
"""
import os, time
import requests

HOST = os.environ.get('IG_GRAPH_HOST', 'graph.facebook.com')
VER = os.environ.get('IG_GRAPH_VERSION', 'v27.0')
BASE = f'https://{HOST}/{VER}'


def _p(path, **data):
    data['access_token'] = os.environ['IG_ACCESS_TOKEN']
    r = requests.post(f'{BASE}/{path}', data=data, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f'{path}: {r.status_code} {r.text[:500]}')
    return r.json()


def _g(path, **params):
    params['access_token'] = os.environ['IG_ACCESS_TOKEN']
    return requests.get(f'{BASE}/{path}', params=params, timeout=60).json()


def post_reel(video_url, caption, cover_url=None, first_comment=None):
    uid = os.environ['IG_USER_ID']
    data = dict(media_type='REELS', video_url=video_url, caption=caption, share_to_feed='true')
    if cover_url:
        data['cover_url'] = cover_url
    cid = _p(f'{uid}/media', **data)['id']
    for _ in range(60):  # 최대 10분 대기
        st = _g(cid, fields='status_code,status').get('status_code')
        if st == 'FINISHED':
            break
        if st == 'ERROR':
            raise RuntimeError(f'컨테이너 처리 실패: {_g(cid, fields="status")}')
        time.sleep(10)
    mid = _p(f'{uid}/media_publish', creation_id=cid)['id']
    link = _g(mid, fields='permalink').get('permalink', '')
    if first_comment:
        try:
            _p(f'{mid}/comments', message=first_comment)
        except Exception as e:
            print('첫 댓글 실패(무시):', e)
    return mid, link
