# File Watermark Tools

通用文件水印工具集 —— 在**任意格式文件**中嵌入/提取数字水印，人眼无感知，文件功能不受影响。

## 工具列表

| 脚本 | 版本 | 功能 |
|:---|:---:|:---|
| `dct_watermark.py` | V3 频域水印 | DCT变换域嵌入，**抗QQ/微信压缩传输** |
| `dct_watermark_dc.py` | DC实验版 | 相邻块DC系数差分嵌入（实验性） |
| `file_watermark.py` | V4 通用水印 | **全格式支持 + AES加密 + 批量处理** |

---

## V3 DCT频域水印（QQ/微信传输优化版）

在图像YCbCr色彩空间的Y通道进行8x8分块DCT变换，通过修改AC最低频系数对的差值来嵌入水印位。专门针对社交软件（QQ/微信）的图片压缩链路优化。

### 核心优势
- 抗QQ压缩 - QQ图片转发（q85+4:2:0抽选）完美提取
- 抗JPEG q=1 - 质量因子1的极限压缩也能提取
- 人眼不可见 - 频域修改，画质几乎无损
- PNG嵌入/JPEG提取 - 嵌入保存为PNG，QQ压缩成JPEG后仍可提取

### 技术原理
1. 图像转为YCbCr，取Y（亮度）通道
2. 将Y通道分为8x8的像素块
3. 对每个块做DCT变换，得到频域系数矩阵
4. 选择最低频的4对AC系数：(0,1)-(1,0), (0,2)-(2,0), (1,1)-(2,2), (0,3)-(3,0)
5. 每1bit嵌入到一对系数中（增强/削弱差值表示1/0）
6. 每个bit用16-32个块重复嵌入，解码时多数投票
7. IDCT重建图像，保存为PNG

### 参数
| 参数 | 默认值 | 说明 |
|:---|---:|:---|
| 系数对 | 4对最低频 | JPEG量化步长最小，抗压缩最强 |
| 嵌入强度 | 80 | 极低强度 + 随机散布，放大不可见 |
| 冗余投票 | 16-32倍 | 每bit用N个块投票 |
| 容量(1440x1440) | 约40-80汉字 | 取决于冗余倍数 |

### 依赖
```bash
apt install python3-numpy python3-pil
# 或 pip install numpy Pillow
```

### 使用
```bash
# 嵌入水印（大图推荐32倍冗余，小图用16倍）
python3 dct_watermark.py encode input.png output.png "你的水印" [强度] [冗余]

# 提取水印（自动识别PNG/JPEG）
python3 dct_watermark.py decode image.jpg

# 模拟QQ压缩测试（质量85+色度4:2:0）
python3 dct_watermark.py qq_sim_test image.png

# JPEG抗压缩测试
python3 dct_watermark.py jpeg_test image.png 质量值

# 一键演示
python3 dct_watermark.py demo
```

### 场景示例

#### QQ传图带水印
```bash
python3 dct_watermark.py encode myphoto.png wm_photo.png "版权保护" 600 32
python3 dct_watermark.py decode qq_received.jpg
```

#### 微信传图带水印
```bash
python3 dct_watermark.py encode myphoto.png wm_photo.png "水印测试" 600 16
python3 dct_watermark.py decode wechat_received.jpg
```

### 抗压缩测试结果
| 测试项 | 结果 |
|:---|---:|
| PNG无损 | 完美提取 |
| JPEG q=95-1 | 全部通过 |
| QQ模拟(q85+4:2:0) | 完美提取 |

### 容量参考
| 图片尺寸 | 冗余16倍 | 冗余32倍 |
|:---|---:|:---:|
| 512x512 | ~10汉字 | - |
| 1440x1440 | ~80汉字 | ~40汉字 |
| 1920x1080 | ~60汉字 | ~30汉字 |
| 3840x2160 4K | ~260汉字 | ~130汉字 |

---

## V4 通用文件水印

利用文件格式规范中的冗余区域嵌入水印，不影响文件功能。支持全格式+通用后备。

### 格式支持
| 格式 | 嵌入技术 | 扩展支持 |
|:---:|:---|:---|
| PNG | tEXt辅助块 | 无损元数据 |
| JPEG | COM注释标记 | 不影响解码 |
| ZIP | EOCD注释区域 | APK/DOCX/XLSX/PPTX |
| PDF | %%EOF后追加 | 阅读器忽略 |
| PE | 尾部安全区(清零校验和) | EXE/DLL/SYS |
| MP4 | free box容器 | MOV |
| 通用 | 尾部魔数标记FWMT+长度验证 | MKV/RAR/7z/所有文件 |

### 附加功能
- AES-256-GCM加密 - PBKDF2密钥派生，密码保护防篡改
- 批量处理 - 支持通配符和递归目录
- 自动备份 - 嵌入前自动创建.bak备份

### 使用
```bash
# 嵌入水印
python3 file_watermark.py embed file.png "水印文本"
python3 file_watermark.py embed file.pdf "机密水印" mypassword

# 提取水印
python3 file_watermark.py extract file.png
python3 file_watermark.py extract file.zip mypassword

# 批量处理
python3 file_watermark.py batch "*.jpg" "批量水印"
python3 file_watermark.py bextract "*.pdf"

# 查看格式
python3 file_watermark.py types
# 一键演示
python3 file_watermark.py demo
```

### 真实文件测试结果
| 文件类型 | 大小 | 嵌入 | 提取 | 功能 |
|:---:|:---:|:---:|:---:|:---:|
| PNG | 3.7KB | OK | OK | 正常打开 |
| JPEG | 48KB | OK | OK | 正常打开 |
| APK | 61MB | OK | OK | 安装正常 |
| PDF | 103KB | OK | OK | 阅读正常 |
| MP3 | 13MB | OK | OK | 播放正常 |

### 水印数据包格式
```
MAGIC(4B FWMT) + VER(1B) + FLAGS(1B) + PAYLOAD_LEN(4B) + [SALT(16B)] + [NONCE(12B)] + CIPHERTEXT + EOF_MARK(6B FWMEND)
```

---

## 项目结构
```
file-watermark-tools/
  README.md
  dct_watermark.py      V3 DCT频域水印（QQ优化版）
  dct_watermark_dc.py   DC系数差分实验版
  file_watermark.py     V4 通用文件水印
```

## 常见问题

**Q: QQ/微信传图后水印提取不到？**
A: 确保用本工具嵌入水印后，发送原图给好友，好友直接从聊天窗口保存图片。不要截图、不要用相册转发。

**Q: 水印影响画质吗？**
A: 每像素变化约+-1-3，人眼无法分辨。

**Q: 通用水印影响文件功能吗？**
A: 不影响。APK安装、PDF阅读、MP3播放均测试正常。

**Q: 最大能嵌入多少文字？**
A: 1440x1440图用32倍冗余约40汉字，16倍约80汉字。

---

## License
MIT
