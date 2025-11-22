#!/usr/bin/env python3
"""
Constants - アプリケーション定数定義

アプリケーション全体で使用する定数を定義
"""

import os

# デフォルトレシピ画像URL
DEFAULT_RECIPE_IMAGE_URL = os.getenv(
    "DEFAULT_RECIPE_IMAGE_URL",
    "http://localhost:8000/static/no-photo.png"
)

