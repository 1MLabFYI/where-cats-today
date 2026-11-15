import sys,numpy as np,onnxruntime as ort,soundfile as sf,espeakng_loader
from phonemizer.backend.espeak.wrapper import EspeakWrapper
EspeakWrapper.set_library(espeakng_loader.get_library_path())
EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
from phonemizer import phonemize
import os
D=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'models','vits-mimic3-ko_KO-kss_low')+'/'
tok={}
for l in open(D+'tokens.txt',encoding='utf8'):
    l=l.rstrip('\n'); 
    if not l: continue
    p,i=l.rsplit(' ',1); tok[p if p else ' ']=int(i)
sess=ort.InferenceSession(D+'ko_KO-kss_low.onnx')
def synth(text,out,length=1.0):
    ph=phonemize(text,language='ko',backend='espeak',strip=True,preserve_punctuation=True,with_stress=True)
    ids=[tok['^'],tok['_']]
    for w in ph.split(' '):
        for c in w:
            if c in tok: ids+= [tok[c],tok['_']]
        ids+=[tok['#'],tok['_']] if '#' in tok else []
    ids+=[tok['$']]
    x=np.array([ids],dtype=np.int64)
    a=sess.run(None,{'input':x,'input_lengths':np.array([x.shape[1]],dtype=np.int64),'scales':np.array([0.667,length,0.8],dtype=np.float32)})[0].squeeze()
    sf.write(out,a,22050); return ph
if __name__=='__main__':
    print(synth(sys.argv[1],sys.argv[2]))
