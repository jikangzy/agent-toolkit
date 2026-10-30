"""Generate the local, unapproved audition and synthetic mixing test bed."""
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

root = Path(__file__).resolve().parent.parent
models = root / '.local/models'
out = root / '.local/tts'
out.mkdir(parents=True, exist_ok=True)
texts = [
    '一三二八年，朱元璋出生在濠州钟离，也就是今天安徽凤阳一带。',
    '一三四四年，灾荒和疾病袭来。他的父母和多位亲人相继去世。一个家，就这样散了。',
    '一三五二年，朱元璋在濠州加入了郭子兴的队伍。',
]
model = Kokoro(str(models / 'kokoro-v1.1-zh.onnx'), str(models / 'voices-v1.1-zh.bin'))
for index, text in enumerate(texts, 1):
    samples, rate = model.create(text, voice='zf_001', speed=1.0, lang='cmn')
    sf.write(out / f'T0{index}.wav', samples, rate)
    print(f'T0{index}: {len(samples) / rate:.3f}s @ {rate}Hz')
rate = 24000
t = np.arange(10 * rate) / rate
env = np.minimum(1, t / 2) * np.minimum(1, (10 - t) / 2)
samples = env * (.08*np.sin(2*np.pi*110*t) + .035*np.sin(2*np.pi*164.81*t) + .02*np.sin(2*np.pi*220*t))
sf.write(out / 'ambient.wav', samples, rate)
