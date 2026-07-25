# File Watermark Tools

通用文件水印工具集 —— 支持在 **任意格式文件** 中嵌入/提取数字水印，人眼无感知，文件功能不受影响。

---

## 工具列表

| 脚本 | 版本 | 功能 |
|:---|:---:|:---|
| `dct_watermark.py` | V3 频域水印 | DCT变换域嵌入，**抗JPEG压缩至q=1** |
| `dct_watermark_dc.py` | DC实验版 | 相邻块DC系数差分嵌入（实验性） |
| `file_watermark.py` | V4 通用水印 | **全格式支持 + AES加密 + 批量处理** |

---

## V3 — DCT频域水印

在图像 **YCbCr色彩空间** 的 Y 通道进行 8×8 分块 DCT 变换，通过修改 **AC低频系数对** 的差值来嵌入水印位。

### 核心优势

- ✅ **抗JPEG压缩** — 质量因子 q=1 极限压缩仍能完美提取
- ✅ **人眼不可见** — 频域修改，画质几乎无损
- ✅ **PNG/JPEG双格式** — 嵌入后保存为PNG，提取时支持JPEG

### 参数

| 参数 | 值 | 说明 |
|:---|:---:|:---|
| 系数对 | 16对 | 覆盖 (0,1)~(5,2) 低中频段 |
| 冗余 | 16倍 | 多数表决抗压缩误码 |
| 强度 | 200 | 嵌入强度，越大越抗压缩 |
| 容量 | ≈32字符 | 512×512图像 |

### 使用

```bash
# 嵌入水印
python dct_watermark.py encode input.png output.png "你的水印" [强度]

# 提取水印
python dct_watermark.py decode image.png

# JPEG抗压缩测试
python dct_watermark.py jpeg_test image.png 质量值

# 一键演示
python dct_watermark.py demo
```

### JPEG抗压测试结果

| 质量因子 | 结果 | 说明 |
|:---:|:---:|:---|
| PNG | ✅ 完美 | 无损格式 |
| q=95 ~ q=50 | ✅ | 常规JPEG压缩 |
| q=40 ~ q=10 | ✅ | 重度压缩 |
| q=5 | ✅ | 极限压缩 (57x) |
| **q=1** | ✅ **完美** | 极致压缩！ |

---

## V4 — 通用文件水印

利用 **文件格式规范中的冗余/保留区域** 嵌入水印，不影响文件功能。支持 **9种格式 + 通用后备**。

### 格式支持

| 格式 | 嵌入技术 | 扩展支持 |
|:---:|:---|:---|
| **PNG** | tEXt辅助块 | 无损元数据 |
| **JPEG** | COM注释标记 | 不影响解码 |
| **ZIP** | EOCD注释区域 | APK / DOCX / XLSX / PPTX |
| **PDF** | %%EOF后追加 | 阅读器忽略 |
| **PE** | 尾部安全区（自动清零校验和） | EXE / DLL / SYS |
| **MP4** | free box容器 | MOV |
| **通用** | 尾部魔数标记 | MKV / RAR / 7z / 所有文件 |

### 附加功能

- 🔐 **AES-256-GCM加密** — PBKDF2密钥派生，密码保护
- 📦 **批量处理** — 支持通配符 `*.jpg` 和递归目录
- 💾 **自动备份** — 嵌入前自动创建 `.bak` 备份

### 使用

```bash
# 单文件嵌入
python file_watermark.py embed 文件.png "水印文本"
python file_watermark.py embed 文件.zip "水印" --nobackup

# 加密水印
python file_watermark.py embed 文件.pdf "机密水印" 密码

# 提取水印
python file_watermark.py extract 文件.png
python file_watermark.py extract 文件.zip 密码

# 批量嵌入（通配符）
python file_watermark.py batch "*.jpg" "批量水印"
python file_watermark.py batch 目录名 "水印" --recursive

# 批量提取
python file_watermark.py bextract "*.pdf"

# 查看支持的格式
python file_watermark.py types

# 一键全格式演示
python file_watermark.py demo
```

### 真实文件测试结果

| 文件类型 | 文件大小 | 嵌入 | 提取 | 功能验证 |
|:---:|:---:|:---:|:---:|:---:|
| PNG图片 | 3.7KB | ✅ | ✅ | 正常打开 ✅ |
| JPEG照片 | 48KB | ✅ | ✅ | 正常打开 ✅ |
| APK安装包 | 61MB | ✅ | ✅ | ZIP解压正常 ✅ |
| PDF文档 | 103KB | ✅ | ✅ | 尾部完整 ✅ |
| MP3音乐 | 13MB | ✅ | ✅ | 文件头完整 ✅ |
| 批量3个文件 | — | ✅ 3/3 | ✅ | — |

---

## 依赖

```bash
pip install Pillow numpy cryptography
```

---

## 项目结构

```
file-watermark-tools/
├── README.md               ← 本文档
├── dct_watermark.py        ← V3 DCT频域水印（抗JPEG q=1）
├── dct_watermark_dc.py     ← DC系数差分实验版
└── file_watermark.py       ← V4 通用文件水印（全格式+批量）
```

---

## 技术原理

### DCT频域水印
1. 将图像Y通道分为 8×8 块
2. 对每块进行DCT变换，得到频域系数
3. 在**AC低频系数对**中嵌入比特（增强/削弱差值）
4. 16倍冗余 + 多数表决，抗JPEG量化损失
5. IDCT重建图像，保存为PNG

### 通用文件水印
- **格式感知**：通过文件魔数自动识别格式
- **精准嵌入**：每种格式使用专用的安全嵌入点
- **AES加密**：密码派生密钥，认证加密防篡改
- **完整性校验**：通用模式使用长度验证 + 结束标记

---

## License

MIT
