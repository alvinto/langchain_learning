"""项目配置：路径与可调参数。"""
from __future__ import annotations
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
INDEX_DIR = PROJECT_DIR / "_faiss_index"

# 切分参数
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

# 检索参数
TOP_K = 4
