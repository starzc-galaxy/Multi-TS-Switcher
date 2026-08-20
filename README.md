# Multi-TS Switcher

多路 UDP-TS 轮询切换转发软件（PyQt6）：多组并行，每组最多 9 路输入源按配置时间轮询切换，输出单路 UDP-TS；全程不转码，只做 TS 包级切换转发，切换时做 PCR/PTS 时间戳重基准与关键帧对齐，避免卡顿黑屏。

## 功能

- 最多 9 组，每组最多 9 个输入源 + 1 个隐藏垫片源（本地 TS 文件循环兜底）。
- 输入/输出均支持单播与组播（可绑定网卡）。
- 每组按配置间隔轮询，自动跳过异常源；全部异常自动切垫片。
- 关键帧对齐切换 + PCR/PTS/DTS 重基准 + discontinuity 标记 + CC 重置。
- 每路状态监测：无数据超时、CC 错误、PCR 抖动、实时码率、收包数。
- 响应式监控墙：按窗口宽度自动排布 1–4 列；F11 全屏只显示监控墙。
- 每组卡片含当前源小预览（引擎进程内解码，不影响转发链路）。
- 手动控制：暂停/恢复、上一步、下一步、强制指定源。
- JSON 配置热生效；按模块本地日志 + 异常退出崩溃记录。
- 离线授权：机器指纹 + Ed25519 签名，授权组数 1–9，无试用。

## 目录

```text
app/                 主程序（UI、引擎、IPC、授权、配置）
  engine/            引擎：TS 解析/PSI/RAP/时间戳重基准/接收/调度/转发/预览
  ui/                PyQt6 界面
  licensing/         授权校验（只含公钥）
  ipc/               进程间通信协议
tools/               make_license.py 授权签发、generate_filler.py 垫片生成
assets/              图标、垫片 TS
config/              app.json、groups.json、license.lic
tests/               pytest 测试
docs/superpowers/    设计文档与实施计划
```

## 运行（源码）

```powershell
python -m pip install -r requirements.txt
python tools/generate_filler.py        # 生成 assets/filler.ts
python app/main.py
```

首次运行会要求导入授权文件；本机授权可用签发工具生成（见下）。

## 打包 Windows exe

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

产物在 `dist\MultiTS_Switcher\`，双击 `MultiTS_Switcher.exe` 运行。配置、日志、授权都在程序目录下，可随包分发。

### 一键交付打包（推荐）

```powershell
powershell -ExecutionPolicy Bypass -File build_all.ps1
```

流水线（Python 编排，入口 `tools/build_pipeline.py`，参考自成熟项目的 Cython 一体化方案）：

1. 运行全部测试；
2. 生成《使用说明书.docx》和应用 .ico 图标；
3. **Cython 源码防护**：复制工程到 `build/protected`，逐模块编译为 .pyd，删除 .py 源码；
4. 用受保护源码分别打包三个程序：主程序、测试工具、授权工具（各自独立 exe）；
5. 收集交付目录（三个程序 + 说明书），用系统 7-Zip 压缩为
   `交付\MultiTS_Switcher_交付包_日期.7z`。

授权工具的私钥（`dev_private_key.pem`）随授权工具一起进包，接收方可直接用它签发授权文件。
**重要**：私钥等于签发权，请把整个授权工具视为机密交付物，只交给可信任的授权管理员，切勿随意转传。

## 授权签发（管理员用）

```powershell
# 第一次：生成密钥对并回填公钥（tools/dev_private_key.pem 务必保密，勿分发）
python tools/make_license.py --init-keys <机器码> 9 --out lic/device.lic

# 之后给任意机器签发
python tools/make_license.py <机器码> 5 --days 30 --out lic/device.lic   # 30 天有效
python tools/make_license.py <机器码> 9 --out lic/device.lic             # 永久
```

机器码在未授权对话框里显示。授权文件拷到目标机，启动软件时导入即可；也可放到 `config\license.lic`。
已授权机器如需升级/调整组数，可在客户端工具栏“授权”→“导入新授权…”重新导入，立即生效（超出新组数的引擎会自动停止）。

### 图形版授权生成器

```powershell
python tools/license_generator.py
```

界面操作：填客户机器码 → 选授权组数（1–9）→ 选有效期（永久/按天数）→ 生成 .lic 文件。首次使用自动生成密钥对并回填公钥。
也可单独打包成 exe：

```powershell
.venv\Scripts\pyinstaller --noconfirm --clean LicenseGenerator.spec
```

产物在 `dist\LicenseGenerator\`。打包版需要把私钥文件 `dev_private_key.pem` 放到 exe 同目录（此文件绝不可随软件分发）。

## 配置说明

- `config/groups.json`：每组配置 `name`/`note`（备注）、`interval_seconds`（轮询间隔）、`output`（输出地址/端口/组播）、`interface`（绑定网卡 IP，留空自动）、`filler_path`（垫片 TS 路径）、`sources`（输入源：地址/端口/组播/启用/备注）。
- `config/app.json`：全局默认网卡、无数据超时、输出缓冲、预览开关/帧率、日志保留天数。
- 界面右侧配置面板修改后点“保存配置”即写入 JSON 并热推给对应引擎进程，无需重启。

## 注意

- 接收组播请确保 Windows 防火墙允许 UDP 入站，且加入组播需本机有对应网卡；多网卡环境建议在配置里指定绑定网卡 IP。
- 垫片文件默认是内置黑场+静音样例（320x180 MPEG2），可替换成自己的 TS 文件。
- `tools/dev_private_key.pem` 是授权私钥，绝不能打进交付包；交付包只含 `app/licensing/keys.py` 里的公钥。
- 引擎为多进程架构：每组一个独立进程，界面卡顿不影响转发；异常退出原因会写入 `logs/error.log` 并在卡片上提示。

## 生产测试工具

```powershell
python tools/stream_tester.py
```

两个页签：

- **发送测试源**：生成并发送 1–9 路彩色测试 TS 流（默认 229.1.1.x:7000 组播，含移动竖条便于肉眼确认切换），可直接给主程序当输入源；测试源文件自动生成在 `test_sources/`。
- **接收验证**：监听一路 UDP-TS（默认 230.1.1.1:7000，可改为主程序实际输出地址），解码显示画面并统计收包/码率/CC 错误，用于验证主程序输出是否正常。

也可单独打包：

```powershell
.venv\Scripts\pyinstaller --noconfirm --clean TestTool.spec
```

产物在 `dist\TestTool\`，测试源文件首次运行时自动生成到 exe 同目录 `test_sources\`。
