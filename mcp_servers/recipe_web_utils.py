"""
Morizo AI v2 - Recipe Web Search Utilities

共通ユーティリティ関数の定義
"""

import re
from typing import Optional
from mcp_servers.recipe_web_constants import RECIPE_SITES
from config.constants import DEFAULT_RECIPE_IMAGE_URL


def identify_site(url: str) -> str:
    """
    URLからサイト名を特定
    
    Args:
        url: レシピページのURL
    
    Returns:
        サイト名（見つからない場合は'other'）
    """
    for site in RECIPE_SITES.keys():
        if site in url:
            return site
    return 'other'


def extract_cookpad_recipe_id(url: str) -> Optional[str]:
    """
    CookpadのURLからレシピIDを抽出（共通ユーティリティ）
    
    Args:
        url: レシピのURL
        
    Returns:
        str: レシピID（見つからない場合はNone）
    """
    match = re.search(r'/recipes/(\d+)', url)
    return match.group(1) if match else None


def build_recipe_image_url(url: str) -> str:
    """
    レシピURLから画像URLを生成（共通ユーティリティ）
    
    Args:
        url: レシピのURL
        
    Returns:
        str: 画像URL（OGP画像URLまたはデフォルト画像URL）
    """
    if not url:
        return DEFAULT_RECIPE_IMAGE_URL
    
    # CookpadのURLの場合
    if "cookpad.com" in url:
        recipe_id = extract_cookpad_recipe_id(url)
        if recipe_id:
            return f"https://og-image.cookpad.com/global/jp/recipe/{recipe_id}"
    
    # その他のサイトの場合はデフォルト画像を使用
    return DEFAULT_RECIPE_IMAGE_URL

