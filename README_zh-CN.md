# 🏎️ FH6 AutoBot — 一个永不落幕的全自动挂机工具

**🌐 语言: [English](README.md) | 中文**

[![CI](https://github.com/hypoxic127/FH6-AFK/actions/workflows/ci.yml/badge.svg)](https://github.com/hypoxic127/FH6-AFK/actions/workflows/ci.yml)
[![Release](https://github.com/hypoxic127/FH6-AFK/actions/workflows/release.yml/badge.svg)](https://github.com/hypoxic127/FH6-AFK/actions/workflows/release.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows-0078d4?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/license-Personal%20Use-f5c542)

> **Forza Horizon 6** 全自动技能点无限循环挂机系统。
> 基于 **计算机视觉 (OpenCV + Tesseract OCR)** 识别游戏画面状态，通过 **虚拟手柄 (ViGEmBus)** 模拟操作，实现 **零人工干预** 的闭环技能点刷取。
> 提供 **赛博朋克风格 Web UI** 仪表盘，支持远程监控与一键操控。

---

## 📋 目录

- [✨ 核心特性](#-核心特性)
- [🔄 工作流程](#-工作流程)
- [🛠️ 技术栈](#️-技术栈)
- [🚀 快速开始](#-快速开始)
- [📖 使用指南](#-使用指南)
- [📁 项目结构](#-项目结构)
- [🧪 测试与 CI](#-测试与-ci)
- [🔍 核心技术原理](#-核心技术原理)
- [🤝 贡献指南](#-贡献指南)
- [📝 许可证](#-许可证)

---

## ✨ 核心特性

| 特性 | 描述 |
|:-----|:-----|
| 🔁 **全自动四阶段循环** | 刷点 → 买车 → 加点 → 卖车，无限循环，睡觉挂机 |
| 👁️ **计算机视觉状态机** | 颜色直方图 + OCR 混合检测，精准识别 10+ 种游戏界面状态 |
| 🎮 **虚拟手柄控制** | ViGEmBus 模拟 Xbox 360 手柄，原生级输入兼容 |
| 🖥️ **Web UI 仪表盘** | 毛玻璃风格界面 + 实时日志 + 手机扫码远程监控 |
| ⏹️ **安全即时停止** | 协作式检查点让 Bot **立即且干净地**停止（释放手柄、重置截图）；仅当卡在原生调用时才用异步注入兜底 |
| 🔄 **自动更新** | GitHub Releases 自动检测更新，Web UI 一键更新或 `--update` 命令行更新 |
| 🛡️ **截图自愈** | BitBlt 失败自动恢复，MSS 实例重置 + 游戏窗口自动置前 |
| ✅ **启动预检** | 运行前校验 Tesseract 是否可用——缺失时明确提示并退出，而非无限重试死循环 |
| 🎰 **超级轮盘计数** | 自动统计已执行的加点宏次数 |
| 📦 **一键打包** | PyInstaller 单文件 `.exe`，无需 Python 环境 |
| 🧪 **170+ 个测试用例** | Ruff 代码检查 + Pytest 测试覆盖，GitHub Actions CI |

---

## 🔄 工作流程

```
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │  🏎️ 刷技能点 │────▶│  🛒 买车     │────▶│  ⚡ 加技能点 │────▶│  🗑️ 卖车    │
    │  Farm Points│     │  Buy Cars   │     │ Upgrade Cars│     │ Trash Cars  │
    └──────┬──────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
           │                                                           │
           │                    ♻️ 无限循环                             │
           └───────────────────────────────────────────────────────────┘
```

| 阶段 | 状态常量 | 说明 |
|:----:|:---------|:-----|
| 1️⃣ | `STATE_FARM_POINTS` | OCR 扫描技能点 → 自动进入 EventLab 刷满 999 |
| 2️⃣ | `STATE_BUY_CARS` | 五步视觉导航 → 批量购买 33 辆 Subaru Impreza 22B-STI |
| 3️⃣ | `STATE_UPGRADE_CARS` | 逐辆选择 NEW 标签车辆 → 消耗技能点升级技能树 |
| 4️⃣ | `STATE_TRASH_CARS` | 批量移除已升级 Impreza（保留 S2 主力车） |

---

## 🛠️ 技术栈

| 类别 | 技术 | 用途 |
|:-----|:-----|:-----|
| **视觉引擎** | OpenCV, Tesseract OCR | 图像处理、文字识别、颜色检测 |
| **数值计算** | NumPy | 直方图比对、图像矩阵运算 |
| **屏幕捕获** | MSS | 高性能跨平台截图 |
| **手柄模拟** | VGamepad + ViGEmBus | 虚拟 Xbox 360 手柄输入 |
| **Web 服务** | Flask + Flask-SocketIO | 实时 Web UI 控制面板 |
| **前端** | Vanilla JS + CSS3 | 毛玻璃仪表盘、WebSocket 实时日志 |
| **测试** | Pytest + Ruff | 单元测试 + 代码质量检查 |
| **打包** | PyInstaller | 一键构建单文件可执行程序 |
| **CI/CD** | GitHub Actions | 自动化测试 + Release 发布 |

---

## 🚀 快速开始

### 📋 前置要求

> ⚠️ 以下软件必须在运行前安装完成

| 软件 | 版本 | 下载 | 备注 |
|:-----|:-----|:-----|:-----|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) | 安装时勾选 "Add to PATH" |
| **Tesseract OCR** | 5.x | [下载链接](https://github.com/UB-Mannheim/tesseract/releases) | 默认路径安装即可（程序自动检测） |
| **ViGEmBus** | 最新版 | [下载链接](https://github.com/nefarius/ViGEmBus/releases) | 安装后需 **重启电脑** |

### 📥 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/hypoxic127/FH6-AFK.git
cd FH6-AFK

# 2. 一键安装（自动创建虚拟环境 + 安装依赖）
python setup.py

# 3. 启动程序（Web UI 模式）
python main_bot.py --web
```

### 🎮 游戏内准备

在启动 Bot 之前，请确保完成以下设置：

1. **游戏语言必须设置为英文** — OCR 识别依赖英文文本
2. **游戏窗口模式** — 窗口化 或 无边框窗口（推荐分辨率 2560×1440）。任意 **16:9** 分辨率均可（含默认的 1600×900）——技能点 OCR 取词区按 16:9 等比调校。若使用**非 16:9 显示器**或**非默认 HUD 缩放**导致技能点读错/读漏，点击 Web UI 的 **Calibrate** 按钮框选技能点数字、保存为你自己的 ROI 即可
3. **购买主力车** — `1998 Subaru Impreza 22B-STI Version`
4. **安装 S2 级改装** — 任意 S2 级调校（PI 徽章显示蓝色）
5. **收藏 EventLab 蓝图** — 支持任意蓝图。默认分享码 `890169683` 每局约获得 10 技能点
6. **配置单局点数** — 在 Web UI 中设置 **单局点数** 和 **目标点数** 以匹配你选择的蓝图。填写不准确会导致多跑或少跑
7. **开启自动转向** — 进入 `设置 → 难度设置 → 自动转向：开启`。Bot 在 EventLab 中依赖自动转向进行自动驾驶

> **⚠️ 重要：** 主力车的 **S2 蓝色 PI 徽章** 是程序区分 "保留车" 与 "可删除车" 的唯一判据。请务必确认主力车已安装 S2 调校。

---

## 📖 使用指南

### 🌐 Web UI 模式（推荐）

```bash
python main_bot.py --web              # 默认端口 6800
python main_bot.py --web --port 8080  # 自定义端口
```

启动后浏览器访问 `http://localhost:6800`，即可看到控制面板：

- 🎯 **实时状态监控** — 当前阶段、循环次数、运行时长、超级轮盘数
- 🔄 **流程进度条** — 可视化四阶段进度
- ⚙️ **选择起始阶段** — 下拉选择从任意阶段开始
- 📜 **实时日志终端** — 带语法高亮的日志流
- 📱 **扫码远程监控** — 手机扫描 QR 码即可远程查看
- 🆕 **自动更新** — 版本号徽章 + 检查更新按钮 + 一键下载更新（带进度条）

### 🔄 自动更新

Bot 启动时会在后台自动检查新版本并提示：

```bash
# 命令行手动更新
FH6AutoBot.exe --update

# 跳过更新检查（适用于开机自启等场景）
FH6AutoBot.exe --skip-update --web
```

在 Web UI 中：点击右上角 🔄 按钮，或在新版本横幅出现时点击 **⬇️ 立即更新** 按钮。

### 💻 终端模式

```bash
python main_bot.py
```

| 选项 | 功能 | 使用场景 |
|:----:|:-----|:---------|
| `[0]` | 🔄 自动循环（全流程） | 主菜单，完整四阶段无限循环 |
| `[1]` | 🏎️ 刷技能点 | 主菜单，进入 EventLab 跑图 |
| `[2]` | 🛒 买车 | 主菜单，批量购买 Impreza |
| `[3]` | ⚡ 加技能点 | 主菜单，消耗技能点升级 |
| `[4]` | 🗑️ 卖车 | 车库内，需选中斯巴鲁品牌 |
| `[5]` | ⏭️ 跳过买车循环 | 车库已有未加点的车时使用 |

### 📦 打包为 EXE

```bash
python packaging/build.py
```

生成 `dist/FH6AutoBot.exe`，无需 Python 即可运行（仍需 Tesseract 和 ViGEmBus）。

> **💡 提示：** 推送 Git 版本标签（如 `git tag v1.2.0 && git push --tags`）会自动触发 GitHub Actions 构建并发布到 Release 页面。

---

## 📁 项目结构

```
FH6_AutoBot/
│
├── main_bot.py                 # 🚀 主程序入口（终端 / Web UI）
│
├── engine/                     # 🧠 感知引擎层
│   ├── ocr.py                  #    计算机视觉（OCR + 颜色检测）
│   ├── state_detect.py         #    游戏状态检测器（直方图 + OCR 混合）
│   ├── event_bus.py            #    事件总线（日志/状态推送到 Web UI）
│   ├── runtime.py              #    PyInstaller 运行时路径解析
│   ├── version.py              #    应用版本号唯一来源
│   ├── updater.py              #    GitHub Releases 自动更新引擎
│   ├── i18n.py                 #    双语字符串表（中/英）
│   └── utils.py                #    日志 / 窗口操作 / 手柄 / MSS 截图
│
├── macro/                      # 🎮 宏操作层
│   ├── master_loop.py          #    主状态机（四阶段循环引擎）
│   ├── core.py                 #    基础设施：截图、日志、常量
│   ├── navigation.py           #    菜单导航 / 视觉制动 / 返回车库
│   ├── purchase.py             #    五步 Impreza 购买导航
│   ├── garage.py               #    车库网格：选择 / 删除 / 主力车导航
│   └── upgrade.py              #    升级宏（Cannot Afford 检测）
│
├── farm/                       # 🏁 EventLab 刷图层
│   └── skills.py               #    视觉状态机（自动驾驶 + 结算检测）
│
├── web/                        # 🌐 Web UI 控制面板
│   ├── server.py               #    Flask + SocketIO 服务端
│   ├── state_manager.py        #    全局状态管理器
│   └── static/                 #    前端资源
│       ├── index.html          #      仪表盘页面
│       ├── style.css           #      赛博朋克主题样式
│       └── app.js              #      WebSocket 客户端逻辑
│
├── packaging/                  # 📦 构建与打包
│   ├── build.py                #    一键 PyInstaller 构建脚本
│   ├── FH6AutoBot.spec         #    PyInstaller spec（--onefile）
│   └── hook_utf8.py            #    运行时钩子（Windows UTF-8 修复）
│
├── tests/                      # 🧪 单元测试（170+ 个用例）
├── tools/                      # 🔧 开发调试工具（不打包）
│
├── .github/workflows/
│   ├── ci.yml                  #    CI（Ruff 检查 + Pytest 测试）
│   └── release.yml             #    Release（PyInstaller → GitHub Release）
│
├── setup.py                    # ⚙️ 一键环境安装脚本
├── requirements.txt            # 📋 Python 依赖清单
├── ruff.toml                   # 🔍 Ruff 代码检查配置
└── pytest.ini                  # 🧪 Pytest 测试配置
```

---

## 🧪 测试与 CI

```bash
# 运行全部测试
python -m pytest

# 代码检查
python -m ruff check .

# 格式校验
python -m ruff format --check .
```

| CI 任务 | 触发条件 | 描述 |
|:--------|:---------|:-----|
| **Lint** | Push / PR | Ruff 代码检查 + 格式校验 |
| **Test** | Push / PR | 170+ 个测试用例（ubuntu-latest，已排除硬件测试） |
| **Release** | `v*` tag | PyInstaller 构建 → GitHub Release 发布（自动同步版本号） |

---

## 🔍 核心技术原理

### 👁️ 视觉状态检测

- **直方图 + OCR 混合** — `StateDetector` 先用颜色分布特征快速筛选候选状态，再用 OCR 精确验证
- **PI 徽章颜色检测** — HSV 色彩空间分析：蓝色 = S2 主力车（保留），橙色 = 可删除车

### 🔤 OCR 识别策略

- **12 路投票** — 3 种预处理（Otsu / 自适应 / 固定阈值）× 4 种 PSM 模式（6/7/8/13）= 12 次识别，对出现最多的最长位数结果投票
- **Otsu + 4 倍放大** — 二值化 + 白色留边 + 4 倍线性放大，最大化小字号数字的识别精度
- **零技能点保底检测** — 无限制 OCR 识别 "No Skill Points Available" 画面
- **启动预检** — 启动时校验 Tesseract 可用性，缺失即明确退出，绝不空转重试

### 🎯 车库网格导航

- **打字机遍历** — 逐列、从上到下扫描 3×N 网格
- **三重校验** — OCR 关键词（2/3 一致）+ NEW 黄色标签 + LEGENDARY 橙色稀有度
- **Cannot Afford 检测** — 弹窗自动关闭，停止购买流程

### 📦 构建与打包

- **PyInstaller --onefile** — 单文件 ~50MB 可执行程序
- **运行时路径层** — `engine/runtime.py` 统一路径解析（开发/打包双模式）
- **UTF-8 控制台修复** — `hook_utf8.py` 解决 Windows 中文日志乱码

### 🔄 自动更新系统

- **整数元组版本比较** — `(1,5,10) > (1,5,9)`，避免字符串比对漏洞
- **事务性文件替换** — 失败时自动回滚（永不损坏用户安装）
- **多镜像下载** — 直连 GitHub → ghproxy 代理链（3 个镜像）
- **防无限重启** — 重启前过滤 `--update` 参数
- **API 限流保护** — 1 小时检查缓存，不触发 GitHub 60 次/小时限制
- **全局更新锁** — 防止 Web UI + CLI 并发下载

### 🛡️ 截图自愈机制

- **BitBlt 失败恢复** — GDI 设备上下文损坏时自动重置 MSS 实例
- **窗口自动置前** — 截图失败后将游戏窗口拉回前台
- **优雅停止** — 停止时释放手柄并重置 MSS；收尾期间的截图失败被静默处理（不再刷 `ERROR` 假错误日志）

### ⏹️ 停止机制

- **协作式优先** — 共享停止标志在安全点被检查（每次按键前、可中断等待、状态机每个 tick），Bot 总在干净的边界停止——绝不会卡在按键中途、留下按住不放的按钮
- **注入式兜底** — 仅当 worker 阻塞在原生调用内（如 Tesseract 子进程）时才用异步异常注入；Web UI 立即响应，由后台任务完成宽限等待 + 兜底注入
- **基于 `BaseException` 的信号** — 停止异常继承自 `BaseException`，宽泛的 `except Exception` 不会误吞停止请求

---

## 🤝 贡献指南

欢迎任何形式的贡献！请遵循以下流程：

1. **Fork** 本仓库
2. 创建特性分支 (`git checkout -b feat/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feat/amazing-feature`)
5. 创建 **Pull Request**

### 开发规范

- 🐍 代码风格：PEP 8（Ruff 强制检查）
- 🏷️ 提交格式：[Conventional Commits](https://www.conventionalcommits.org/)（`feat` / `fix` / `docs` / `refactor` / `chore`）
- ✅ 所有 PR 必须通过 CI 检查（Lint + Test）

---

## 📝 许可证

本项目仅供 **学习与个人使用**。

---

**如果这个项目对你有帮助，请给一个 ⭐ Star 支持一下！**

Made with ❤️ by [hypoxic127](https://github.com/hypoxic127)
