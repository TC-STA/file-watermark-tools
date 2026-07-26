#!/usr/bin/env python3
"""DCT Watermark - QQ传输优化版 | 最低频系数+高强度+高冗余"""
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
# 只保留最低频的4对系数 —— 抗JPEG量化最强
PAIRS = [(0,1),(1,0),(0,2),(2,0),(1,1),(2,2),(0,3),(3,0)]
QQ_STRENGTH = 600
QQ_REPEAT = 16

def _get_pairs():
    return [(PAIRS[i], PAIRS[i+1]) for i in range(0, len(PAIRS), 2)]

def encode(ipath, opath, secret, strength=QQ_STRENGTH, repeat=QQ_REPEAT):
    data = secret.encode('utf-8') + EOF
    bits = ''.join(format(b,'08b') for b in data)
    pairs = _get_pairs()
    n_pairs = len(pairs)
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    blocks_needed = len(bits) * repeat
    max_blocks = (h//8) * (w//8)
    if blocks_needed > max_blocks:
        raise ValueError(f'图太小! 需要{blocks_needed}块, 只有{max_blocks}块')
    for bi in range(h//8):
        for bj in range(w//8):
            block_idx = bi * (w//8) + bj
            bit_idx = block_idx // repeat
            if bit_idx >= len(bits): break
            blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8].copy()
            d = _dct(blk)
            pi = block_idx % n_pairs
            (u1,v1), (u2,v2) = pairs[pi]
            bit = bits[bit_idx]
            if bit == '1':
                d[u1,v1] += strength; d[u2,v2] -= strength
            else:
                d[u1,v1] -= strength; d[u2,v2] += strength
            y[bi*8:(bi+1)*8, bj*8:(bj+1)*8] = _idct(d)
    y = np.clip(y,0,255).astype(np.uint8)
    out = np.zeros((h,w,3),dtype=np.uint8)
    out[:,:,0] = y
    out[:,:,1] = np.array(img)[:,:,1]
    out[:,:,2] = np.array(img)[:,:,2]
    Image.fromarray(out,'YCbCr').convert('RGB').save(opath,'PNG')
    print(f'[OK] {opath}: {len(secret)}chars repeat={repeat} strength={strength}')

def decode(ipath, strength=QQ_STRENGTH, repeat=QQ_REPEAT):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    pairs = _get_pairs()
    n_pairs = len(pairs)
    max_blocks = (h//8) * (w//8)
    raw_bits = []
    for bi in range(h//8):
        for bj in range(w//8):
            block_idx = bi * (w//8) + bj
            if block_idx >= max_blocks: break
            b = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8]
            d = _dct(b)
            pi = block_idx % n_pairs
            (u1,v1), (u2,v2) = pairs[pi]
            raw_bits.append('1' if d[u1,v1] > d[u2,v2] else '0')
    bits = []
    for i in range(0, len(raw_bits) - repeat + 1, repeat):
        chunk = raw_bits[i:i+repeat]
        ones = chunk.count('1')
        bits.append('1' if ones > repeat // 2 else '0')
    bs = ''.join(bits)
    res = bytearray()
    for i in range(0, len(bs), 8):
        if i+8 > len(bs): break
        v = int(bs[i:i+8],2); res.append(v)
        if len(res)>=8 and res[-8:]==EOF:
            res=res[:-8]; break
    try:
        txt = bytes(res).decode('utf-8')
        print(f'[OK] "{txt}"')
        return txt
    except:
        print('[FAIL] No valid watermark'); return None

def jpeg_test(ipath, q):
    jpg = ipath.replace('.png',f'_q{q}.jpg')
    Image.open(ipath).convert('RGB').save(jpg,'JPEG',quality=q)
    return decode(jpg)

def qq_sim_test(ipath):
    """模拟QQ压缩链路：质量85 + 色度4:2:0"""
    jpg = ipath.replace('.png','_qq.jpg')
    Image.open(ipath).convert('RGB').save(jpg,'JPEG',quality=85, subsampling=1)
    return decode(jpg)

if __name__ == '__main__':
    if len(sys.argv)<2:
        print('Usage:')
        print('  encode <input> <output> <msg> [strength] [repeat]')
        print('  decode <image>')
        print('  demo')
        print('  jpeg_test <image> <quality>')
        print('  qq_sim_test <image>')
    elif sys.argv[1]=='demo':
        d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
        print('='*55); print('  DCT Watermark QQ Demo'); print('='*55)
        print('\n[1/3] Create test image...')
        img = Image.new('RGB',(512,512))
        for x in range(512):
            for y in range(512):
                img.putpixel((x,y),(int(255*x/512),int(255*y/512),int(128+64*np.sin(x*y/5000))))
        orig = os.path.join(d,'dct_orig.png'); img.save(orig,'PNG')
        print(f'    OK: {orig}')
        print('\n[2/3] Embedding...')
        secret = 'QQ wm OK!'
        stego = os.path.join(d,'dct_wm.png')
        encode(orig, stego, secret, strength=600, repeat=QQ_REPEAT)
        print('\n[3/3] QQ模拟压缩测试...')
        r = decode(stego); print(f'PNG match: {r == secret}')
        for q in [95,85,75,65,55,45,35,25,15,5,1]:
            r2 = jpeg_test(stego,q)
            print(f'  q={q}: {"OK" if r2 else "FAIL"}')
        r3 = qq_sim_test(stego)
        print(f'  QQ模拟(q85+4:2:0): {"OK" if r3 else "FAIL"}')
        print('\n'+'='*55)
    elif sys.argv[1]=='encode' and len(sys.argv)>=5:
        s = float(sys.argv[5]) if len(sys.argv)>5 else QQ_STRENGTH
        r = int(sys.argv[6]) if len(sys.argv)>6 else QQ_REPEAT
        encode(sys.argv[2],sys.argv[3],sys.argv[4],s,r)
    elif sys.argv[1]=='decode' and len(sys.argv)>=3:
        decode(sys.argv[2])
    elif sys.argv[1]=='jpeg_test' and len(sys.argv)>=4:
        jpeg_test(sys.argv[2],int(sys.argv[3]))
    elif sys.argv[1]=='qq_sim_test' and len(sys.argv)>=3:
        qq_sim_test(sys.argv[2])
