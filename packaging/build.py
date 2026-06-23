# -*- coding: utf-8 -*-
"""
build.py — FH6 AutoBot 一键打包脚本
=====================================
将项目打包为独立可执行文件（无需安装 Python）。

用法:
    python packaging/build.py

输出: dist/FH6AutoBot.exe 单文件可执行程序。

前置条件:
    - Python 3.10+
    - pip install pyinstaller
    - 已安装 requirements.txt 中的所有依赖

注意:
    - Tesseract OCR 不会打包进 exe，用户需自行安装或将 tesseract/ 放在 exe 同目录
    - ViGEmBus 驱动需用户提前安装（系统级驱动无法打包）
"""

import os
import shutil
import subprocess
import sys
import urllib.request


def download_vigembus(tools_dir: str) -> None:
    driver_dir = os.path.join(tools_dir, "drivers")
    os.makedirs(driver_dir, exist_ok=True)
    installer_path = os.path.join(driver_dir, "ViGEmBus_Setup.exe")
    if not os.path.exists(installer_path):
        print("  📥 正在下载 ViGEmBus 安装包...")
        url = "https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe"
        try:
            urllib.request.urlretrieve(url, installer_path)
            print("  ✅ ViGEmBus 安装包下载完成")
        except Exception as e:
            print(f"  ❌ ViGEmBus 下载失败: {e}")
            print("  ⚠️ 请手动下载并放在 tools/drivers/ViGEmBus_Setup.exe 后重新打包")
            sys.exit(1)
    else:
        print("  ✅ ViGEmBus 安装包已存在")


def prepare_tesseract(tools_dir: str) -> None:
    tess_dir = os.path.join(tools_dir, "tesseract")
    if os.path.exists(os.path.join(tess_dir, "tesseract.exe")):
        print("  ✅ Tesseract OCR 引擎已存在")
        return

    print("  🔍 正在寻找系统中已安装的 Tesseract OCR...")
    sys_tess = r"C:\Program Files\Tesseract-OCR"
    if os.path.exists(os.path.join(sys_tess, "tesseract.exe")):
        print("  📥 正在复制系统 Tesseract 到打包目录...")
        shutil.copytree(sys_tess, tess_dir, dirs_exist_ok=True)
        print("  ✅ Tesseract OCR 复制完成")
    else:
        print("  ❌ 未找到 Tesseract OCR！")
        print("  ⚠️ 无法自动下载免安装版，请先手动将 Tesseract 文件夹放入 tools/tesseract/")
        print("  建议路径: tools/tesseract/tesseract.exe")
        sys.exit(1)


def main() -> int:
    """执行 PyInstaller 打包流程。"""
    # Force UTF-8 stdout/stderr to prevent cp1252 crash on emoji/Chinese
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    packaging_dir: str = os.path.dirname(os.path.abspath(__file__))
    project_root: str = os.path.dirname(packaging_dir)
    spec_file: str = os.path.join(packaging_dir, "FH6AutoBot.spec")
    dist_dir: str = os.path.join(project_root, "dist")
    build_dir: str = os.path.join(project_root, "build")

    print("=" * 50)
    print("  FH6 AutoBot — 打包构建")
    print("=" * 50)
    print()

    # 准备内置依赖 (Tesseract & ViGEmBus)
    tools_dir = os.path.join(project_root, "tools")
    prepare_tesseract(tools_dir)
    download_vigembus(tools_dir)
    print()

    # 检查 PyInstaller
    try:
        import PyInstaller  # noqa: F401

        print(f"  ✅ PyInstaller {PyInstaller.__version__} 已就绪")
    except ImportError:
        print("  ❌ PyInstaller 未安装，正在自动安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 清理旧构建
    for d in [build_dir, dist_dir]:
        if os.path.exists(d):
            print(f"  🧹 清理旧目录: {d}")
            shutil.rmtree(d)

    # 执行打包
    print()
    print("  🔨 正在打包...")
    print()

    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_file, "--noconfirm"],
        cwd=project_root,
    )

    if result.returncode != 0:
        print()
        print("  ❌ 打包失败！请检查上方错误输出。")
        return 1

    # 验证输出
    exe_path: str = os.path.join(dist_dir, "FH6AutoBot.exe")
    if os.path.exists(exe_path):
        size_mb: float = os.path.getsize(exe_path) / (1024 * 1024)
        print()
        print("=" * 50)
        print("  ✅ 打包成功！")
        print(f"  📦 输出路径: {exe_path}")
        print(f"  📏 文件大小: {size_mb:.1f} MB")
        print()
        print("  使用方法:")
        print("    1. 双击 FH6AutoBot.exe 即可运行")
        print("    2. 若未安装手柄驱动，将自动弹窗安装")
        print("=" * 50)
    else:
        print(f"  ⚠️ 未找到输出文件: {exe_path}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
