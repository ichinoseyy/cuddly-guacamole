#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
轻量本地文件索引/检索（Windows + Linux）

用法:
  python ff.py scan <path1> [path2 ...] [--full]
  python ff.py search [关键词] [-c 分类] [-e 扩展名] [-l 数量]
  python ff.py stats
  python ff.py clean
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime


CATEGORY_MAP = {
    "文档": [".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".ppt", ".pptx"],
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "视频": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"],
    "音频": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "代码": [".py", ".js", ".html", ".css", ".cpp", ".c", ".java", ".go", ".rs", ".sh"],
    "可执行": [".exe", ".msi", ".deb", ".rpm", ".sh", ".bat", ".cmd"],
    "CAD图纸": [".dwg", ".dxf", ".stp", ".step", ".igs", ".iges"],
    "Unity工程": [".unity", ".prefab", ".asset", ".mat", ".controller", ".anim"],
}

EXCLUDE_DIRS = {
    "AppData",
    ".cache",
    "node_modules",
    "__pycache__",
    "System Volume Information",
    "$RECYCLE.BIN",
    "lost+found",
    ".git",
    ".svn",
    "tmp",
    "temp",
    "cache",
}

WIN_SYSTEM_DIRS = {"Windows", "Program Files", "Program Files (x86)", "ProgramData", "System32", "SysWOW64"}
LINUX_SYSTEM_PREFIXES = ("/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/sys", "/usr", "/var")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "file_index.db")
EXT_TO_CATEGORY = {ext.lower(): cat for cat, exts in CATEGORY_MAP.items() for ext in exts}


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ext TEXT,
                size INTEGER,
                mtime REAL,
                category TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_ext ON files(ext)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime)")


def classify(ext: str) -> str:
    return EXT_TO_CATEGORY.get(ext.lower(), "其他")


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} TB"


def should_skip_root(path: str) -> bool:
    abs_path = os.path.abspath(path)
    if sys.platform.startswith("win"):
        parts = {p.lower() for p in abs_path.split(os.sep) if p}
        return any(item.lower() in parts for item in WIN_SYSTEM_DIRS)
    return any(abs_path == p or abs_path.startswith(p + os.sep) for p in LINUX_SYSTEM_PREFIXES)


def iter_files(root_path: str):
    for current, dirs, files in os.walk(root_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
        if sys.platform.startswith("win"):
            dirs[:] = [d for d in dirs if d not in WIN_SYSTEM_DIRS]
        for name in files:
            yield os.path.join(current, name), name


def scan(paths: list[str], full_scan: bool = False) -> None:
    init_db()
    checked = 0
    updated = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("PRAGMA journal_mode=MEMORY")

        for root in paths:
            if not os.path.exists(root):
                print(f"路径不存在: {root}")
                continue
            if should_skip_root(root):
                print(f"跳过系统目录: {root}")
                continue

            root = os.path.abspath(root)
            print(f"扫描: {root}")
            for file_path, name in iter_files(root):
                checked += 1
                try:
                    st = os.stat(file_path)
                except OSError:
                    continue

                ext = os.path.splitext(name)[1].lower()
                if not full_scan:
                    old = conn.execute("SELECT size, mtime FROM files WHERE path=?", (file_path,)).fetchone()
                    if old and old[0] == st.st_size and old[1] == st.st_mtime:
                        continue

                conn.execute(
                    """
                    INSERT OR REPLACE INTO files (path, name, ext, size, mtime, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (file_path, name, ext, st.st_size, st.st_mtime, classify(ext)),
                )
                updated += 1

        conn.commit()
        conn.execute("PRAGMA synchronous=FULL")

    print(f"完成: 扫描 {checked} 个文件，更新 {updated} 条记录")


def search(keyword: str = "", category: str | None = None, ext: str | None = None, limit: int = 50) -> None:
    init_db()

    sql = "SELECT path, name, size, mtime, category FROM files WHERE 1=1"
    params: list[object] = []

    if keyword:
        sql += " AND (name LIKE ? OR path LIKE ?)"
        kw = f"%{keyword}%"
        params.extend([kw, kw])
    if category:
        sql += " AND category=?"
        params.append(category)
    if ext:
        normalized_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        sql += " AND ext=?"
        params.append(normalized_ext)

    sql += " ORDER BY mtime DESC LIMIT ?"
    params.append(max(1, limit))

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        print("没有找到匹配文件")
        return

    print(f"找到 {len(rows)} 个文件")
    print(f"{'文件名':<36} {'大小':<10} {'修改时间':<16} {'分类':<8}")
    print("-" * 90)
    for path, name, size, mtime, cat in rows:
        t = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        short_name = name if len(name) <= 34 else name[:31] + "..."
        print(f"{short_name:<36} {format_size(size):<10} {t:<16} {cat:<8}")
        print(path)


def stats() -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        total_size = conn.execute("SELECT COALESCE(SUM(size), 0) FROM files").fetchone()[0]
        categories = conn.execute(
            "SELECT category, COUNT(*) FROM files GROUP BY category ORDER BY COUNT(*) DESC"
        ).fetchall()

    print(f"索引文件总数: {total}")
    print(f"总大小: {format_size(total_size)}")
    if categories:
        print("分类统计:")
        for cat, count in categories:
            print(f"  {cat}: {count}")


def clean() -> None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        all_paths = [row[0] for row in conn.execute("SELECT path FROM files").fetchall()]
        missing = [p for p in all_paths if not os.path.exists(p)]
        if not missing:
            print("没有无效记录")
            return
        conn.executemany("DELETE FROM files WHERE path=?", [(p,) for p in missing])
        conn.commit()
    print(f"已清理 {len(missing)} 条无效记录")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="轻量本地文件检索工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="扫描目录并建立索引")
    p_scan.add_argument("paths", nargs="+", help="要扫描的目录路径")
    p_scan.add_argument("--full", action="store_true", help="全量扫描（忽略增量判断）")

    p_search = sub.add_parser("search", help="搜索文件")
    p_search.add_argument("keyword", nargs="?", default="", help="文件名/路径关键词")
    p_search.add_argument("-c", "--category", help="分类（如 文档/图片/视频）")
    p_search.add_argument("-e", "--ext", help="扩展名（如 pdf 或 .pdf）")
    p_search.add_argument("-l", "--limit", type=int, default=50, help="返回数量上限")

    sub.add_parser("stats", help="查看索引统计")
    sub.add_parser("clean", help="清理已不存在文件的索引记录")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.cmd == "scan":
        scan(args.paths, args.full)
    elif args.cmd == "search":
        search(args.keyword, args.category, args.ext, args.limit)
    elif args.cmd == "stats":
        stats()
    elif args.cmd == "clean":
        clean()


if __name__ == "__main__":
    main()
