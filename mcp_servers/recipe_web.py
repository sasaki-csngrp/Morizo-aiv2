"""
Morizo AI v2 - Recipe Web Search Module

This module provides web search functionality for recipe retrieval using Google Search API and Perplexity API.
"""

import os
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests
from googleapiclient.discovery import build
from dotenv import load_dotenv
from config.loggers import GenericLogger
from bs4 import BeautifulSoup

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


class _PerplexitySearchClient:
    """Perplexity APIを使用したレシピ検索クライアント"""
    
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required")
        
        self.api_url = "https://api.perplexity.ai/chat/completions"
        
        # 対応サイトの定義
        self.recipe_sites = {
            'cookpad.com': 'Cookpad',
            'kurashiru.com': 'クラシル',
            'recipe.rakuten.co.jp': '楽天レシピ',
            'delishkitchen.tv': 'デリッシュキッチン'
        }
    
    async def search_recipes(self, recipe_title: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """レシピ検索を実行（Perplexity API使用）"""
        logger.debug(f"🔍 [PERPLEXITY] Searching recipes")
        logger.debug(f"🔍 [PERPLEXITY] Recipe title: {recipe_title}")
        
        try:
            # 検索クエリを構築
            query = self._build_recipe_query(recipe_title)
            
            # Perplexity APIを呼び出し
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": "あなたはレシピ検索アシスタントです。レシピのURLを提供してください。"
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.2
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            # エラーレスポンスの詳細を取得
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"❌ [PERPLEXITY] API Error {response.status_code}: {error_detail}")
                logger.error(f"❌ [PERPLEXITY] Request payload: {payload}")
                response.raise_for_status()
            
            result = response.json()
            
            # レスポンスからURLを抽出（非同期で画像も取得）
            recipes = await self._parse_perplexity_response(result, recipe_title, num_results)
            
            logger.debug(f"✅ [PERPLEXITY] Found recipes")
            logger.debug(f"📊 [PERPLEXITY] Found {len(recipes)} recipes")
            return recipes
            
        except Exception as e:
            logger.error(f"❌ [PERPLEXITY] Search error: {e}")
            return []
    
    def _build_recipe_query(self, recipe_title: str) -> str:
        """レシピ検索用のクエリを構築"""
        # 複数サイトを対象とした検索クエリ
        sites = "または".join(self.recipe_sites.keys())
        return f"{recipe_title} レシピ {sites} のURLを教えてください。URLのみを返してください。"
    
    async def _parse_perplexity_response(self, response: Dict, recipe_title: str, num_results: int) -> List[Dict[str, Any]]:
        """Perplexity APIのレスポンスを解析・整形（画像URLも取得）"""
        recipes = []
        
        try:
            # レスポンスからメッセージを取得
            choices = response.get('choices', [])
            if not choices:
                logger.warning(f"⚠️ [PERPLEXITY] No choices in response")
                return recipes
            
            content = choices[0].get('message', {}).get('content', '')
            
            # URLを抽出（正規表現でURLを検索）
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content)
            
            # レシピサイトのURLのみをフィルタリング
            recipe_urls = []
            for url in urls:
                for site in self.recipe_sites.keys():
                    if site in url:
                        recipe_urls.append(url)
                        break
            
            # 重複を除去
            recipe_urls = list(dict.fromkeys(recipe_urls))
            
            # 要求された数だけ処理（画像URLも並列取得）
            import asyncio
            recipe_data_list = []
            image_tasks = []
            
            for url in recipe_urls[:num_results]:
                site_name = self._identify_site(url)
                recipe_data_list.append({
                    'url': url,
                    'site_name': site_name
                })
                # 画像取得タスクを作成
                image_tasks.append(self._fetch_recipe_image(url))
            
            # 画像取得を並列実行
            image_urls = await asyncio.gather(*image_tasks)
            
            # レシピデータと画像URLを結合
            for recipe_data, image_url in zip(recipe_data_list, image_urls):
                recipe = {
                    'title': recipe_title,
                    'url': recipe_data['url'],
                    'description': f'{recipe_title}のレシピ（Perplexity検索）',
                    'site': recipe_data['site_name'],
                    'source': self.recipe_sites.get(recipe_data['site_name'], 'Unknown'),
                    'image_url': image_url  # 画像URLを追加
                }
                recipes.append(recipe)
            
        except Exception as e:
            logger.error(f"❌ [PERPLEXITY] Error parsing response: {e}")
        
        return recipes
    
    def _identify_site(self, url: str) -> str:
        """URLからサイト名を特定"""
        for site in self.recipe_sites.keys():
            if site in url:
                return site
        return 'other'
    
    async def _fetch_recipe_image(self, url: str) -> Optional[str]:
        """
        レシピページから画像URLを取得
        
        Args:
            url: レシピページのURL
        
        Returns:
            画像URL（取得失敗時はNone）
        """
        try:
            # HTMLを取得
            response = requests.get(
                url, 
                timeout=5, 
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )
            response.raise_for_status()
            
            # BeautifulSoupでパース
            soup = BeautifulSoup(response.text, 'lxml')
            
            # デバッグ: HTMLの一部をログ出力（最初の1000文字）
            logger.debug(f"🔍 [PERPLEXITY] HTML preview for {url}: {response.text[:1000]}")
            
            # 1. OGP画像を優先的に取得
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
                # 相対URLの場合は絶対URLに変換
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = urljoin(url, image_url)
                logger.info(f"🖼️ [PERPLEXITY] Found OGP image for {url}: {image_url}")
                return image_url
            else:
                logger.debug(f"🔍 [PERPLEXITY] No OGP image found for {url}")
            
            # 2. Twitter Card画像
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                image_url = twitter_image['content']
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    image_url = urljoin(url, image_url)
                logger.debug(f"🖼️ [PERPLEXITY] Found Twitter image for {url}: {image_url}")
                return image_url
            
            # 3. クラシル専用: 特定のクラス名の画像を取得
            if 'kurashiru.com' in url:
                logger.debug(f"🔍 [PERPLEXITY] Searching for Kurashiru image in {url}")
                # クラシルのレシピ画像は通常、特定のクラスやdata属性に含まれる
                # まず、すべてのimgタグを確認
                all_imgs = soup.find_all('img')
                logger.debug(f"🔍 [PERPLEXITY] Found {len(all_imgs)} img tags in Kurashiru page")
                
                # OGP画像が既に取得できている場合はスキップ（OGPが優先）
                # クラシルのレシピ画像は通常、特定のクラスやdata属性に含まれる
                img_tag = soup.find('img', class_=lambda x: x and ('recipe-image' in str(x).lower() or 'main-image' in str(x).lower() or 'hero-image' in str(x).lower()))
                if not img_tag:
                    # data-src属性も確認
                    img_tag = soup.find('img', attrs={'data-src': True})
                if not img_tag:
                    # videoタグのposter属性も確認（クラシルは動画サイト）
                    video_tag = soup.find('video')
                    if video_tag and video_tag.get('poster'):
                        image_url = video_tag['poster']
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = urljoin(url, image_url)
                        logger.info(f"🖼️ [PERPLEXITY] Found Kurashiru video poster for {url}: {image_url}")
                        return image_url
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = urljoin(url, image_url)
                        logger.info(f"🖼️ [PERPLEXITY] Found Kurashiru image for {url}: {image_url}")
                        return image_url
                logger.debug(f"⚠️ [PERPLEXITY] No Kurashiru-specific image found for {url}")
            
            # 4. デリッシュキッチン専用: 特定のクラス名の画像を取得
            if 'delishkitchen.tv' in url:
                # デリッシュキッチンのレシピ画像を取得
                img_tag = soup.find('img', class_=lambda x: x and ('recipe-image' in str(x).lower() or 'main-image' in str(x).lower() or 'hero-image' in str(x).lower()))
                if not img_tag:
                    # data-src属性も確認
                    img_tag = soup.find('img', attrs={'data-src': True})
                if img_tag:
                    image_url = img_tag.get('src') or img_tag.get('data-src')
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = urljoin(url, image_url)
                        logger.debug(f"🖼️ [PERPLEXITY] Found DelishKitchen image for {url}: {image_url}")
                        return image_url
            
            # 5. フォールバック: 最初の大きな画像を取得（アイコンやロゴを除外）
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src:
                    # アイコンやロゴを除外
                    skip_keywords = ['icon', 'logo', 'avatar', 'button', 'badge', 'spinner', 'loading']
                    if not any(skip in src.lower() for skip in skip_keywords):
                        # サイズが大きそうな画像を優先（width/height属性を確認）
                        width = img.get('width')
                        height = img.get('height')
                        if width and height:
                            try:
                                w = int(str(width).replace('px', ''))
                                h = int(str(height).replace('px', ''))
                                # 小さすぎる画像はスキップ
                                if w < 100 or h < 100:
                                    continue
                            except ValueError:
                                pass
                        
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = urljoin(url, src)
                        logger.debug(f"🖼️ [PERPLEXITY] Found fallback image for {url}: {src}")
                        return src
            
            logger.warning(f"⚠️ [PERPLEXITY] No image found for {url}")
            return None
            
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ [PERPLEXITY] Timeout while fetching image from {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ [PERPLEXITY] Request error while fetching image from {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"⚠️ [PERPLEXITY] Failed to fetch image from {url}: {e}")
            return None


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


# グローバルインスタンス（デフォルトはGoogle Search）
# 環境変数 USE_PERPLEXITY_SEARCH でPerplexityに切り替え可能
USE_PERPLEXITY_SEARCH = os.getenv('USE_PERPLEXITY_SEARCH', 'False').lower() in ('true', '1', 'yes')

# グローバルインスタンス（後方互換性のため）
try:
    if USE_PERPLEXITY_SEARCH:
        search_client = _PerplexitySearchClient()
        logger.info("🔍 [WEB] Using Perplexity Search (global)")
    else:
        search_client = _GoogleSearchClient()
        logger.info("🔍 [WEB] Using Google Search (global)")
except Exception as e:
    logger.warning(f"⚠️ [WEB] Failed to initialize search client: {e}, falling back to Google Search")
    search_client = _GoogleSearchClient()

# 検索クライアントのインスタンス（再利用のため）
_google_search_client = None
_perplexity_search_client = None


def get_search_client(menu_source: str = "mixed", use_perplexity: bool = None) -> Any:
    """
    検索クライアントを取得（menu_sourceに基づいて動的に選択）
    
    Args:
        menu_source: メニューのソース（"llm", "rag", "mixed"）
        use_perplexity: 強制的にPerplexityを使用するか（Noneの場合はmenu_sourceに基づいて決定）
    
    Returns:
        検索クライアントインスタンス
    """
    global _google_search_client, _perplexity_search_client
    
    # 環境変数で全体を切り替える場合
    if USE_PERPLEXITY_SEARCH:
        if _perplexity_search_client is None:
            try:
                _perplexity_search_client = _PerplexitySearchClient()
            except Exception as e:
                logger.warning(f"⚠️ [WEB] Failed to initialize Perplexity client: {e}, falling back to Google Search")
                if _google_search_client is None:
                    _google_search_client = _GoogleSearchClient()
                return _google_search_client
        return _perplexity_search_client
    
    # use_perplexityが明示的に指定されている場合
    if use_perplexity is True:
        if _perplexity_search_client is None:
            try:
                _perplexity_search_client = _PerplexitySearchClient()
            except Exception as e:
                logger.warning(f"⚠️ [WEB] Failed to initialize Perplexity client: {e}, falling back to Google Search")
                if _google_search_client is None:
                    _google_search_client = _GoogleSearchClient()
                return _google_search_client
        return _perplexity_search_client
    
    # menu_sourceが"llm"の場合はPerplexityを使用
    if menu_source == "llm":
        logger.debug(f"🔍 [WEB] menu_source='llm' detected, attempting to use Perplexity Search")
        if _perplexity_search_client is None:
            try:
                _perplexity_search_client = _PerplexitySearchClient()
                logger.info("✅ [WEB] Perplexity Search client initialized successfully for LLM proposals")
            except ValueError as e:
                logger.error(f"❌ [WEB] Perplexity API key not configured: {e}")
                logger.warning(f"⚠️ [WEB] Falling back to Google Search (may use mock data)")
                if _google_search_client is None:
                    _google_search_client = _GoogleSearchClient()
                return _google_search_client
            except Exception as e:
                logger.error(f"❌ [WEB] Failed to initialize Perplexity client: {e}")
                logger.warning(f"⚠️ [WEB] Falling back to Google Search (may use mock data)")
                if _google_search_client is None:
                    _google_search_client = _GoogleSearchClient()
                return _google_search_client
        logger.debug(f"🔍 [WEB] Returning Perplexity Search client for LLM proposals")
        return _perplexity_search_client
    
    # デフォルトはGoogle Search
    if _google_search_client is None:
        _google_search_client = _GoogleSearchClient()
    return _google_search_client
