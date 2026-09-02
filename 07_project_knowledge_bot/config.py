"""项目配置：路径与可调参数。"""
from __future__ import annotations  # 启用 PEP 563 延迟注解
from pathlib import Path  # 导入 Path 处理路径

PROJECT_DIR = Path(__file__).resolve().parent  # 赋值给 PROJECT_DIR
DATA_DIR = PROJECT_DIR / "data"  # 赋值给 DATA_DIR
INDEX_DIR = PROJECT_DIR / "_faiss_index"  # 赋值给 INDEX_DIR

# 切分参数
CHUNK_SIZE = 400  # 赋值给 CHUNK_SIZE
CHUNK_OVERLAP = 50  # 赋值给 CHUNK_OVERLAP

# 检索参数
TOP_K = 4  # 赋值给 TOP_K
