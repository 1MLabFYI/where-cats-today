"""내레이션 TTS.
- 기본: Microsoft Edge 신경망 음성 ko-KR-SunHiNeural (무료, 밝은 여성 음성) — 캐릭터별 피치로 구분
- 대체: 오프라인 KSS 음성 (네트워크가 막힌 환경용)
"""
import asyncio, os, subprocess

VOICE = {
    # 허미: 또랑또랑한 진행자 톤 / 냐미: 한 톤 높고 조금 빠른 애교 톤
    'hermi': dict(voice='ko-KR-SunHiNeural', pitch='+18Hz', rate='+6%'),
    'nyami': dict(voice='ko-KR-SunHiNeural', pitch='+32Hz', rate='+10%'),
    'both':  dict(voice='ko-KR-SunHiNeural', pitch='+24Hz', rate='+8%'),
}


def speaker_of(sc):
    if sc['type'] in ('cover', 'summary'):
        return 'both'
    return sc.get('speaker', 'hermi')


async def _edge(text, out_mp3, v):
    import edge_tts
    await edge_tts.Communicate(text, v['voice'], pitch=v['pitch'], rate=v['rate']).save(out_mp3)


def synth(text, speaker, out_wav):
    v = VOICE[speaker]
    try:
        mp3 = out_wav[:-4] + '.mp3'
        asyncio.run(_edge(text, mp3, v))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp3, '-ar', '44100', '-ac', '1', out_wav], check=True)
        return 'edge'
    except Exception as e:  # 오프라인 대체 음성
        print('edge-tts 실패 → KSS 대체 음성 사용:', e)
        from tts_kss import synth as kss
        raw = out_wav[:-4] + '_raw.wav'
        kss(text, raw, length=0.95)
        shift = 1.10 if speaker == 'hermi' else 1.16
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af',
                        f'asetrate=22050*{shift},aresample=44100,atempo={1/shift*1.05:.3f}', '-ac', '1', out_wav],
                       check=True)
        return 'kss'


def synth_episode(ep, work):
    used = set()
    for i, sc in enumerate(ep['scenes']):
        used.add(synth(sc['narration'], speaker_of(sc), os.path.join(work, f'voice_{i:02d}.wav')))
    return used
