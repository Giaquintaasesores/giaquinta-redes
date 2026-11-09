"""Reel vertical 1080x1920 con estilo Giaquinta: clips de Mixkit + textos de marca + voz (edge-tts) + musica.

Uso: python3 render_reel.py spec.json carpeta_salida
Requisitos: ffmpeg/ffprobe, playwright (python) con chromium, pip install edge-tts.

spec.json:
{
  "name": "cauciones-fondo-de-reparo",
  "voice": "es-AR-TomasNeural",            # o es-AR-ElenaNeural
  "music_id": "623",                        # id de https://assets.mixkit.co/music/<id>/<id>.mp3
  "tag": "CAUCIONES",                       # etiqueta dorada por defecto
  "scenes": [
    {"clip": "1436", "ss": 1.0, "h1": "Titulo grande", "p": "bajada opcional", "num": null, "tag": null,
     "vo": "texto que dice la voz"}
  ],
  "end": {"tag": "CAUCIONES", "h1": "Armamos tu carpeta sin compromiso.", "p": "Con DNI y los últimos 2 balances.",
          "legal": "Emisión sujeta a evaluación de la compañía aseguradora.", "vo": "..."}
}
"clip" es el id de un video de Mixkit (https://assets.mixkit.co/videos/<id>/<id>-720.mp4, licencia gratuita de uso comercial).
"""
import asyncio, json, os, ssl, subprocess, sys, urllib.request
import edge_tts, edge_tts.communicate as ec
from playwright.async_api import async_playwright

if os.path.exists('/root/.ccr/ca-bundle.crt'):
    ec._SSL_CTX = ssl.create_default_context(cafile='/root/.ccr/ca-bundle.crt')

FONT = 'https://cdn.jsdelivr.net/npm/@fontsource/poppins@5.0.8/files/poppins-latin-%s-normal.woff2'
fonts = ''.join("@font-face{font-family:Pop;font-weight:%s;src:url(%s)}" % (w, FONT % w) for w in ['500', '700', '800'])
CSS = fonts + """html,body{margin:0;background:transparent}
.o{position:relative;width:1080px;height:1920px;font-family:Pop,sans-serif;color:#fff;overflow:hidden}
.grad{position:absolute;left:0;right:0;bottom:0;height:1150px;background:linear-gradient(180deg,rgba(0,40,110,0) 0%,rgba(0,40,110,.82) 45%,rgba(0,40,110,.96) 100%)}
.top{position:absolute;left:0;right:0;top:0;height:300px;background:linear-gradient(180deg,rgba(0,20,60,.65),rgba(0,20,60,0))}
.logo{position:absolute;left:80px;top:90px;line-height:1}.logo b{font-weight:700;font-size:44px;letter-spacing:4px}.logo s{display:block;text-decoration:none;font-size:15px;letter-spacing:7px;margin-top:8px;opacity:.9}
.box{position:absolute;left:80px;right:80px;bottom:300px}
.tag{display:inline-block;background:#F0A93E;color:#00286e;font-weight:700;font-size:30px;letter-spacing:2px;padding:8px 26px;border-radius:999px}
.num{display:inline-flex;width:120px;height:120px;border-radius:50%;background:#F0A93E;color:#00286e;font-weight:800;font-size:70px;align-items:center;justify-content:center;margin-bottom:10px}
h1{margin:26px 0 0;font-weight:800;font-size:88px;line-height:1.05;letter-spacing:-1.5px;text-shadow:0 4px 24px rgba(0,0,0,.35)}
p{margin:26px 0 0;font-size:44px;font-weight:500;line-height:1.25}
.wa{display:inline-block;margin-top:40px;background:#fff;color:#004aad;font-weight:800;font-size:50px;padding:20px 44px;border-radius:999px}
.end{position:absolute;inset:0;background:linear-gradient(150deg,#00286e 0%,#00317f 45%,#0047ab 100%)}
.ring{position:absolute;right:-260px;bottom:-260px;width:1000px;height:1000px;border-radius:50%;border:120px solid rgba(255,255,255,.05)}
.legal{position:absolute;left:80px;right:80px;bottom:110px;font-size:26px;opacity:.75;line-height:1.35}"""

VF = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
ENC = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-an']
UA = {'User-Agent': 'Mozilla/5.0'}


def page(inner, end=False):
    bg = '<div class=end></div><div class=ring></div>' if end else '<div class=top></div><div class=grad></div>'
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body><div class='o' id='o'>{bg}<div class='logo'><b>GIAQUINTA</b><s>ASESORES DE SEGUROS</s></div>{inner}</div></body></html>"


def scene_html(s, default_tag):
    head = f"<div class='num'>{s['num']}</div><br>" if s.get('num') else f"<span class='tag'>{s.get('tag') or default_tag}</span>"
    return page(f"<div class='box'>{head}<h1>{s['h1']}</h1>" + (f"<p>{s['p']}</p>" if s.get('p') else "") + "</div>")


def end_html(e, default_tag):
    legal = e.get('legal', '')
    legal_html = (legal + '<br>' if legal else '') + '+15 años · San Martín 4143, Neuquén'
    return page(f"<div class='box' style='bottom:430px'><span class='tag'>{e.get('tag') or default_tag}</span><h1>{e['h1']}</h1>"
                + (f"<p>{e['p']}</p>" if e.get('p') else "")
                + f"<span class='wa'>WhatsApp 299 620-0998</span></div><div class='legal'>{legal_html}</div>", end=True)


def fetch(url, path):
    if not os.path.exists(path):
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            open(path, 'wb').write(r.read())


def dur(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip())


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-800:])


async def main(spec_path, out_dir):
    spec = json.load(open(spec_path))
    name, tag = spec['name'], spec.get('tag', 'SEGUROS')
    voice = spec.get('voice', 'es-AR-TomasNeural')
    work = os.path.join(out_dir, 'work_' + name)
    os.makedirs(work, exist_ok=True)
    items = [(s['clip'], s.get('ss', 1.0), scene_html(s, tag), s['vo']) for s in spec['scenes']]
    items.append((None, 0, end_html(spec['end'], tag), spec['end']['vo']))

    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page(viewport={'width': 1080, 'height': 1920})
        for k, (clip, _, html, vo) in enumerate(items):
            o = f'{work}/{k}'
            open(o + '.html', 'w').write(html)
            await pg.goto('file://' + os.path.abspath(o + '.html'))
            await pg.evaluate('document.fonts.ready')
            await pg.wait_for_timeout(500)
            await pg.locator('#o').screenshot(path=o + '.png', omit_background=True)
            await edge_tts.Communicate(vo, voice, rate=spec.get('rate', '+4%')).save(o + '.mp3')
            if clip:
                fetch(f'https://assets.mixkit.co/videos/{clip}/{clip}-720.mp4', f'{work}/clip_{clip}.mp4')
        await b.close()

    music = f'{work}/music.mp3'
    fetch(f"https://assets.mixkit.co/music/{spec.get('music_id', '623')}/{spec.get('music_id', '623')}.mp3", music)

    files, starts, t = [], [], 0.0
    for k, (clip, ss, _, _) in enumerate(items):
        o = f'{work}/{k}'
        d = round(dur(o + '.mp3') + (0.9 if clip is None else 0.7), 2)
        tmp = o + '.tmp.mp4'
        if clip:
            fc = f"[0:v]{VF},trim=duration={d},setpts=PTS-STARTPTS[b];[1:v]format=rgba,fade=in:st=0.15:d=0.45:alpha=1[o];[b][o]overlay=shortest=1,format=yuv420p"
            run(['ffmpeg', '-y', '-v', 'error', '-ss', str(ss), '-i', f'{work}/clip_{clip}.mp4', '-loop', '1', '-framerate', '30', '-i', o + '.png', '-filter_complex', fc, '-t', str(d)] + ENC + [tmp])
        else:
            run(['ffmpeg', '-y', '-v', 'error', '-framerate', '30', '-i', o + '.png', '-vf', f"format=yuv420p,loop=-1:1,trim=duration={d},fade=in:st=0:d=0.3"] + ENC + [tmp])
        os.replace(tmp, o + '.mp4')
        files.append(o + '.mp4'); starts.append(t); t += d

    lst = f'{work}/list.txt'
    open(lst, 'w').write(''.join(f"file '{os.path.abspath(f)}'\n" for f in files))
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', f'{work}/video.mp4'])
    ins, fc = [], []
    for k in range(len(items)):
        ins += ['-i', f'{work}/{k}.mp3']
        ms = int((starts[k] + 0.25) * 1000)
        fc.append(f'[{k+1}:a]adelay={ms}|{ms}[a{k}]')
    n = len(items)
    fc.append(f'[{n+1}:a]atrim=0:{t},volume=0.12,afade=t=out:st={t-1.5}:d=1.5[m]')
    fc.append(''.join(f'[a{k}]' for k in range(n)) + f'[m]amix=inputs={n+1}:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]')
    out = os.path.join(out_dir, name + '.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-i', f'{work}/video.mp4'] + ins + ['-i', music, '-filter_complex', ';'.join(fc),
         '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-t', str(t), '-movflags', '+faststart', out + '.tmp.mp4'])
    os.replace(out + '.tmp.mp4', out)
    # cuadros de control para revisar antes de entregar
    for i, s in enumerate(starts):
        run(['ffmpeg', '-y', '-v', 'error', '-ss', str(s + 1.2), '-i', out, '-frames:v', '1', '-vf', 'scale=360:640', f'{work}/check_{i}.jpg'])
    print(out, round(t, 1), os.path.getsize(out))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1], sys.argv[2]))
