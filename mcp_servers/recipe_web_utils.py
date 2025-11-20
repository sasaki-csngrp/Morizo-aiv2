"""
Morizo AI v2 - Recipe Web Search Utilities

共通ユーティリティ関数の定義
"""

from mcp_servers.recipe_web_constants import RECIPE_SITES


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

