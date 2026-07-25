#!/usr/bin/env python3
"""DCT Watermark - Frequency Domain | Ultra JPEG Resistant"""
import os, sys, numpy as np
from PIL import Image

_DCT = np.zeros((8,8))
for i in range(8):
    for j in range(8):
        _DCT[i,j] = np.sqrt(1/8) if i==0 else np.sqrt(2/8)*np.cos(np.pi*(2*j+1)*i/16)
_IDCT = _DCT.T
_dct = lambda b: _DCT @ b @ _DCT.T
_idct = lambda b: _IDCT @ b @ _IDCT.T

EOF = bytes(8)
PAIRS = [(0,1),(1,0),(0,2),(2,0),(1,2),(2,1),(0,3),(3,0),(1,3),(3,1),
         (0,4),(4,0),(2,3),(3,2),(1,4),(4,1),(1,1),(2,2),(0,5),(5,0),
         (0,6),(6,0),(1,5),(5,1),(2,4),(4,2),(3,4),(4,3),(1,6),(6,1),(2,5),(5,2)]
DEFAULT_STRENGTH = 200.0

def _get_pairs():
    return [(PAIRS[i], PAIRS[i+1]) for i in range(0, len(PAIRS), 2)]

def encode(ipath, opath, secret, strength=DEFAULT_STRENGTH):
    data = secret.encode('utf-8') + EOF
    bits = ''.join(format(b,'08b') for b in data)
    pairs = _get_pairs()
    n_pairs = len(pairs)

    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    n_blocks = (h//8) * (w//8)
    bits_needed = len(bits) * n_pairs
    if bits_needed > n_blocks:
        raise ValueError(f'Image too small! Need {bits_needed} blocks')

    idx, bi_idx = 0, 0
    for bi in range(h//8):
        for bj in range(w//8):
            if idx >= len(bits): break
            blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8].copy()
            d = _dct(blk)
            (u1,v1), (u2,v2) = pairs[bi_idx % n_pairs]
            if bits[idx] == '1':
                d[u1,v1] += strength; d[u2,v2] -= strength
            else:
                d[u1,v1] -= strength; d[u2,v2] += strength
            y[bi*8:(bi+1)*8, bj*8:(bj+1)*8] = _idct(d)
            bi_idx += 1
            if bi_idx % n_pairs == 0: idx += 1
        if idx >= len(bits): break

    y = np.clip(y,0,255).astype(np.uint8)
    out = np.zeros((h,w,3),dtype=np.uint8)
    out[:,:,0] = y
    out[:,:,1] = np.array(img)[:,:,1]
    out[:,:,2] = np.array(img)[:,:,2]
    Image.fromarray(out,'YCbCr').convert('RGB').save(opath,'PNG')
    print(f'[OK] {opath}: {len(secret)}chars x{n_pairs}fold strength={strength}')

def decode(ipath, strength=DEFAULT_STRENGTH):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    pairs = _get_pairs()
    n_pairs = len(pairs)
    raw = []
    for bi in range(h//8):
        for bj in range(w//8):
            b = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8]
            d = _dct(b)
            (u1,v1), (u2,v2) = pairs[len(raw) % n_pairs]
            raw.append('1' if d[u1,v1] > d[u2,v2] else '0')
    bits = []
    for i in range(0, len(raw)-n_pairs+1, n_pairs):
        c = raw[i:i+n_pairs]
        bits.append('1' if c.count('1') > n_pairs//2 else '0')
    bs = ''.join(bits)
    res = bytearray()
    for i in range(0, len(bs), 8):
        v = int(bs[i:i+8],2); res.append(v)
        if len(res)>=8 and res[-8:]==EOF: res=res[:-8]; break
    try:
        txt = res.decode('utf-8')
        print(f'[OK] "{txt}"')
        return txt
    except:
        print('[FAIL] No valid watermark'); return None

def jpeg_test(ipath, q):
    jpg = ipath.replace('.png',f'_q{q}.jpg')
    Image.open(ipath).convert('RGB').save(jpg,'JPEG',quality=q)
    return decode(jpg)

def demo():
    d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
    print('='*55); print('  DCT Watermark Demo'); print('='*55)
    print('\n[1/3] Creating test image...')
    img = Image.new('RGB',(512,512))
    for x in range(512):
        for y in range(512):
            img.putpixel((x,y),(int(255*x/512),int(255*y/512),int(128+64*np.sin(x*y/5000))))
    orig = os.path.join(d,'dct_orig.png'); img.save(orig,'PNG')
    print(f'    OK: {orig}')
    print('\n[2/3] Embedding...')
    secret = 'Q=1 works! DCT wm!'
    stego = os.path.join(d,'dct_wm.png')
    encode(orig, stego, secret, strength=200)
    print('\n[3/3] JPEG resistance test...')
    r = decode(stego); print(f'PNG match: {r == secret}')
    for q in [95,80,65,50,40,30,20,10,5,1]:
        r2 = jpeg_test(stego,q)
        print(f'  q={q}: {"OK" if r2 else "FAIL"}')
    print('\n'+'='*55)

if __name__ == '__main__':
    if len(sys.argv)<2:
        print('Usage:\n  encode <input> <output> <msg> [strength]\n  decode <image>\n  demo\n  jpeg_test <image> <quality>')
    elif sys.argv[1]=='demo': demo()
    elif sys.argv[1]=='encode' and len(sys.argv)>=5:
        s = float(sys.argv[5]) if len(sys.argv)>5 and sys.argv[5].replace('.','').lstrip('-').isdigit() else DEFAULT_STRENGTH
        encode(sys.argv[2],sys.argv[3],sys.argv[4],s)
    elif sys.argv[1]=='decode' and len(sys.argv)>=3:
        decode(sys.argv[2])
    elif sys.argv[1]=='jpeg_test' and len(sys.argv)>=4:
        jpeg_test(sys.argv[2],int(sys.argv[3]))
    else: print('Invalid args')