"""인스타그램 캡션(한·영 병기)"""
import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = yaml.safe_load(open(os.path.join(ROOT, 'config', 'channel.yaml'), encoding='utf8'))


def caption(ep, credits, blog_url=None):
    c, inf = CFG['channel'], ep['info']
    tags = CFG['hashtags']['base'] + CFG['hashtags'][ep['region']]
    tags += ['#' + ep['place_ko'].replace(' ', '') + '여행', '#' + ep['place_en'].replace(' ', '')]
    tags += ['#' + ep['place_ko'].replace(' ', '') + '맛집']
    eat = '\n'.join(f"· {m['ko']} ({m['en']})" for m in ep['must_eat'])
    rest = '\n'.join(f"· {r['name']} — {r['menu']}\n  {r['address']}" for r in ep.get('restaurants', []))
    blog_line = ('🔗 코스·맛집 전체 가이드는 프로필 링크에서!\nFull guide & restaurant list: link in bio'
                 + (f'\n{blog_url}' if blog_url else ''))
    spots = [s['label_ko'] for s in ep['scenes'][2:5] if s.get('label_ko')]
    spots_en = [s['label_en'] for s in ep['scenes'][2:5] if s.get('label_en')]
    txt = f"""📍 {c['title_ko']} | {ep['place_ko']} — {ep['hook_ko']}
📍 {c['title_en']} | {ep['place_en']} — {ep.get('hook_en', '')}

🐾 허미의 코스 / Hermi's route
{' → '.join(spots)}
{' → '.join(spots_en)}

🍦 냐미의 꼭 먹어봐야 할 메뉴 / Nyami's must-eats
{eat}

🍽 냐미가 찜한 맛집 / Where to eat
{rest}

🗺 여행 정보 / Travel info
· 위치 Where: {inf['address_ko']} / {inf['address_en']}
· 베스트 시기 Best time: {inf['best_ko']} / {inf['best_en']}
· 가는 법 Getting there: {inf['transport_ko']} / {inf['transport_en']}
· 꿀팁 Tip: {inf['tip_ko']} / {inf['tip_en']}

{blog_line}

💾 저장하고 같이 가냥! Save it for your next trip!
— {c['signature_ko']} · {c['signature_en']}

※ 영업시간·요금은 방문 전 확인해 주세요. Please check hours before visiting.
※ 캐릭터는 AI로 제작되었습니다. Characters are AI-generated.
{('📷 ' + '; '.join(credits)) if credits else ''}

{' '.join(dict.fromkeys(tags[:28]))}"""
    return txt[:2150]
