#!/usr/bin/env python3
"""DCT DC Differential Watermark - Extreme JPEG Resistance"""
import os, sys, numpy as np
from PIL import Image

_DCT = np.zeros((8,8))
for i in range(8):
    for j in range(8):
        _DCT[i,j] = np.sqrt(1/8) if i==0 else np.sqrt(2/8)*np.cos(np.pi*(2*j+1)*i/16)
_IDCT = _DCT.T
_dct = lambda b: _DCT @ b @ _DCT.T
_idct = lambda b: _IDCT @ b @ _IDCT.T

EOF = bytes(8); R = 7; TH = 20

def _pairs(h, w):
    nh, nw = h//8, w//8
    ps = []
    for bi in range(nh):
        for bj in range(0, nw-1, 2):
            ps.append(((bi,bj), (bi,bj+1)))
    for bj in range(nw):
        for bi in range(0, nh-1, 2):
            ps.append(((bi,bj), (bi+1,bj)))
    return ps

def encode(ipath, opath, secret, thr=TH):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    pairs = _pairs(h, w)
    total_pairs = len(pairs)
    total_bits = total_pairs // R

    db = secret.encode('utf-8') + EOF
    dbits = ''.join(format(b, '08b') for b in db)
    if len(dbits) > total_bits:
        raise ValueError(f'Need {len(dbits)} bits, max {total_bits}')
    dbits = dbits.ljust(total_bits, '0')

    pairs = pairs[:total_bits * R]
    for pi, ((b1i,b1j), (b2i,b2j)) in enumerate(pairs):
        bit = dbits[pi // R]
        blk = y[b2i*8:(b2i+1)*8, b2j*8:(b2j+1)*8].copy()
        d1 = _dct(y[b1i*8:(b1i+1)*8, b1j*8:(b1j+1)*8])
        d2 = _dct(blk)
        target = d1[0,0] + (thr+2) if bit == '1' else d1[0,0] - (thr+2)
        d2[0,0] = target
        blk2 = np.clip(_idct(d2), 0, 255)
        d2v = _dct(blk2)
        if (bit == '1' and d2v[0,0] <= d1[0,0]) or (bit == '0' and d2v[0,0] >= d1[0,0]):
            d2[0,0] = d1[0,0] + (thr*2+4) if bit == '1' else d1[0,0] - (thr*2+4)
            blk2 = np.clip(_idct(d2), 0, 255)
        y[b2i*8:(b2i+1)*8, b2j*8:(b2j+1)*8] = blk2

    y = np.clip(y, 0, 255).astype(np.uint8)
    out = np.zeros((h,w,3), dtype=np.uint8)
    out[:,:,0] = y
    out[:,:,1] = np.array(img)[:,:,1]
    out[:,:,2] = np.array(img)[:,:,2]
    Image.fromarray(out, 'YCbCr').convert('RGB').save(opath, 'PNG')
    print(f'[OK] {opath}: {len(secret)}chars thr={thr}')

def decode(ipath):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    pairs = _pairs(y.shape[0], y.shape[1])
    raw = []
    for (b1i,b1j), (b2i,b2j) in pairs:
        d1 = _dct(y[b1i*8:(b1i+1)*8, b1j*8:(b1j+1)*8])
        d2 = _dct(y[b2i*8:(b2i+1)*8, b2j*8:(b2j+1)*8])
        raw.append('1' if d2[0,0] > d1[0,0] else '0')
    bits = []
    for i in range(0, len(raw)-R+1, R):
        c = raw[i:i+R]
        bits.append('1' if c.count('1') > R//2 else '0')
    bs = ''.join(bits)
    res = bytearray()
    for i in range(0, len(bs), 8):
        v = int(bs[i:i+8], 2)
        res.append(v)
        if len(res) >= 8 and res[-8:] == EOF:
            res = res[:-8]; break
    try:
        txt = res.decode('utf-8')
        print(f'[OK] Extracted: "{txt}"')
        return txt
    except:
        print('[FAIL] No valid watermark')
        return None

def jpeg_test(ipath, q):
    jpg = ipath.replace('.png', f'_q{q}.jpg')
    Image.open(ipath).convert('RGB').save(jpg, 'JPEG', quality=q)
    return decode(jpg)

def demo():
    d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
    print('='*55); print('  DC Watermark Demo'); print('='*55)
    print('\n[1/4] Creating test image...')
    img = Image.new('RGB', (512, 512))
    for x in range(512):
        for y in range(512):
            img.putpixel((x,y), (int(255*x/512), int(255*y/512), int(128+64*np.sin(x*y/5000))))
    orig = os.path.join(d, 'dc_orig.png')
    img.save(orig, 'PNG')
    print(f'    Created: {orig}')
    print('\n[2/4] Embedding (DC differential)...')
    secret = 'DC watermark - extreme JPEG resistance!'
    stego = os.path.join(d, 'dc_wm.png')
    encode(orig, stego, secret, thr=20)
    print('\n[3/4] Extracting from PNG...')
    r = decode(stego)
    print(f'    Match: {r == secret}')
    print('\n[4/4] JPEG resistance test...')
    for q in [95, 80, 65, 50, 40, 30, 20, 10, 5, 1]:
        r2 = jpeg_test(stego, q)
        print(f'    q={q}: {"OK" if r2 else "FAIL"}')
    print('\nFiles:\n [F] ' + orig + '\n [F] ' + stego)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage:\n  encode <input> <output> <msg> [threshold]\n  decode <image>\n  demo\n  jpeg_test <image> <quality>')
    elif sys.argv[1] == 'demo': demo()
    elif sys.argv[1] == 'encode' and len(sys.argv) >= 5:
        thr = float(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].replace('.','').lstrip('-').isdigit() else 20
        encode(sys.argv[2], sys.argv[3], sys.argv[4], thr)
    elif sys.argv[1] == 'decode' and len(sys.argv) >= 3:
        decode(sys.argv[2])
    elif sys.argv[1] == 'jpeg_test' and len(sys.argv) >= 4:
        jpeg_test(sys.argv[2], int(sys.argv[3]))
    else:
        print('Invalid arguments')