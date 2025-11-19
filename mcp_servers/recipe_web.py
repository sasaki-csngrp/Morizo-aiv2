"""
Morizo AI v2 - Recipe Web Search Module

This module provides web search functionality for recipe retrieval using Google Search API.
"""

import os
import re
from typing import List, Dict, Any
from googleapiclient.discovery import build
from dotenv import load_dotenv
from config.loggers import GenericLogger

# 環境変数の読み込み
load_dotenv()

# ロガーの初期化
logger = GenericLogger("mcp", "recipe_web", initialize_logging=False)


class _GoogleSearchClient:
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
        
        # 対応サイトの定義
        self.recipe_sites = {
            'cookpad.com': 'Cookpad',
            'kurashiru.com': 'クラシル',
            'recipe.rakuten.co.jp': '楽天レシピ',
            'delishkitchen.tv': 'デリッシュキッチン'
        }
        
        # モック用レシピデータ（課金回避用）
        self.mock_recipes = [
            {
                'title': '簡単！基本のハンバーグ',
                'url': 'https://cookpad.com/jp/recipes/17546743',
                'description': 'ふわふわでジューシーなハンバーグの作り方。基本のレシピなので初心者でも安心して作れます。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '絶品！オムライス',
                'url': 'https://cookpad.com/jp/recipes/19174499',
                'description': 'ふわふわの卵で包んだオムライス。ケチャップライスと卵の相性が抜群です。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '本格！カレーライス',
                'url': 'https://cookpad.com/jp/recipes/19240768',
                'description': 'スパイスから作る本格カレー。時間をかけて作ることで深い味わいが楽しめます。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '簡単！チキンソテー',
                'url': 'https://cookpad.com/jp/recipes/17426721',
                'description': 'ジューシーで柔らかいチキンソテーの作り方。下味がポイントです。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '絶品！パスタ',
                'url': 'https://cookpad.com/jp/recipes/18584308',
                'description': '本格的なパスタの作り方。アルデンテの麺とソースのバランスが重要です。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '簡単！サラダ',
                'url': 'https://cookpad.com/jp/recipes/17616085',
                'description': '新鮮な野菜を使ったサラダ。ドレッシングの作り方も紹介しています。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '絶品！スープ',
                'url': 'https://cookpad.com/jp/recipes/17563615',
                'description': '体が温まる美味しいスープ。野菜のうま味がたっぷりです。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '簡単！炒飯',
                'url': 'https://cookpad.com/jp/recipes/17832934',
                'description': 'パラパラで美味しい炒飯の作り方。コツを掴めば簡単に作れます。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '絶品！天ぷら',
                'url': 'https://cookpad.com/jp/recipes/17564487',
                'description': 'サクサクで美味しい天ぷらの作り方。衣の作り方がポイントです。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            },
            {
                'title': '簡単！煮物',
                'url': 'https://cookpad.com/jp/recipes/18558350',
                'description': 'ほっこり美味しい煮物。野菜の甘みが引き出されます。',
                'site': 'cookpad.com',
                'source': 'Cookpad'
            }
        ]
    
    async def search_recipes(self, recipe_title: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """レシピ検索を実行（複数サイト対応）"""
        logger.debug(f"🔍 [WEB] Searching recipes")
        logger.debug(f"🔍 [WEB] Recipe title: {recipe_title}")
        
        # モック機能が有効な場合はモックデータを返す
        if self.USE_MOCK_SEARCH:
            logger.debug(f"🎭 [WEB] Using mock data (Google Search API disabled)")
            # 検索キーワードに基づいて関連するレシピをフィルタリング
            filtered_recipes = self._filter_mock_recipes(recipe_title, num_results)
            logger.debug(f"✅ [WEB] Found mock recipes")
            logger.debug(f"📊 [WEB] Found {len(filtered_recipes)} mock recipes")
            return filtered_recipes
        
        try:
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
            logger.error(f"❌ [WEB] Search error: {e}")
            return []
    
    def _filter_mock_recipes(self, recipe_title: str, num_results: int) -> List[Dict[str, Any]]:
        """モックレシピをランダムに選択"""
        import random
        
        # モックレシピからランダムに選択
        available_recipes = self.mock_recipes.copy()
        random.shuffle(available_recipes)
        
        # 要求された数だけ返す
        return available_recipes[:num_results]
    
    def _build_recipe_query(self, recipe_title: str) -> str:
        """レシピ検索用のクエリを構築"""
        # 複数サイトを対象とした検索クエリ
        sites_query = " OR ".join([f"site:{site}" for site in self.recipe_sites.keys()])
        return f"({sites_query}) {recipe_title} レシピ"
    
    def _parse_search_results(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """検索結果を解析・整形"""
        recipes = []
        
        for item in items:
            # サイト名を特定
            site_name = self._identify_site(item.get('link', ''))
            
            recipe = {
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'description': item.get('snippet', ''),
                'site': site_name,
                'source': self.recipe_sites.get(site_name, 'Unknown')
            }
            
            recipes.append(recipe)
        
        return recipes
    
    def _identify_site(self, url: str) -> str:
        """URLからサイト名を特定"""
        for site in self.recipe_sites.keys():
            if site in url:
                return site
        return 'other'


def prioritize_recipes(recipes: List[Dict]) -> List[Dict]:
    """レシピを優先順位でソート"""
    priority_order = ['cookpad.com', 'kurashiru.com', 'recipe.rakuten.co.jp', 'delishkitchen.tv']
    
    def get_priority(recipe):
        site = recipe.get('site', '')
        try:
            return priority_order.index(site)
        except ValueError:
            return len(priority_order)
    
    return sorted(recipes, key=get_priority)


def filter_recipe_results(recipes: List[Dict]) -> List[Dict]:
    """レシピ結果をフィルタリング"""
    filtered = []
    
    for recipe in recipes:
        # 基本的な検証
        if recipe.get('title') and recipe.get('url'):
            # レシピサイトかどうかを確認
            if recipe.get('site') in ['cookpad.com', 'kurashiru.com', 'recipe.rakuten.co.jp', 'delishkitchen.tv']:
                filtered.append(recipe)
    
    return filtered


# グローバルインスタンス
search_client = _GoogleSearchClient()
