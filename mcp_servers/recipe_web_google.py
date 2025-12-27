"""
Morizo AI v2 - Recipe Web Search Module (Google Search)

This module provides web search functionality for recipe retrieval using Google Search API.
"""

import os
import re
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from dotenv import load_dotenv
from config.loggers import GenericLogger
from mcp_servers.recipe_web_constants import RECIPE_SITES, MOCK_RECIPES
from mcp_servers.recipe_web_utils import identify_site, build_recipe_image_url

# 環境変数の読み込み
load_dotenv()

# ロガーの初期化
logger = GenericLogger("mcp", "recipe_web_google", initialize_logging=False)


class GoogleSearchClient:
    """Google Search APIを使用したレシピ検索クライアント"""
    
    # モック機能の切り替えフラグ（課金回避用）
    # 環境変数 USE_MOCK_SEARCH で制御（デフォルト: True）
    USE_MOCK_SEARCH = os.getenv('USE_MOCK_SEARCH', 'True').lower() in ('true', '1', 'yes')
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        
        if not self.api_key or not self.engine_id:
            raise ValueError("GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID are required")
        
        self.service = build("customsearch", "v1", developerKey=self.api_key)
    
    async def search_recipes(self, recipe_title: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        レシピ検索を実行（複数サイト対応）
        
        動作モード:
        - モックモードがTrueの場合: タイトルチェックをせず、ランダムにモックデータを返す（LLM/RAG問わず使用可能）
        - モックモードがFalseの場合: 実際のGoogle Search APIを使用し、タイトルに基づいた検索結果を返す
        """
        logger.debug(f"🔍 [WEB] Searching recipes")
        logger.debug(f"🔍 [WEB] Recipe title: {recipe_title}")
        
        # モック機能が有効な場合はモックデータを返す（タイトルチェックなし）
        if self.USE_MOCK_SEARCH:
            logger.debug(f"🎭 [WEB] Using mock data (Google Search API disabled, no title check)")
            # モックモード: タイトルチェックをせず、ランダムにモックレシピを返す
            # LLM分のレシピでもモックモードが使用可能
            filtered_recipes = self._filter_mock_recipes(recipe_title, num_results)
            logger.debug(f"✅ [WEB] Found mock recipes")
            logger.debug(f"📊 [WEB] Found {len(filtered_recipes)} mock recipes")
            return filtered_recipes
        
        # モックモードがFalseの場合: 実際のGoogle Search APIを使用（タイトルチェックあり）
        try:
            logger.debug(f"🔍 [WEB] Using Google Search API (title check enabled)")
            # 検索クエリを構築
            query = self._build_recipe_query(recipe_title)
            
            result = self.service.cse().list(
                q=query,
                cx=self.engine_id,
                num=num_results,
                lr='lang_ja'  # 日本語に限定
            ).execute()
            
            # 結果を解析・整形
            recipes = self._parse_search_results(result.get('items', []))
            
            logger.debug(f"✅ [WEB] Found recipes")
            logger.debug(f"📊 [WEB] Found {len(recipes)} recipes")
            return recipes
            
        except Exception as e:
            logger.error(f"❌ [WEB] 検索エラー: {e}")
            return []
    
    def _filter_mock_recipes(self, recipe_title: str, num_results: int) -> List[Dict[str, Any]]:
        """
        モックレシピをランダムに選択（タイトルチェックなし）
        
        注意: モックモードでは、recipe_titleパラメータは無視され、
        タイトルに関係なくランダムにモックレシピを返します。
        LLM分のレシピでもモックモードが使用可能です。
        """
        import random
        
        # モックレシピからランダムに選択（タイトルチェックなし）
        available_recipes = MOCK_RECIPES.copy()
        random.shuffle(available_recipes)
        
        # 要求された数だけ取得
        selected_recipes = available_recipes[:num_results]
        
        # CookpadのURLの場合、image_urlを追加
        for recipe in selected_recipes:
            if recipe.get('site') == 'cookpad.com':
                image_url = build_recipe_image_url(recipe.get('url', ''))
                recipe['image_url'] = image_url
                logger.debug(f"🖼️ [GOOGLE] Built Cookpad OGP image URL for mock recipe: {recipe['image_url']}")
        
        return selected_recipes
    
    def _build_recipe_query(self, recipe_title: str) -> str:
        """レシピ検索用のクエリを構築"""
        # 複数サイトを対象とした検索クエリ
        sites_query = " OR ".join([f"site:{site}" for site in RECIPE_SITES.keys()])
        return f"({sites_query}) {recipe_title} レシピ"

    def _extract_cookpad_recipe_id(self, url: str) -> Optional[str]:
        """CookpadのURLからレシピIDを抽出（後方互換性のため残す）"""
        from mcp_servers.recipe_web_utils import extract_cookpad_recipe_id
        return extract_cookpad_recipe_id(url)
    
    def _build_cookpad_ogp_image_url(self, url: str) -> Optional[str]:
        """CookpadのOGP画像URLを構築（後方互換性のため残す）"""
        from mcp_servers.recipe_web_utils import build_recipe_image_url
        image_url = build_recipe_image_url(url)
        # デフォルト画像の場合はNoneを返す（既存の動作を維持）
        from config.constants import DEFAULT_RECIPE_IMAGE_URL
        return image_url if image_url != DEFAULT_RECIPE_IMAGE_URL else None
    
    
    def _parse_search_results(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """検索結果を解析・整形"""
        recipes = []
        
        for item in items:
            # サイト名を特定
            site_name = identify_site(item.get('link', ''))
            
            recipe = {
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'description': item.get('snippet', ''),
                'site': site_name,
                'source': RECIPE_SITES.get(site_name, 'Unknown')
            }
            
            # CookpadのURLの場合は、OGP画像URLを追加
            if site_name == 'cookpad.com':
                image_url = build_recipe_image_url(recipe['url'])
                recipe['image_url'] = image_url
                logger.debug(f"🖼️ [GOOGLE] Built Cookpad OGP image URL: {recipe['image_url']}")
            
            recipes.append(recipe)
        
        return recipes

