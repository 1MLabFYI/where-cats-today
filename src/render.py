"""오늘 어디냥? — 릴스 렌더러 (1080x1920, 30fps)
episode.json + photos + tts wav -> mp4
"""
import json, math, os, subprocess, sys, wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = lambda *p: os.path.join(ROOT, 'assets', *p)
W, H, FPS = 1080, 1920, 30
FONT = A('fonts', 'Jua.ttf')
BLUE = (30, 91, 198)      # 허미
PINK = (224, 68, 90)      # 냐미
INK = (35, 38, 60)
SPEAKER = {'hermi': ('허미', BLUE), 'nyami': ('냐미', PINK)}
CHAR_SIDE = {'hermi': 'left', 'nyami': 'right'}


from fontTools.ttLib import TTFont as _TT
_CMAP = set(_TT(FONT).getBestCmap())
FALLBACK = A('fonts', 'DejaVuSans-Bold.ttf')
_fc = {}


def font(sz):
    if sz not in _fc:
        f = ImageFont.truetype(FONT, sz)
        f.fb = ImageFont.truetype(FALLBACK, int(sz * 0.8))
        _fc[sz] = f
    return _fc[sz]


def _runs(s, f):
    """Jua에 없는 글자(·, ① 등)는 대체 폰트로"""
    out, cur, curf = [], '', None
    for ch in s:
        ff = f if (ord(ch) in _CMAP or ch == ' ') else getattr(f, 'fb', f)
        if ff is not curf and cur:
            out.append((cur, curf)); cur = ''
        cur += ch; curf = ff
    if cur:
        out.append((cur, curf))
    return out


def text_w(d, s, f, stroke=0):
    w = 0
    for r, ff in _runs(s, f):
        w += d.textlength(r, font=ff)
    return int(w + 2 * stroke)


def dtext(d, xy, s, font, fill, stroke_width=0, stroke_fill=None):
    x, y = xy
    for r, ff in _runs(s, font):
        dy = (font.size - ff.size) * 0.55 if ff is not font else 0
        d.text((x, y + dy), r, font=ff, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += d.textlength(r, font=ff)


def draw_text_c(d, y, s, f, fill, stroke, scol, x=None):
    """가운데 정렬 텍스트 (배경 박스 없이 외곽선만)"""
    w = text_w(d, s, f, stroke)
    x = (W - w) // 2 if x is None else x
    dtext(d, (x, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=scol)
    return f.size


def wrap(d, s, f, maxw):
    out = []
    for para in s.split('\n'):
        line = ''
        for word in para.split(' '):
            t = (line + ' ' + word).strip()
            if text_w(d, t, f) <= maxw:
                line = t
            else:
                if line:
                    out.append(line)
                line = word
        out.append(line)
    return out


# ---------- background ----------
def load_bg(path, label):
    if path and os.path.exists(path):
        im = Image.open(path).convert('RGB')
    else:  # 사진이 없을 때 쓰는 자리표시자
        im = Image.new('RGB', (W, H))
        g = np.linspace(0, 1, H)[:, None]
        top, bot = np.array([150, 200, 235]), np.array([40, 110, 170])
        arr = (top * (1 - g) + bot * g)[:, None, :].repeat(W, 1).reshape(H, W, 3)
        im = Image.fromarray(arr.astype(np.uint8))
        d = ImageDraw.Draw(im)
        draw_text_c(d, 520, '[ 실사 사진 자리 ]', font(44), (255, 255, 255), 0, None)
        draw_text_c(d, 580, label[:40], font(34), (230, 240, 255), 0, None)
    # cover-fit to 1.12x
    s = max(W * 1.12 / im.width, H * 1.12 / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def kenburns(bg, t, dur, seed):
    z = 1.0 + 0.10 * (t / max(dur, 0.01))          # 1.00 -> 1.10 zoom
    cw, ch = int(bg.width / 1.12 / z * 1.0), int(bg.height / 1.12 / z)
    cw, ch = min(cw, bg.width), min(ch, bg.height)
    dirx = 1 if seed % 2 else -1
    cx = bg.width / 2 + dirx * (bg.width - cw) * 0.35 * (t / max(dur, 0.01))
    cy = bg.height / 2
    box = (int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))
    return bg.crop(box).resize((W, H), Image.BILINEAR)


def vignette():
    """상·하단만 아주 옅게 어둡게 (자막 가독성)"""
    a = np.zeros((H, W), np.float32)
    y = np.arange(H)[:, None]
    a += np.clip((380 - y) / 380, 0, 1) * 110
    a += np.clip((y - 1150) / 770, 0, 1) * 120
    return Image.fromarray(np.dstack([np.zeros((H, W, 3), np.uint8), a.astype(np.uint8)]), 'RGBA')


VIG = None
PREV = [None]


# ---------- characters ----------
_cache = {}


def char_img(name, height):
    k = (name, height)
    if k not in _cache:
        im = Image.open(A('chars', name + '.png')).convert('RGBA')
        s = height / im.height
        _cache[k] = im.resize((int(im.width * s), height), Image.LANCZOS)
    return _cache[k]


def char_pos(t, base_y, idx=0):
    """처음 0.45초 튀어오르며 등장 → 이후 살랑살랑"""
    if t < 0.45:
        p = t / 0.45
        off = (1 - p) ** 2 * 500 - math.sin(p * math.pi) * 40
    else:
        off = math.sin((t - 0.45) * 3.2 + idx) * 7
    return int(base_y + off)


# ---------- static overlays ----------
def overlay_common(ep, sc, d):
    # 좌상단 채널 시그니처
    dtext(d, (48, 70), '오늘 어디냥?', font=font(40), fill=(255, 255, 255), stroke_width=4, stroke_fill=BLUE)
    dtext(d, (52, 120), 'Where to, Meow?', font=font(26), fill=(255, 255, 255), stroke_width=3, stroke_fill=BLUE)
    if sc.get('label_ko'):
        f1, f2 = font(60), font(34)
        draw_text_c(d, 250, sc['label_ko'], f1, (255, 255, 255), 6, INK)
        draw_text_c(d, 330, sc.get('label_en', ''), f2, (255, 244, 200), 4, INK)


def overlay_subtitle(sc, d):
    if not sc.get('subtitle'):
        return
    name, col = SPEAKER[sc['speaker']]
    f = font(54)
    lines = wrap(d, sc['subtitle'], f, 940)
    y0 = 975 - (len(lines) - 1) * 70
    dtext(d, ((W - text_w(d, name, font(38), 4)) // 2, y0 - 62), name, font=font(38), fill=col,
           stroke_width=4, stroke_fill=(255, 255, 255))
    for i, ln in enumerate(lines):
        draw_text_c(d, y0 + i * 70, ln, f, (255, 255, 255), 5, col)


def overlay_cover(ep, d):
    draw_text_c(d, 300, '오늘 어디냥?', font(150), (255, 255, 255), 12, BLUE)
    draw_text_c(d, 475, 'Where to, Meow?', font(70), (255, 236, 150), 7, BLUE)
    badge = '국내편 · KOREA' if ep['region'] == 'domestic' else '해외편 · WORLD'
    bf = font(40)
    bw = text_w(d, badge, bf) + 60
    bx = (W - bw) // 2
    d.rounded_rectangle((bx, 595, bx + bw, 660), 33, fill=PINK if ep['region'] == 'domestic' else BLUE)
    draw_text_c(d, 603, badge, bf, (255, 255, 255), 0, None)
    draw_text_c(d, 700, f"{ep['place_ko']} · {ep['place_en']}", font(96), (255, 255, 255), 8, INK)
    draw_text_c(d, 830, ep['hook_ko'], font(56), (255, 255, 255), 5, PINK)
    draw_text_c(d, 905, ep.get('hook_en', ''), font(36), (255, 255, 255), 4, INK)


def overlay_info(ep, d, base):
    inf = ep['info']
    card = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((60, 230, W - 60, 1180), 44, fill=(255, 255, 255, 228))
    base.alpha_composite(card)
    draw_text_c(d, 270, '여행 정보 · Travel Info', font(58), BLUE, 0, None)
    rows = [('위치', 'Where', inf['address_ko'], inf['address_en']),
            ('베스트 시기', 'Best time', inf['best_ko'], inf['best_en']),
            ('가는 법', 'Getting there', inf['transport_ko'], inf['transport_en']),
            ('꿀팁', 'Tip', inf['tip_ko'], inf['tip_en'])]
    y = 380
    for ko, en, vk, ve in rows:
        dtext(d, (110, y), f'{ko}', font=font(36), fill=PINK)
        dtext(d, (110 + text_w(d, ko, font(36)) + 14, y + 8), en, font=font(26), fill=(150, 150, 165))
        y += 50
        for ln in wrap(d, vk, font(40), 850):
            dtext(d, (110, y), ln, font=font(40), fill=INK); y += 50
        for ln in wrap(d, ve, font(28), 850):
            dtext(d, (110, y), ln, font=font(28), fill=(110, 115, 135)); y += 36
        y += 26


def overlay_summary(ep, sc, d):
    draw_text_c(d, 260, '오늘의 냥행 요약', font(64), (255, 255, 255), 6, BLUE)
    draw_text_c(d, 345, f"{ep['place_ko']} · {ep['place_en']}", font(40), (255, 240, 190), 4, INK)
    y = 450
    for s in sc['summary']:
        f = font(52)
        w = text_w(d, '✓ ' + s, f, 5)
        x = (W - w) // 2
        d.ellipse((x, y + 10, x + 40, y + 50), fill=PINK)
        d.line((x + 10, y + 30, x + 18, y + 40, x + 31, y + 20), fill=(255, 255, 255), width=5)
        dtext(d, (x + 56, y), s, font=f, fill=(255, 255, 255), stroke_width=5, stroke_fill=INK)
        y += 84
    draw_text_c(d, 760, '허미냐미 냥행기', font(104), (255, 255, 255), 10, PINK)
    draw_text_c(d, 890, "Hermi & Nyami's Travel Diary", font(44), (255, 255, 255), 5, BLUE)
    draw_text_c(d, 970, '저장하고 같이 가냥!  Save & go together!', font(40), (255, 236, 150), 4, INK)


# ---------- scene render ----------
def scene_frames(ep, sc, idx, bg, dur):
    global VIG
    VIG = VIG or vignette()
    static = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(static)
    if sc['type'] == 'cover':
        overlay_cover(ep, d)
        chars = [('hermi_wave', 'left', 620), ('nyami_walk', 'right', 600)]
    elif sc['type'] == 'info':
        overlay_common(ep, {}, d)
        overlay_info(ep, d, static)
        chars = [(sc.get('pose', 'hermi_point'), 'right', 520)]
    elif sc['type'] == 'summary':
        overlay_common(ep, {}, d)
        overlay_summary(ep, sc, d)
        chars = [('hermi_camera', 'left', 560), ('nyami_icecream', 'right', 560)]
    else:
        overlay_common(ep, sc, d)
        overlay_subtitle(sc, d)
        chars = [(sc['pose'], CHAR_SIDE[sc['speaker']], 600)]
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        fr = kenburns(bg, t, dur, idx).convert('RGBA')
        fr.alpha_composite(VIG)
        fr.alpha_composite(static)
        for j, (name, side, h) in enumerate(chars):
            im = char_img(name, h)
            x = 40 if side == 'left' else W - im.width - 40
            if len(chars) == 1:
                x = 30 if side == 'left' else W - im.width - 30
            y = char_pos(t - j * 0.12, 1660 - h, j)
            fr.alpha_composite(im, (x, max(y, 0)))
        if t < 0.3 and PREV[0] is not None:  # 이전 장면과 크로스페이드
            fr = Image.blend(PREV[0], fr, t / 0.3)
        if i == n - 1:
            PREV[0] = fr
        yield fr.convert('RGB')


def wav_len(p):
    with wave.open(p) as w:
        return w.getnframes() / w.getframerate()


def render(ep_path, work, out_mp4, bgm=None):
    ep = json.load(open(ep_path, encoding='utf8'))
    durs = []
    for i, sc in enumerate(ep['scenes']):
        v = os.path.join(work, f'voice_{i:02d}.wav')
        L = wav_len(v) if os.path.exists(v) else 3.0
        durs.append(max(2.6, L + 0.55))
    silent = os.path.join(work, 'video_silent.mp4')
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                          '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                          '-crf', '20', '-pix_fmt', 'yuv420p', silent], stdin=subprocess.PIPE)
    for i, sc in enumerate(ep['scenes']):
        bg = load_bg(os.path.join(work, f'photo_{i:02d}.jpg'), sc.get('photo_query', ''))
        for fr in scene_frames(ep, sc, i, bg, durs[i]):
            p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
    # audio: voice track (scene offsets) + bgm
    total = sum(durs)
    inputs, filt, k = [], [], 0
    off = 0.0
    for i, dd in enumerate(durs):
        v = os.path.join(work, f'voice_{i:02d}.wav')
        if os.path.exists(v):
            inputs += ['-i', v]
            ms = int((off + 0.35) * 1000)
            filt.append(f'[{k}:a]aresample=44100,adelay={ms}|{ms},apad[v{k}]'); k += 1
        off += dd
    mix = ''.join(f'[v{j}]' for j in range(k))
    graph = ';'.join(filt) + f';{mix}amix=inputs={k}:normalize=0,atrim=0:{total:.2f}[vo]'
    if bgm and os.path.exists(bgm):
        inputs += ['-stream_loop', '-1', '-i', bgm]
        graph += (f';[{k}:a]aresample=44100,volume=0.13,atrim=0:{total:.2f},'
                  f'afade=t=out:st={total - 1.5:.2f}:d=1.5[bg];[vo][bg]amix=inputs=2:normalize=0[m];[m]loudnorm=I=-14:TP=-1.5:LRA=11[a]')
    else:
        graph += ';[vo]loudnorm=I=-14:TP=-1.5:LRA=11[a]'
    audio = os.path.join(work, 'audio.m4a')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *inputs, '-filter_complex', graph, '-map', '[a]',
                    '-c:a', 'aac', '-b:a', '160k', '-ac', '2', audio], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', audio, '-c:v', 'copy',
                    '-c:a', 'copy', '-shortest', '-movflags', '+faststart', out_mp4], check=True)
    return total


if __name__ == '__main__':
    print(render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None))
