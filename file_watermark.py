#!/usr/bin/env python3
"""File Watermark Tool - Universal
在任何文件中嵌入/提取水印，支持批量处理
Supported: PNG, JPEG, ZIP, PDF, Generic (所有文件)
"""
import os, sys, struct, hashlib, glob, zlib
from typing import Optional, List

MAGIC = b'FWMT'
VERSION = 1
EOF_MARK = b'__FWM_EOF__'

def detect_format(path: str) -> str:
    with open(path, 'rb') as f:
        h = f.read(16)
    if h[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    if h[:2] == b'\xff\xd8': return 'jpeg'
    if h[:2] == b'PK':
        if h[2:4] in (b'\x03\x04',): return 'zip'  # ZIP/APK/DOCX/XLSX/PPTX
        return 'zip'
    if h[:5] == b'%PDF-': return 'pdf'
    if h[:2] == b'MZ': return 'exe'       # PE (EXE/DLL/SYS)
    if h[:4] == b'\x1a\x45\xdf\xa3': return 'mkv'
    if h[4:8] == b'ftyp': return 'mp4'    # MP4/MOV
    if h[:4] == b'Rar!': return 'rar'
    if h[:6] == b'\x37\x7a\xbc\xaf\x27\x1c': return '7z'
    return 'unknown'

def pack_wm(data: bytes, password: str = '') -> bytes:
    payload = data
    flag = 0
    if password:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, 100000)
        key = kdf.derive(password.encode())
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, data, None)
        payload = salt + nonce + ct
        flag = 1
    hdr = struct.pack('>4s B B I', MAGIC, VERSION, flag, len(payload))
    return hdr + payload

def unpack_wm(data: bytes, password: str = '') -> Optional[bytes]:
    if len(data) < 10 or data[:4] != MAGIC: return None
    ver, flag, plen = struct.unpack('>B B I', data[4:10])
    if ver > VERSION: return None
    payload = data[10:10+plen]
    if len(payload) != plen: return None
    if flag == 0: return payload
    if flag == 1 and password:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        salt, nonce, ct = payload[:16], payload[16:28], payload[28:]
        kdf = PBKDF2HMAC(hashes.SHA256(), 32, salt, 100000)
        key = kdf.derive(password.encode())
        try: return AESGCM(key).decrypt(nonce, ct, None)
        except: return None
    return None

# ----- PNG -----
def _embed_png(path: str, wm_data: bytes) -> bool:
    with open(path, 'rb') as f: raw = f.read()
    # 找IEND块的起始（包含其长度字段）
    iend_tag = raw.rfind(b'IEND')
    if iend_tag < 4: return False
    iend_start = iend_tag - 4  # IEND块的长度字段开始
    cd = b'watermark\x00' + wm_data
    cl = struct.pack('>I', len(cd))
    cc = struct.pack('>I', zlib.crc32(b'tEXt' + cd) & 0xffffffff)
    # 在IEND整个块之前插入新块
    new_raw = raw[:iend_start] + cl + b'tEXt' + cd + cc + raw[iend_start:]
    with open(path, 'wb') as f: f.write(new_raw)
    return True

def _extract_png(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    # 直接搜索tEXt块（更鲁棒）
    pos = 8
    while pos + 12 <= len(raw):
        length = struct.unpack('>I', raw[pos:pos+4])[0]
        if pos + 12 + length > len(raw): break
        tag = raw[pos+4:pos+8]
        if tag == b'tEXt' and length >= 10:
            cd = raw[pos+8:pos+8+length]
            if cd.startswith(b'watermark\x00'):
                return cd[10:]
        pos += 12 + length
    return None

# ----- JPEG -----
def _embed_jpeg(path: str, wm_data: bytes) -> bool:
    with open(path, 'rb') as f: raw = f.read()
    sos = raw.find(b'\xff\xda')
    if sos < 0: return False
    com = b'\xff\xfe' + struct.pack('>H', len(wm_data)+2) + wm_data
    with open(path, 'wb') as f: f.write(raw[:sos] + com + raw[sos:])
    return True

def _extract_jpeg(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    pos = 2
    while pos < len(raw) - 1:
        if raw[pos] != 0xff: break
        mk = raw[pos+1]
        if mk == 0xfe:
            length = struct.unpack('>H', raw[pos+2:pos+4])[0]
            return raw[pos+4:pos+4+length-2] if length >= 2 else None
        if mk in range(0xd0, 0xda):
            pos += 2
        else:
            length = struct.unpack('>H', raw[pos+2:pos+4])[0]
            pos += 2 + length
        if mk == 0xda: break
    return None

# === ADD_ZIP ===
# ----- ZIP -----
def _embed_zip(path: str, wm_data: bytes) -> bool:
    with open(path, 'rb') as f: raw = f.read()
    eocd = raw.rfind(b'PK\x05\x06')
    if eocd < 0: return False
    prefix = raw[:eocd+20]
    rest = raw[eocd+22:] if eocd+22 <= len(raw) else b''
    with open(path, 'wb') as f:
        f.write(prefix + struct.pack('<H', len(wm_data)) + wm_data + rest)
    return True

def _extract_zip(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    eocd = raw.rfind(b'PK\x05\x06')
    if eocd < 0 or eocd+22 > len(raw): return None
    clen = struct.unpack('<H', raw[eocd+20:eocd+22])[0]
    return raw[eocd+22:eocd+22+clen] if clen > 0 else None

# ----- PDF -----
def _embed_pdf(path: str, wm_data: bytes) -> bool:
    with open(path, 'rb') as f: raw = f.read()
    eof = raw.rfind(b'%%EOF')
    if eof < 0: return False
    with open(path, 'wb') as f:
        f.write(raw[:eof+5] + b'\n%' + MAGIC + struct.pack('>I',len(wm_data)) + wm_data + b'\n%%EOF')
    return True

def _extract_pdf(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    eof = raw.rfind(b'%%EOF')
    if eof < 0: return None
    tail = raw[eof-260:eof] if eof > 260 else raw[:eof]
    idx = tail.find(MAGIC)
    if idx < 0: return None
    plen = struct.unpack('>I', tail[idx+4:idx+8])[0]
    return tail[idx+8:idx+8+plen]

# === ADD_GENERIC ===
# ----- Generic (尾部追加) -----
def _embed_generic(path: str, wm_data: bytes) -> bool:
    with open(path, 'ab') as f:
        f.write(MAGIC + struct.pack('>I', len(wm_data)) + wm_data + EOF_MARK)
    return True

def _extract_generic(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    eof_pos = raw.rfind(EOF_MARK)
    if eof_pos < 0: return None
    # 从EOF_MARK往前逐一检查每个MAGIC位置，验证长度精确匹配
    search_start = max(0, eof_pos - 200)
    for i in range(eof_pos - 8, search_start - 1, -1):
        if raw[i:i+4] == MAGIC:
            plen = struct.unpack('>I', raw[i+4:i+8])[0]
            if i + 8 + plen == eof_pos:  # 精确匹配到EOF_MARK位置
                return raw[i+8:i+8+plen]
    return None

# ----- PE (EXE/DLL) -----
def _embed_pe(path: str, wm_data: bytes) -> bool:
    _embed_generic(path, wm_data)
    # 尝试将PE校验和置零（表示不校验）
    try:
        with open(path, 'r+b') as f:
            f.seek(0x3c); lfanew = struct.unpack('<H', f.read(2))[0]
            f.seek(lfanew + 0x58)
            if int.from_bytes(f.read(4), 'little') != 0:
                f.seek(lfanew + 0x58); f.write(b'\x00\x00\x00\x00')
    except: pass
    return True

def _extract_pe(path: str) -> Optional[bytes]:
    return _extract_generic(path)

# ----- MP4 -----
def _embed_mp4(path: str, wm_data: bytes) -> bool:
    with open(path, 'rb') as f: raw = f.read()
    payload = MAGIC + struct.pack('>I', len(wm_data)) + wm_data
    box = struct.pack('>I', 8 + len(payload)) + b'free' + payload
    with open(path, 'wb') as f: f.write(raw + box)
    return True

def _extract_mp4(path: str) -> Optional[bytes]:
    with open(path, 'rb') as f: raw = f.read()
    pos = 0
    while pos + 8 < len(raw):
        size = struct.unpack('>I', raw[pos:pos+4])[0]
        if size < 8: break
        typ = raw[pos+4:pos+8]
        if typ == b'free' and size > 16:
            inner = raw[pos+8:pos+size]
            idx = inner.find(MAGIC)
            if idx >= 0:
                plen = struct.unpack('>I', inner[idx+4:idx+8])[0]
                if idx + 8 + plen <= len(inner):
                    return inner[idx+8:idx+8+plen]
        pos += size
    return None

def _zlib_crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xffffffff

def embed(path: str, text: str, password: str = '', backup: bool = True) -> str:
    if not os.path.exists(path): return f'[FAIL] 文件不存在: {path}'
    wm_data = pack_wm(text.encode('utf-8'), password)
    fmt = detect_format(path)
    if backup:
        import shutil; shutil.copy2(path, path + '.bak')
    handlers = {'png': _embed_png, 'jpeg': _embed_jpeg, 'zip': _embed_zip,
                 'pdf': _embed_pdf, 'exe': _embed_pe, 'mp4': _embed_mp4}
    handler = handlers.get(fmt, _embed_generic)
    if handler(path, wm_data):
        return f'[OK] {path}\n   格式={fmt}, 水印={len(text)}字' + (' (加密)' if password else '')
    return f'[FAIL] 嵌入失败: {fmt}'

def extract(path: str, password: str = '') -> str:
    if not os.path.exists(path): return f'[FAIL] 文件不存在: {path}'
    fmt = detect_format(path)
    extractors = {'png': _extract_png, 'jpeg': _extract_jpeg, 'zip': _extract_zip,
                  'pdf': _extract_pdf, 'exe': _extract_pe, 'mp4': _extract_mp4}
    handler = extractors.get(fmt, _extract_generic)
    raw = handler(path)
    if raw is None: return f'[FAIL] 未发现水印 (格式={fmt})'
    data = unpack_wm(raw, password)
    if data is None: return f'[FAIL] 水印损坏或密码错误'
    return f'[OK] "{data.decode("utf-8")}"'

# ============================================================
# 批量处理
# ============================================================

def batch_embed(pattern: str, text: str, password: str = '',
                recursive: bool = False, backup: bool = True) -> str:
    files = _glob_files(pattern, recursive)
    if not files: return f'[FAIL] 未匹配到文件: {pattern}'
    ok = 0
    results = []
    for f in files:
        r = embed(f, text, password, backup)
        results.append(r)
        if r.startswith('[OK]'): ok += 1
    return '\n'.join(results) + f'\n=== 批量完成: {ok}/{len(files)} 成功 ==='

def batch_extract(pattern: str, password: str = '',
                  recursive: bool = False) -> str:
    files = _glob_files(pattern, recursive)
    if not files: return f'[FAIL] 未匹配到文件: {pattern}'
    res = []
    for f in files:
        r = extract(f, password)
        res.append(f'[{os.path.basename(f)}] {r}')
    return '\n'.join(res)

def _glob_files(pattern: str, recursive: bool = False) -> List[str]:
    if os.path.isfile(pattern): return [pattern]
    if os.path.isdir(pattern):
        p = pattern.rstrip('/') + '/'
        if recursive:
            return [os.path.join(dp, f) for dp, _, fn in os.walk(pattern) for f in fn]
        return glob.glob(p + '*')
    fs = glob.glob(pattern, recursive=recursive)
    if recursive: fs += glob.glob(pattern + '/**/*', recursive=True)
    return sorted(set(f for f in fs if os.path.isfile(f)))

# ============================================================
# Demo & CLI
# ============================================================

def demo():
    d = os.path.dirname(os.path.abspath(__file__)) or '/storage/emulated/0/By_TC_STA/python'
    print('='*55)
    print('   通用文件水印工具 — 全格式演示')
    print('='*55)
    from PIL import Image
    import zipfile
    wm_text = 'FileWatermark!'

    # 1. PNG
    png_p = os.path.join(d, 'fwm_test.png')
    Image.new('RGB', (100,100), (128,128,128)).save(png_p, 'PNG')
    r1 = embed(png_p, wm_text)
    r1x = extract(png_p)

    # 2. JPEG
    jpg_p = os.path.join(d, 'fwm_test.jpg')
    Image.new('RGB', (100,100), (128,128,128)).save(jpg_p, 'JPEG', quality=85)
    r2 = embed(jpg_p, wm_text)
    r2x = extract(jpg_p)

    # 3. ZIP
    zip_p = os.path.join(d, 'fwm_test.zip')
    with zipfile.ZipFile(zip_p, 'w') as z: z.writestr('x.txt', 'test')
    r3 = embed(zip_p, wm_text)
    r3x = extract(zip_p)

    # 4. PDF (模拟)
    pdf_p = os.path.join(d, 'fwm_test.pdf')
    with open(pdf_p, 'wb') as f:
        f.write(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Size 1 >>\n%%EOF')
    r4 = embed(pdf_p, wm_text)
    r4x = extract(pdf_p)

    # 5. 通用 (文本文件)
    txt_p = os.path.join(d, 'fwm_test.txt')
    with open(txt_p, 'w') as f: f.write('Hello World!')
    r5 = embed(txt_p, wm_text)
    r5x = extract(txt_p)

    print('\n--- 嵌入结果 ---')
    for r in [r1,r2,r3,r4,r5]: print(r)
    print('\n--- 提取验证 ---')
    for r in [r1x,r2x,r3x,r4x,r5x]: print(r)

    # 清理
    for f in [png_p, jpg_p, zip_p, pdf_p, txt_p,
              png_p+'.bak', jpg_p+'.bak', zip_p+'.bak', pdf_p+'.bak', txt_p+'.bak']:
        if os.path.exists(f): os.remove(f)
    print('\n'+'='*55)
    print('全部格式验证完成！')

def show_types():
    print('''支持的格式:
  PNG   → tEXt辅助块 (无损元数据)
  JPEG  → COM注释标记 (不影响解码)
  ZIP   → EOCD注释区域 → 也支持 APK/DOCX/XLSX/PPTX
  PDF   → %%EOF后追加 (阅读器忽略)
  PE    → 尾部安全区 → EXE/DLL/SYS
  MP4   → free box容器 → 也支持 MOV
  通用   → 尾部魔数标记 → MKV/RAR/7z/所有其他文件''')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage:')
        print('  embed <file> <text> [password] [--nobackup]')
        print('  extract <file> [password]')
        print('  batch <pattern> <text> [password] [--recursive] [--nobackup]')
        print('  bextract <pattern> [password] [--recursive]')
        print('  demo')
        print('  types')
    elif sys.argv[1] == 'demo': demo()
    elif sys.argv[1] == 'types': show_types()
    elif sys.argv[1] == 'embed' and len(sys.argv) >= 4:
        pw = sys.argv[4] if len(sys.argv) >= 5 and not sys.argv[4].startswith('--') else ''
        bk = '--nobackup' not in sys.argv
        print(embed(sys.argv[2], sys.argv[3], pw, bk))
    elif sys.argv[1] == 'extract' and len(sys.argv) >= 3:
        pw = sys.argv[3] if len(sys.argv) >= 4 else ''
        print(extract(sys.argv[2], pw))
    elif sys.argv[1] == 'batch' and len(sys.argv) >= 4:
        pw = ''
        rec = False
        bk = True
        for arg in sys.argv[4:]:
            if arg.startswith('--pw='): pw = arg[5:]
            elif arg == '--recursive': rec = True
            elif arg == '--nobackup': bk = False
        print(batch_embed(sys.argv[2], sys.argv[3], pw, rec, bk))
    elif sys.argv[1] == 'bextract' and len(sys.argv) >= 3:
        pw = ''
        rec = False
        for arg in sys.argv[3:]:
            if arg.startswith('--pw='): pw = arg[5:]
            elif arg == '--recursive': rec = True
        print(batch_extract(sys.argv[2], pw, rec))
    else:
        print('Invalid args. Use: demo / types / embed / extract / batch / bextract')
