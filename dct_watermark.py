#!/usr/bin/env python3
"""DCT Watermark - 随机散布版 | 视觉不可见 + 抗QQ/微信压缩"""
import os, sys, numpy as np
from PIL import Image
import random

_DCT = np.zeros((8,8))
for i in range(8):
    for j in range(8):
        _DCT[i,j] = np.sqrt(1/8) if i==0 else np.sqrt(2/8)*np.cos(np.pi*(2*j+1)*i/16)
_IDCT = _DCT.T
_dct = lambda b: _DCT @ b @ _DCT.T
_idct = lambda b: _IDCT @ b @ _IDCT.T

def _get_pairs():
    # 最低频4对AC系数
    P = [(0,1),(1,0),(0,2),(2,0),(1,1),(2,2),(0,3),(3,0)]
    return [(P[i], P[i+1]) for i in range(0, len(P), 2)]

EOF = bytes(8)
SEED = 12345  # 固定种子，编解码一致

def encode(ipath, opath, secret, strength=80, repeat=16):
    data = secret.encode('utf-8') + EOF
    bits = ''.join(format(b,'08b') for b in data)
    pairs = _get_pairs()
    n_pairs = len(pairs)
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    n_blocks = (h//8) * (w//8)
    needed = len(bits) * repeat
    if needed > n_blocks:
        raise ValueError(f'图太小! 需要{needed}块, 只有{n_blocks}块')
    # 随机散布：生成打乱的块索引
    rng = random.Random(SEED)
    order = list(range(n_blocks))
    rng.shuffle(order)
    for idx in range(needed):
        block_idx = order[idx]
        bi = block_idx // (w//8)
        bj = block_idx % (w//8)
        bit_idx = idx // repeat
        pi = idx % n_pairs
        blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8].copy()
        d = _dct(blk)
        (u1,v1),(u2,v2) = pairs[pi]
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
    print(f'[OK] {opath}: {len(secret)}chars s={strength} r={repeat}')

def decode(ipath, strength=80, repeat=16):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    n_blocks = (h//8) * (w//8)
    pairs = _get_pairs()
    n_pairs = len(pairs)
    # 同样的随机顺序
    rng = random.Random(SEED)
    order = list(range(n_blocks))
    rng.shuffle(order)
    # 收集raw_bits
    raw_bits = []
    for idx in range(n_blocks):
        block_idx = order[idx]
        bi = block_idx // (w//8)
        bj = block_idx % (w//8)
        b = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8]
        d = _dct(b)
        pi = idx % n_pairs
        (u1,v1),(u2,v2) = pairs[pi]
        raw_bits.append('1' if d[u1,v1] > d[u2,v2] else '0')
    # 投票
    bits = []
    for i in range(0, len(raw_bits)-repeat+1, repeat):
        chunk = raw_bits[i:i+repeat]
        ones = chunk.count('1')
        bits.append('1' if ones > repeat//2 else '0')
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
        print('[FAIL] No valid watermark')
        return None

def jpeg_test(ipath, q):
    jpg = ipath.replace('.png',f'_q{q}.jpg')
    Image.open(ipath).convert('RGB').save(jpg,'JPEG',quality=q)
    return decode(jpg)

def qq_sim_test(ipath):
    jpg = ipath.replace('.png','_qq.jpg')
    Image.open(ipath).convert('RGB').save(jpg,'JPEG',quality=85,subsampling=1)
    return decode(jpg)

if __name__ == '__main__':
    if len(sys.argv)<2:
        print('Usage: python3 dct_watermark.py <encode|decode|demo|jpeg_test|qq_sim_test> ...')
    elif sys.argv[1]=='demo':
        d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
        print('='*55)
        print('  DCT Watermark - 随机散布版 Demo')
        print('='*55)
        import numpy as np
        print('\n[1/3] 生成512x512测试图...')
        img = Image.new('RGB',(512,512),(128,128,128))
        for x in range(512):
            for y in range(512):
                v = int(128 + 30*np.sin(x/20)*np.cos(y/30) + 20*np.sin(x*y/10000))
                img.putpixel((x,y),(v,v,v))
        orig = os.path.join(d,'dct_orig.png'); img.save(orig,'PNG')
        print(f'    OK')
        print('\n[2/3] 嵌入水印 (strength=80, repeat=16)...')
        secret = '散布测试!'
        stego = os.path.join(d,'dct_wm.png')
        encode(orig, stego, secret, strength=80, repeat=16)
        print('\n[3/3] 抗压缩测试:')
        r = decode(stego); print(f'  PNG: {"OK" if r==secret else "FAIL"}')
        for q in [85,50,1]:
            r2 = jpeg_test(stego,q)
            print(f'  q={q}: {"OK" if r2==secret else "FAIL"}')
        r3 = qq_sim_test(stego)
        print(f'  QQ模拟: {"OK" if r3==secret else "FAIL"}')
        print('='*55)
    elif sys.argv[1]=='encode' and len(sys.argv)>=5:
        s = float(sys.argv[5]) if len(sys.argv)>5 else 150
        r = int(sys.argv[6]) if len(sys.argv)>6 else 16
        encode(sys.argv[2],sys.argv[3],sys.argv[4],s,r)
    elif sys.argv[1]=='decode' and len(sys.argv)>=3:
        decode(sys.argv[2])
    elif sys.argv[1]=='jpeg_test' and len(sys.argv)>=4:
        jpeg_test(sys.argv[2],int(sys.argv[3]))
    elif sys.argv[1]=='qq_sim_test' and len(sys.argv)>=3:
        qq_sim_test(sys.argv[2])
