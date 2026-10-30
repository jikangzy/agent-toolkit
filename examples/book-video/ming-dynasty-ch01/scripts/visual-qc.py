"""Verify the rendered silent preview. Outputs are ignored; no synthesis occurs."""
from pathlib import Path
import subprocess,json,hashlib,re,os
from PIL import Image,ImageDraw
p=Path(__file__).resolve().parents[1]
o=p/'.local/visual'
f=Path(os.environ.get('HYPERFRAMES_FFMPEG_PATH',str(o/'ffmpeg-cached.exe')))
probe=Path(os.environ.get('HYPERFRAMES_FFPROBE_PATH',str(p/'.local/tooling/node_modules/@ffprobe-installer/win32-x64/ffprobe.exe')))
v=o/'ming-opening-silent-preview.mp4'
def run(args):
 r=subprocess.run([str(x) for x in args],capture_output=True,text=True,encoding='utf-8',errors='replace');return r
r=run([probe,'-v','error','-show_streams','-show_format','-of','json',v]);assert r.returncode==0,r.stderr
meta=json.loads(r.stdout);(o/'ffprobe.json').write_text(r.stdout,encoding='utf-8')
video=next(x for x in meta['streams'] if x['codec_type']=='video');audio=[x for x in meta['streams'] if x['codec_type']=='audio']
assert (video['width'],video['height'],video['codec_name'],video['r_frame_rate'])==(1080,1920,'h264','30/1')
assert abs(float(meta['format']['duration'])-82)<.1
assert not audio,'Silent preview must have no audio stream'
r=run([f,'-v','error','-i',v,'-f','null','-']);(o/'decode.log').write_text(r.stderr,encoding='utf-8');assert r.returncode==0 and not r.stderr.strip(),r.stderr
r=run([f,'-hide_banner','-i',v,'-vf','blackdetect=d=0.1:pix_th=0.08:pic_th=0.98','-an','-f','null','-']);(o/'blackdetect.log').write_text(r.stderr,encoding='utf-8');assert r.returncode==0
blacks=re.findall(r'black_start:[^\r\n]+',r.stderr)
frames=o/'decoded-frames';frames.mkdir(exist_ok=True)
times=[4,15,27,38,49,60,69,79]
for i,t in enumerate(times):
 r=run([f,'-y','-v','error','-ss',str(t),'-i',v,'-frames:v','1',frames/f'S{i+1:02}.png']);assert r.returncode==0,r.stderr
sheet=Image.new('RGB',(1080,1050),'#171714');draw=ImageDraw.Draw(sheet)
for i,t in enumerate(times):
 im=Image.open(frames/f'S{i+1:02}.png').convert('RGB');im.thumbnail((260,462));x=(i%4)*270+5;y=(i//4)*525+28;sheet.paste(im,(x,y));draw.text((x,y-20),f'S{i+1:02} | {t}s',fill='#e8dcc2')
sheet.save(o/'contact-sheet.jpg',quality=90)
assets=[]
for a in json.loads((p/'assets/generated/ASSET-MANIFEST.json').read_text(encoding='utf-8'))['assets']:
 file=p/'assets/generated'/a['filename'];im=Image.open(file);im.load();sha=hashlib.sha256(file.read_bytes()).hexdigest();ok=sha==a['sha256'] and im.size==(a['width'],a['height']);assert ok,a['id'];assets.append(dict(id=a['id'],sha256=sha,width=im.width,height=im.height,decode='PASS'))
report=dict(status='PASS' if not blacks else 'FAIL',video_sha256=hashlib.sha256(v.read_bytes()).hexdigest(),bytes=v.stat().st_size,duration=meta['format']['duration'],codec=video['codec_name'],width=video['width'],height=video['height'],fps=video['r_frame_rate'],frames=video.get('nb_frames'),audio_streams=len(audio),full_decode='PASS',black_intervals=blacks,assets=assets,contact_sheet='.local/visual/contact-sheet.jpg')
(o/'render-qc.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='assets'},indent=2));assert not blacks
