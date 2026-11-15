"""오늘 어디냥? 파이프라인
  python src/main.py generate [--date YYYY-MM-DD] [--region domestic|overseas] [--episode path.json]
      → out/<id>/ : reel.mp4, cover.jpg, caption.txt, site_img/, naver_draft.html, episode.json
  python src/main.py publish --dir out/<id> --video-url URL [--cover-url URL] [--site-only]
"""
import argparse, datetime as dt, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate(a):
    import plan, photos, render, tts
    if a.episode:
        ep = json.load(open(a.episode, encoding='utf8'))
        ep.setdefault('date', dt.date.today().isoformat())
    else:
        date = dt.date.fromisoformat(a.date) if a.date else None
        ep = plan.make_episode(date, a.region)
    out = os.path.join(ROOT, 'out', ep['id'])
    os.makedirs(out, exist_ok=True)
    credits = photos.fetch_for_episode(ep, out)
    engines = tts.synth_episode(ep, out)
    bgm_dir = os.path.join(ROOT, 'assets', 'bgm')
    bgms = sorted(f for f in os.listdir(bgm_dir) if f.endswith(('.mp3', '.wav', '.m4a')))
    bgm = os.path.join(bgm_dir, bgms[sum(ep['id'].encode()) % len(bgms)]) if bgms else None
    tmp = os.path.join(out, 'episode.json')
    json.dump(ep, open(tmp, 'w', encoding='utf8'), ensure_ascii=False, indent=2)
    total = render.render(tmp, out, os.path.join(out, 'reel.mp4'), bgm)
    os.system(f'ffmpeg -y -loglevel error -ss 1.2 -i "{out}/reel.mp4" -frames:v 1 -q:v 2 "{out}/cover.jpg"')
    ep['credits'] = credits
    json.dump(ep, open(tmp, 'w', encoding='utf8'), ensure_ascii=False, indent=2)
    site_images(out)
    open(os.path.join(out, 'caption.txt'), 'w', encoding='utf8').write(texts.caption(ep, credits))
    import webgen
    ep['images'] = sorted(os.listdir(os.path.join(out, 'site_img')))
    open(os.path.join(out, 'naver_draft.html'), 'w', encoding='utf8').write(
        '<!DOCTYPE html><meta charset="utf-8"><body style="max-width:720px;margin:auto">' +
        webgen.article_html(ep, 'ko', webgen.url(f"img/{ep['id']}"), for_blogger=True))
    if not a.episode:
        plan.save_history(ep)
    print(json.dumps({'id': ep['id'], 'dir': out, 'seconds': round(total, 1), 'tts': sorted(engines),
                      'place': ep['place_ko']}, ensure_ascii=False))
    gh = os.environ.get('GITHUB_OUTPUT')
    if gh:
        with open(gh, 'a') as f:
            f.write(f"id={ep['id']}\ndir={out}\nplace={ep['place_ko']}\n")


def site_images(out):
    """사이트·블로거용 이미지: cover.jpg(공유 썸네일), thumb.webp(목록), pXX.webp(본문 사진)"""
    from PIL import Image
    d = os.path.join(out, 'site_img'); os.makedirs(d, exist_ok=True)
    cv = Image.open(os.path.join(out, 'cover.jpg')).convert('RGB')
    c2 = cv.copy(); c2.thumbnail((720, 1280)); c2.save(os.path.join(d, 'cover.jpg'), quality=85)
    c3 = cv.copy(); c3.thumbnail((480, 640)); c3.save(os.path.join(d, 'thumb.webp'), quality=80)
    for i in range(10):
        f = os.path.join(out, f'photo_{i:02d}.jpg')
        if os.path.exists(f):
            im = Image.open(f).convert('RGB'); im.thumbnail((1200, 1600))
            im.save(os.path.join(d, f'p{i:02d}.webp'), quality=80)


def publish(a):
    """사이트 등록 → 블로거 게시 → 인스타 릴스 게시 → 사이트에 릴스 임베드 (각 단계는 재실행해도 중복 게시 안 됨)"""
    import webgen, blogger
    ep = webgen.add_episode(os.path.join(a.dir, 'episode.json'), os.path.join(a.dir, 'site_img'))
    webgen.build()
    if blogger.enabled() and not ep.get('blogger_urls'):
        try:
            webgen.set_permalink(ep['id'], None, blogger.post(ep))
        except Exception as e:
            print('블로거 게시 실패(인스타 게시는 계속):', e)
    link = ep.get('ig_permalink')
    if not link and not a.site_only:
        from publish_ig import post_reel
        ko, en = webgen.page_url(ep, 'ko'), webgen.page_url(ep, 'en')
        cap = texts.caption(ep, ep.get('credits', []), ko)
        comment = f'🔗 코스·맛집 전체 가이드 {ko}\n🔗 Full guide (EN) {en}' if webgen.base() else None
        mid, link = post_reel(a.video_url, cap, a.cover_url, comment)
        webgen.set_permalink(ep['id'], link)
    webgen.build()
    res = {'permalink': link, 'page': webgen.page_url(ep, 'ko')}
    json.dump(res, open('result.json', 'w'))
    print(json.dumps(res, ensure_ascii=False))
    gh = os.environ.get('GITHUB_OUTPUT')
    if gh:
        with open(gh, 'a') as f:
            f.write(f'permalink={link}\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    g = sp.add_parser('generate'); g.add_argument('--date'); g.add_argument('--region'); g.add_argument('--episode')
    p = sp.add_parser('publish'); p.add_argument('--dir', required=True); p.add_argument('--video-url', required=True)
    p.add_argument('--cover-url'); p.add_argument('--site-only', action='store_true')
    a = ap.parse_args()
    {'generate': generate, 'publish': publish}[a.cmd](a)
