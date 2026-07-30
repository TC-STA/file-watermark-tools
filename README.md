# File Watermark Tools

> 一套开箱即用的 **图片数字水印工具集**，覆盖频域扩频水印、DCT分块水印、EXIF元数据水印、文件级水印四种方案。
> 支持在 **QQ/微信压缩传输** 后仍能提取水印，真正做到「发出去能读回来」。

---

## 📋 工具一览

| 工具 | 方案类型 | 隐形程度 | 抗QQ压缩 | 容量 |
|:-----|:---------|:--------:|:--------:|:----:|
| **`ss_watermark.py`** 🏆 | 扩频水印（全图DCT+PN序列） | ★★★★★ | ✅ | ~100汉字 |
| **`exif_watermark.py`** | EXIF元数据水印 | ★★★★★ | ⚠️ DateTime | 8~500字节 |
| **`dct_watermark.py`** | DCT系数对（随机散布） | ★★★☆☆ | ✅ | ~300汉字 |
| **`file_watermark.py`** | 文件级通用水印 | ★★★★★ | ❌ | 不限 |

---

## 🚀 快速开始

```bash
# 按需安装依赖
pip3 install --break-system-packages numpy      # DCT/扩频水印需要
pip3 install --break-system-packages pillow     # 图片处理
pip3 install --break-system-packages piexif     # EXIF水印需要
pip3 install --break-system-packages cryptography  # 文件水印加密需要
```

Android（Termux）：
```bash
apt install python3-numpy python3-pil
pip3 install --break-system-packages piexif cryptography
```

---

## 🏆 方案一：扩频水印（真正隐形·推荐）

**`ss_watermark.py`** — 将水印以伪随机(PN)序列叠加到全图DCT系数，**每个像素仅改±1**，无块边界，放大100%也看不出。

### 原理
```
秘密文本 → UTF-8 → 2字节长度头 + 数据 + 8字节EOF
→ 比特流 → 每bit对应一段DCT系数 → 生成PN序列(±1)
→ 系数叠加(strength×PN×bit_val) → IDCT → 保存PNG
```

### 使用
```bash
# 嵌入水印
python3 ss_watermark.py encode input.png output.png "版权信息2026"

# 提取水印（PNG/JPEG均可）
python3 ss_watermark.py decode watermarked.jpg

# 自定义参数
python3 ss_watermark.py encode input.png output.png "秘密消息" 12 20

# 运行演示
python3 ss_watermark.py demo
```

### 参数
| 参数 | 默认值 | 说明 |
|:-----|:------:|:-----|
| `strength` | 12 | 嵌入强度，越大抗压缩越强 |
| `coeffs_per_block` | 20 | 每块系数数，越多容量越大 |

### 测试结果
| 测试项 | 结果 |
|:-------|:----:|
| PNG（无损） | ✅ 完美提取 |
| JPEG q=95~50 | ✅ 完美提取 |
| **QQ模拟（q85+4:2:0）** | ✅ **完美提取** |

### 建议
- **1440×1440**：默认参数可嵌 **~100汉字**，完全隐形
- 适合：QQ/微信传图、社媒分享、版权保护
- ⚠️ 图片**不能缩放**，缩放后块对齐失效

---

## ⚠️ 方案二：EXIF元数据水印

**`exif_watermark.py`** — 在图片EXIF字段中嵌入信息，**不修改像素**，完全无损。

### 策略对比
| 策略 | 位置 | 容量 | 同设备 | QQ/微信 |
|:-----|:-----|:----:|:------:|:-------:|
| `comment` | UserComment | ~500字节 | ✅ | ❌ 被剥离 |
| `desc` | ImageDescription | ~500字节 | ✅ | ⚠️ 可能保留 |
| `datetime` | DateTime ✅保留 | **~8字节** | ✅ | ✅ |

### 使用
```bash
# 分析EXIF（标注QQ保留字段）
python3 exif_watermark.py analyze photo.jpg

# 同设备无损（大容量）
python3 exif_watermark.py encode in.jpg out.jpg "版权信息" comment

# QQ传输（短消息，限8字节）
python3 exif_watermark.py encode in.jpg out.jpg "TC-STA" datetime

# 提取
python3 exif_watermark.py decode image.jpg
```

### QQ保留分析
实测QQ压缩后保留的字段：
- ✅ **DateTime**（19字节，可用~8字节存水印）
- ✅ **ImageWidth / ImageLength / Orientation**
- ❌ **UserComment / MakerNote / COM注释**（被剥离）

---

## 🔧 方案三：DCT系数对水印

**`dct_watermark.py`** — 在每个8×8块的4对最低频AC系数中嵌入水印，随机散布全图。

### 使用
```bash
python3 dct_watermark.py encode input.png output.png "水印内容"
python3 dct_watermark.py decode image.jpg
python3 dct_watermark.py encode input.png output.png "版权" 80 32
python3 dct_watermark.py demo
```

### 迭代历程
| 版本 | 强度 | 系数 | 散布 | 视觉 | 抗QQ |
|:---|:---:|:----|:----|:---:|:---:|
| V1 | 600 | 16对 | 顺序（集中上半） | ❌ 块状明显 | ✅ |
| V2 | 180 | 4对最低频 | 顺序 | ⚠️ 仍可见 | ✅ |
| V3 🏆 | **80** | 4对最低频 | **随机全图** | ✅ **不可见** | ✅ |

---

## 📄 方案四：文件级通用水印

**`file_watermark.py`** — 在文件中嵌入/提取水印，支持**任意格式文件**，每个格式使用最合适的嵌入方式，不影响文件功能。

### 原理

水印数据包格式（通用尾部方案）：
```
[MAGIC(4B FWMT)][VERSION(1B)][FLAGS(1B)][PAYLOAD_LEN(4B)][SALT(16B)][NONCE(12B)][CIPHERTEXT][EOF_MARK(8B)]
```

各格式嵌入方式：

| 格式 | 嵌入位置 | 说明 |
|:-----|:---------|:-----|
| **PNG** | tEXt辅助块 | 标准PNG元数据块，不破坏图像数据 |
| **JPEG** | COM注释标记 | 在SOS标记前插入，解码器自动忽略 |
| **ZIP/APK/DOCX/XLSX** | EOCD注释区域 | ZIP格式标准注释字段 |
| **PDF** | %%EOF后追加 | PDF阅读器忽略尾部追加内容 |
| **EXE/DLL** | 文件尾部 + 校验和置零 | PE格式安全区 |
| **MP4/MOV** | free box容器 | MP4标准容器扩展 |
| **MKV/RAR/7z/其他** | 尾部魔数标记 | 通用方案，FWMT+长度+EOF |

### 使用
```bash
# 嵌入水印（自动检测格式）
python3 file_watermark.py embed photo.png "版权信息2026"
python3 file_watermark.py embed report.pdf "机密文档 v1.2"
python3 file_watermark.py embed app.apk "内部版本 2026-07"

# 嵌入 + 加密
python3 file_watermark.py embed secret.zip "最高机密" 我的密码

# 嵌入 + 不创建备份（默认会生成 .bak）
python3 file_watermark.py embed photo.jpg "水印" --nobackup

# 提取水印
python3 file_watermark.py extract photo.png
python3 file_watermark.py extract secret.zip 我的密码

# 查看支持的格式
python3 file_watermark.py types

# 一键演示（自动测试所有格式）
python3 file_watermark.py demo
```

### 批量处理
```bash
# 批量嵌入（通配符）
python3 file_watermark.py batch "*.jpg" "批量水印"
python3 file_watermark.py batch "*.pdf" "内部机密" --recursive

# 批量提取
python3 file_watermark.py bextract "*.png"
python3 file_watermark.py bextract "*.pdf" --recursive
```

### 功能特性
| 功能 | 说明 |
|:-----|:-----|
| **全格式支持** | PNG/JPEG/ZIP(APK/DOCX)/PDF/PE(EXE)/MP4/MKV/通用 |
| **AES-256-GCM加密** | PBKDF2密钥派生，认证加密防篡改 |
| **自动备份** | 嵌入前自动创建 `.bak` 备份 |
| **批量处理** | 支持通配符和递归目录 |
| **格式自识别** | 自动检测文件格式选择最佳嵌入方式 |
| **零影响** | 嵌入后文件功能完全正常 |

### 依赖
加密功能需要额外安装：
```bash
pip3 install --break-system-packages cryptography
```
纯文本嵌入不需要此依赖。

### 注意事项
- ⚠️ **不抗QQ/微信压缩**：社交软件传输会重编码文件，水印数据会被剥离
- ✅ 适合：文件存档、内部流转、同设备/局域网/云盘传输
- ✅ 加密模式下**忘记密码则无法恢复**

---

## 📊 方案选择指南

| 场景 | 推荐工具 | 理由 |
|:-----|:---------|:-----|
| **QQ/微信传图·完全隐形** 🥇 | `ss_watermark.py` | 扩频，无块效应，像素变化±1 |
| QQ传图·次选 | `dct_watermark.py` | DCT系数对，抗压缩稳健 |
| QQ传图·短标识 | `exif_watermark.py datetime` | 仅8字节，但不改像素 |
| 同设备·大容量无损 | `exif_watermark.py comment` | 500字节，完全不改图 |
| 任意文件·无压缩场景 | `file_watermark.py` | 全格式支持，加密可选 |

---

## 📦 仓库结构

```
file-watermark-tools/
├── ss_watermark.py       # 🏆 扩频水印（推荐）
├── exif_watermark.py     # EXIF元数据水印
├── dct_watermark.py      # DCT系数对（随机散布版）
├── dct_watermark_dc.py   # DC系数实验版
├── file_watermark.py     # 文件级通用水印
└── README.md
```

---

## License
MIT
