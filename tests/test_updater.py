# -*- coding: utf-8 -*-
"""
tests/test_updater.py — 自动更新器完整性校验 (H-1) 回归测试
============================================================
覆盖范围:
  H-1  updater.py  下载的 EXE 必须经过哈希/大小校验后才能被替换执行，
                   防止被篡改/损坏的下载（含第三方代理镜像）导致任意代码执行。

测试纯函数 _sha256_file / _verify_file，无硬件依赖（不导入 vgamepad/mss）。
"""

import hashlib
import os

from engine.updater import _sha256_file, _verify_file, parse_version


def _write(tmp_path, data: bytes) -> str:
    """写入临时文件并返回路径。"""
    p = os.path.join(str(tmp_path), "blob.bin")
    with open(p, "wb") as f:
        f.write(data)
    return p


# ================================================================
# _sha256_file
# ================================================================


class TestSha256File:
    def test_matches_hashlib(self, tmp_path) -> None:
        """分块计算结果应与 hashlib 一次性计算一致。"""
        data = b"FH6" * 100_000  # ~300 KB，跨多个 64KB 分块
        path = _write(tmp_path, data)
        assert _sha256_file(path) == hashlib.sha256(data).hexdigest()

    def test_empty_file(self, tmp_path) -> None:
        """空文件应返回空内容的 SHA-256。"""
        path = _write(tmp_path, b"")
        assert _sha256_file(path) == hashlib.sha256(b"").hexdigest()


# ================================================================
# _verify_file
# ================================================================

# 一个 >1MB 的载荷，避免触发兜底的 "too small" 检查
_BIG = b"\x00" * 1_500_000
_BIG_SHA = hashlib.sha256(_BIG).hexdigest()
_BIG_SIZE = len(_BIG)


class TestVerifyFileHash:
    """有 sha256 时必须哈希精确匹配。"""

    def test_hash_match_passes(self, tmp_path) -> None:
        path = _write(tmp_path, _BIG)
        ok, _ = _verify_file(path, expected_size=_BIG_SIZE, expected_sha256=_BIG_SHA)
        assert ok is True

    def test_hash_mismatch_rejected(self, tmp_path) -> None:
        """哈希不符必须拒绝，即使大小恰好匹配（模拟被代理篡改但等长的内容）。"""
        tampered = b"\x01" * _BIG_SIZE  # 同样大小，不同内容
        path = _write(tmp_path, tampered)
        ok, reason = _verify_file(path, expected_size=_BIG_SIZE, expected_sha256=_BIG_SHA)
        assert ok is False
        assert "sha256" in reason.lower() or "mismatch" in reason.lower()

    def test_hash_case_insensitive(self, tmp_path) -> None:
        """期望哈希大小写不应影响比较结果。"""
        path = _write(tmp_path, _BIG)
        ok, _ = _verify_file(path, expected_size=_BIG_SIZE, expected_sha256=_BIG_SHA.upper())
        assert ok is True


class TestVerifyFileSizeFallback:
    """无 sha256 时退化为精确大小匹配。"""

    def test_size_match_passes(self, tmp_path) -> None:
        path = _write(tmp_path, _BIG)
        ok, _ = _verify_file(path, expected_size=_BIG_SIZE, expected_sha256=None)
        assert ok is True

    def test_size_mismatch_rejected(self, tmp_path) -> None:
        path = _write(tmp_path, _BIG)
        ok, reason = _verify_file(path, expected_size=_BIG_SIZE + 1, expected_sha256=None)
        assert ok is False
        assert "size" in reason.lower()


class TestVerifyFileNoMetadata:
    """size / hash 都未知时仅做 >1MB 健全性检查。"""

    def test_large_file_accepted(self, tmp_path) -> None:
        path = _write(tmp_path, _BIG)
        ok, _ = _verify_file(path, expected_size=0, expected_sha256=None)
        assert ok is True

    def test_small_file_rejected(self, tmp_path) -> None:
        path = _write(tmp_path, b"tiny")
        ok, reason = _verify_file(path, expected_size=0, expected_sha256=None)
        assert ok is False
        assert "small" in reason.lower()

    def test_missing_file_rejected(self, tmp_path) -> None:
        ok, reason = _verify_file(os.path.join(str(tmp_path), "nope.bin"), expected_size=0, expected_sha256=None)
        assert ok is False


# ================================================================
# parse_version 边界
# ================================================================


class TestParseVersion:
    def test_plain(self) -> None:
        assert parse_version("v1.5.10") == (1, 5, 10)

    def test_suffix_stripped(self) -> None:
        assert parse_version("1.5.4-beta") == (1, 5, 4)
        assert parse_version("1.6.0.RC1") == (1, 6, 0)

    def test_empty_is_lowest(self) -> None:
        """空版本串应解析为最小值，不会被误判为有新版本。"""
        assert parse_version("") <= parse_version("0.0.1")
