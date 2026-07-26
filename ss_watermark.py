#!/usr/bin/env python3
"""SS Watermark - 扩频水印 | 真正隐形，无块效应"""
import os, sys, numpy as np
from PIL import Image
import random

# DCT矩阵
_DCT = np.zeros((8,8))
for i in range(8):
    for j in range(8):
        _DCT[i,j] = np.sqrt(1/8) if i==0 else np.sqrt(2/8)*np.cos(np.pi*(2*j+1)*i/16)
_IDCT = _DCT.T
_dct = lambda b: _DCT @ b @ _DCT.T
_idct = lambda b: _IDCT @ b @ _IDCT.T

# ZigZag顺序（跳过DC(0,0)）
_ZZ = []
for s in range(1, 15):
    for i in range(max(0,s-7), min(8,s)):
        j = s - i
        if j < 8:
            _ZZ.append((i,j))
    if len(_ZZ) >= 63: break
_ZZ = _ZZ[:63]

SEED = 54321

def encode(ipath, opath, secret, strength=12, coeffs_per_block=20):
    data = secret.encode('utf-8')
    # 头部2字节存长度 + 数据 + 8字节EOF
    payload = bytes([len(data) >> 8, len(data) & 0xFF]) + data + b'\x00'*8
    bits = ''.join(format(b,'08b') for b in payload)
    n_bits = len(bits)
    
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    bh, bw = h//8, w//8
    n_blocks = bh * bw
    use_c = min(coeffs_per_block, len(_ZZ))
    total = n_blocks * use_c
    cpb = total // n_bits  # coeffs per bit
    if cpb < 50:
        raise ValueError(f'系数太少/bit ({cpb})，换大图或缩短水印')
    
    # 提取系数
    coeffs = np.zeros(total)
    idx = 0
    for bi in range(bh):
        for bj in range(bw):
            blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8].copy()
            d = _dct(blk)
            for k in range(use_c):
                u,v = _ZZ[k]
                coeffs[idx] = d[u,v]
                idx += 1
    
    # 嵌入
    mod = coeffs.copy()
    for b in range(n_bits):
        s = b * cpb
        e = s + cpb
        rng = random.Random(SEED + b)
        pn = np.array([1 if rng.random()>0.5 else -1 for _ in range(e-s)])
        bit_val = 1 if bits[b] == '1' else -1
        mod[s:e] += strength * pn * bit_val
    
    # 写回
    idx = 0
    for bi in range(bh):
        for bj in range(bw):
            blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8].copy()
            d = _dct(blk)
            for k in range(use_c):
                u,v = _ZZ[k]
                d[u,v] = mod[idx]
                idx += 1
            y[bi*8:(bi+1)*8, bj*8:(bj+1)*8] = _idct(d)
    
    y = np.clip(y,0,255).astype(np.uint8)
    out = np.zeros((h,w,3),dtype=np.uint8)
    out[:,:,0] = y
    out[:,:,1] = np.array(img)[:,:,1]
    out[:,:,2] = np.array(img)[:,:,2]
    Image.fromarray(out,'YCbCr').convert('RGB').save(opath,'PNG')
    print(f'[OK] {opath}: {len(secret)}chars s={strength} cpb={cpb}')

def decode(ipath, strength=12, coeffs_per_block=20):
    img = Image.open(ipath).convert('YCbCr')
    y = np.array(img, dtype=np.float64)[:,:,0]
    h, w = y.shape
    bh, bw = h//8, w//8
    n_blocks = bh * bw
    use_c = min(coeffs_per_block, len(_ZZ))
    total = n_blocks * use_c
    
    # 提取系数
    coeffs = np.zeros(total)
    idx = 0
    for bi in range(bh):
        for bj in range(bw):
            blk = y[bi*8:(bi+1)*8, bj*8:(bj+1)*8]
            d = _dct(blk)
            for k in range(use_c):
                u,v = _ZZ[k]
                coeffs[idx] = d[u,v]
                idx += 1
    
    # 先试最短长度（16bits=2字节头），逐步增加
    best = None
    for try_bits in range(16, min(total // 20, 4096) + 1, 8):
        cpb = total // try_bits
        bits = []
        for b in range(try_bits):
            s = b * cpb
            e = s + cpb
            rng = random.Random(SEED + b)
            pn = np.array([1 if rng.random()>0.5 else -1 for _ in range(e-s)])
            corr = np.dot(coeffs[s:e], pn)
            bits.append('1' if corr > 0 else '0')
        bs = ''.join(bits)
        # 解析
        header_len = int(bs[:16], 2)
        data_len = header_len
        if data_len <= 0 or data_len > 1024:
            continue
        total_bytes = 2 + data_len + 8  # header + data + eof
        if total_bytes * 8 > len(bs):
            continue
        # 提取data
        data_bits = bs[16:16+data_len*8]
        eof_bits = bs[16+data_len*8:16+data_len*8+64]
        # 检查EOF
        eof_bytes = bytes(int(eof_bits[i:i+8],2) for i in range(0,64,8))
        if eof_bytes == b'\x00'*8:
            data_bytes = bytes(int(data_bits[i:i+8],2) for i in range(0,len(data_bits),8))
            try:
                txt = data_bytes.decode('utf-8')
                print(f'[OK] "{txt}"')
                return txt
            except:
                pass
    print('[FAIL] No valid watermark')
    return None

def demo():
    d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
    print('='*55)
    print('  SS Watermark - 扩频水印 Demo')
    print('='*55)
    print('\n[1/3] 生成512x512测试图...')
    arr = np.random.RandomState(42).randint(0,255,(512,512,3),dtype=np.uint8)
    img = Image.fromarray(arr,'RGB')
    orig = os.path.join(d,'ss_orig.png')
    img.save(orig,'PNG')
    print('    OK')
    print('\n[2/3] 嵌入扩频水印 (strength=12)...')
    secret = '扩频水印隐形!'
    stego = os.path.join(d,'ss_wm.png')
    encode(orig, stego, secret, strength=12, coeffs_per_block=20)
    print('\n[3/3] 抗压缩测试:')
    r = decode(stego)
    print(f'  PNG: {"OK" if r==secret else "FAIL"}')
    for q in [95,85,50,1]:
        jpg = stego.replace('.png',f'_q{q}.jpg')
        Image.open(stego).convert('RGB').save(jpg,'JPEG',quality=q)
        r2 = decode(jpg)
        print(f'  q={q}: {"OK" if r2==secret else "FAIL"}')
    # QQ模拟
    jpg_qq = stego.replace('.png','_qq.jpg')
    Image.open(stego).convert('RGB').save(jpg_qq,'JPEG',quality=85,subsampling=1)
    r3 = decode(jpg_qq)
    print(f'  QQ模拟: {"OK" if r3==secret else "FAIL"}')
    print('='*55)

if __name__ == '__main__':
    if len(sys.argv)<2:
        print('Usage: python3 ss_watermark.py <encode|decode|demo> ...')
    elif sys.argv[1]=='demo':
        demo()
    elif sys.argv[1]=='encode' and len(sys.argv)>=5:
        s = float(sys.argv[5]) if len(sys.argv)>5 else 12
        c = int(sys.argv[6]) if len(sys.argv)>6 else 20
        encode(sys.argv[2],sys.argv[3],sys.argv[4],s,c)
    elif sys.argv[1]=='decode' and len(sys.argv)>=3:
        decode(sys.argv[2])
    else:
        print('Usage: python3 ss_watermark.py <encode|decode|demo> ...')
