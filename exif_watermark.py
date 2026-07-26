#!/usr/bin/env python3
"""EXIF Watermark - 在EXIF元数据中嵌入/提取水印

适用场景：
  - ✅ 同设备无损传递 (PNG/JPEG)：用UserComment/ImageDescription，空间大
  - ⚠️ QQ/微信传输后：仅DateTime等基础字段可能保留，空间约8~19字符
  - ❌ 自定义字段(UserComment/MakerNote)会被剥离

依赖: pip3 install --break-system-packages piexif
"""
import os, sys
from PIL import Image
from PIL.ExifTags import TAGS

try:
    import piexif
    HAVE_PIEXIF = True
except ImportError:
    HAVE_PIEXIF = False

QQ_KEEP_0TH = {256, 257, 274, 306, 34665}
QQ_KEEP_EXIF = {33434, 33437, 34855, 36867, 36868, 37385, 40960, 40961, 40962, 40963, 41495, 41728, 41729}

def _ensure_piexif():
    if not HAVE_PIEXIF:
        print('[!] 需要piexif库: pip3 install --break-system-packages piexif')
        return False
    return True

def analyze(path):
    if not _ensure_piexif(): return
    img = Image.open(path)
    print(f'\n=== EXIF 分析: {os.path.basename(path)} ===')
    print(f'格式: {img.format} | 尺寸: {img.size[0]}x{img.size[1]}')
    exif_raw = img.info.get('exif')
    if not exif_raw:
        print('[信息] 该图片无EXIF数据')
        return
    exif = piexif.load(exif_raw)
    for ifd_name in ['0th', 'Exif', 'GPS', 'Interop', '1st']:
        ifd = exif.get(ifd_name, {})
        if not ifd: continue
        print(f'\n--- {ifd_name} ---')
        for tag_id, val in ifd.items():
            name = TAGS.get(tag_id, f'0x{tag_id:04X}')
            if ifd_name == '0th' and tag_id in QQ_KEEP_0TH: flag = '\u2705'
            elif ifd_name == 'Exif' and tag_id in QQ_KEEP_EXIF: flag = '\u26a0\ufe0f'
            else: flag = '\u274c'
            if isinstance(val, bytes):
                try: display = val.decode('utf-8', errors='replace')[:60]
                except: display = f'<{len(val)}bytes>'
            else: display = str(val)[:60]
            print(f'  {flag} {name}(0x{tag_id:04X}): {display}')
    print()

def encode(ipath, opath, secret, strategy='auto'):
    if not _ensure_piexif(): return False
    if not opath.lower().endswith(('.jpg','.jpeg','.png')):
        print('[FAIL] 仅支持JPEG/PNG'); return False
    img = Image.open(ipath)
    exif_raw = img.info.get('exif', b'')
    exif_dict = piexif.load(exif_raw) if exif_raw else {'0th':{},'Exif':{},'GPS':{},'Interop':{},'1st':{}}
    secret_bytes = secret.encode('utf-8')
    if strategy == 'datetime':
        if len(secret_bytes) > 8:
            print(f'[WARN] DateTime策略最多8字节，截断')
            secret_bytes = secret_bytes[:8]
        ts = bytearray(b'2026:07:26 00:00:00')
        # 清零第11~18位置
        for i in range(11, 19): ts[i] = 0
        for i, b in enumerate(secret_bytes): ts[11+i] = b
        exif_dict['0th'][306] = bytes(ts)
        field_name = 'DateTime'
    elif strategy in ('comment','usercomment') or (strategy=='auto' and len(secret_bytes)<=500):
        exif_dict['Exif'][piexif.ExifIFD.UserComment] = secret_bytes
        field_name = 'UserComment'
    elif strategy in ('desc','imagedescription') or strategy=='auto':
        exif_dict['0th'][270] = secret_bytes
        field_name = 'ImageDescription'
    else:
        print(f'[FAIL] 未知策略: {strategy}'); return False
    try:
        exif_bytes = piexif.dump(exif_dict)
    except Exception as e:
        print(f'[FAIL] piexif.dump失败: {e}'); return False
    fmt = 'JPEG' if opath.lower().endswith(('.jpg','.jpeg')) else 'PNG'
    img.save(opath, fmt, exif=exif_bytes, quality=95)
    verify = decode(opath, silent=True)
    if verify == secret:
        print(f'[OK] "{secret}" → {opath} (策略={strategy}, 字段={field_name})')
        return True
    else:
        print(f'[WARN] 验证不一致: 提取=""{verify}""')
        return False

def decode(path, silent=False):
    if not _ensure_piexif(): return None
    img = Image.open(path)
    exif_raw = img.info.get('exif')
    if not exif_raw:
        if not silent: print('[FAIL] 无EXIF数据')
        return None
    exif_dict = piexif.load(exif_raw)
    exif_ifd = exif_dict.get('Exif',{})
    candidates = []
    uc = exif_ifd.get(piexif.ExifIFD.UserComment)
    if uc and isinstance(uc, bytes) and len(uc)>0: candidates.append(('UserComment', uc))
    desc = exif_dict.get('0th',{}).get(270)
    if desc and isinstance(desc, bytes) and len(desc)>0: candidates.append(('ImageDescription', desc))
    dt = exif_dict.get('0th',{}).get(306)
    if dt and isinstance(dt, bytes) and len(dt)>=19:
        raw = dt[11:19].rstrip(b'\x00')
        if len(raw)>0: candidates.append(('DateTime', raw))
    for field, data in candidates:
        try:
            txt = data.decode('utf-8')
            if txt:
                if not silent: print(f'[OK] "{txt}" (来自 {field})')
                return txt
        except: pass
    if not silent: print('[FAIL] 未发现有效水印')
    return None

def main():
    if len(sys.argv)<2:
        print('用法:')
        print('  python3 exif_watermark.py analyze <图片>')
        print('  python3 exif_watermark.py encode <输入> <输出> <水印内容> [策略]')
        print('  python3 exif_watermark.py decode <图片>')
        print('')
        print('策略: auto(默认) | comment | desc | datetime')
        print('')
        print('QQ/微信保留:')
        print('  "\u2705 DateTime(基础字段, ~8字节, datetime策略)')
        print('  "\u26a0\ufe0f ImageDescription(可能保留, desc策略)')
        print('  "\u274c UserComment/COM(会被剥离, 适合同设备)')
        print('')
        print('示例:')
        print('  同设备: exif_watermark.py encode in.jpg out.jpg "版权信息" comment')
        print('  QQ短:  exif_watermark.py encode in.jpg out.jpg "TC-STA" datetime')
        print('  分析:   exif_watermark.py analyze photo.jpg')
        return
    cmd = sys.argv[1]
    if cmd=='analyze' and len(sys.argv)>=3: analyze(sys.argv[2])
    elif cmd=='encode' and len(sys.argv)>=5:
        s = sys.argv[5] if len(sys.argv)>5 else 'auto'
        encode(sys.argv[2], sys.argv[3], sys.argv[4], s)
    elif cmd=='decode' and len(sys.argv)>=3: decode(sys.argv[2])
    else: print('参数错误')

if __name__=='__main__': main()
