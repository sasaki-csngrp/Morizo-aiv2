"""
Morizo AI v2 - Recipe Web Search Module (Perplexity)

This module provides web search functionality for recipe retrieval using Perplexity API.
"""

import os
import re
import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests
from dotenv import load_dotenv
from config.loggers import GenericLogger
from bs4 import BeautifulSoup
from mcp_servers.recipe_web_constants import RECIPE_SITES
from mcp_servers.recipe_web_utils import identify_site

# 環境変数の読み込み
load_dotenv()

# ロガーの初期化
logger = GenericLogger("mcp", "recipe_web_perplexity", initialize_logging=False)


class PerplexitySearchClient:
    """Perplexity APIを使用したレシピ検索クライアント"""
    
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required")
        
        self.api_url = "https://api.perplexity.ai/chat/completions"
    
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
        sites = "または".join(RECIPE_SITES.keys())
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
                for site in RECIPE_SITES.keys():
                    if site in url:
                        recipe_urls.append(url)
                        break
            
            # 重複を除去
            recipe_urls = list(dict.fromkeys(recipe_urls))
            
            # 要求された数だけ処理（画像URLも並列取得）
            recipe_data_list = []
            image_tasks = []
            
            for url in recipe_urls[:num_results]:
                site_name = identify_site(url)
                recipe_data_list.append({
                    'url': url,
                    'site_name': site_name
                })
                # 画像取得タスクを作成
                image_tasks.append(self._fetch_recipe_image(url))
            
            # 画像取得を並列実行
            image_urls = await asyncio.gather(*image_tasks)
            
            # レシピデータと画像URLを結合
            from config.constants import DEFAULT_RECIPE_IMAGE_URL
            for recipe_data, image_url in zip(recipe_data_list, image_urls):
                recipe = {
                    'title': recipe_title,
                    'url': recipe_data['url'],
                    'description': f'{recipe_title}のレシピ（Perplexity検索）',
                    'site': recipe_data['site_name'],
                    'source': RECIPE_SITES.get(recipe_data['site_name'], 'Unknown'),
                    'image_url': image_url if image_url else DEFAULT_RECIPE_IMAGE_URL
                }
                recipes.append(recipe)
            
        except Exception as e:
            logger.error(f"❌ [PERPLEXITY] Error parsing response: {e}")
        
        return recipes
    
    def _normalize_image_url(self, image_url: str, base_url: str) -> str:
        """画像URLを正規化（相対URLを絶対URLに変換）"""
        if image_url.startswith('//'):
            return 'https:' + image_url
        elif image_url.startswith('/'):
            return urljoin(base_url, image_url)
        return image_url
    
    def _fetch_ogp_image(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """OGP画像を取得"""
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            image_url = self._normalize_image_url(og_image['content'], url)
            logger.info(f"🖼️ [PERPLEXITY] Found OGP image for {url}: {image_url}")
            return image_url
        logger.debug(f"🔍 [PERPLEXITY] No OGP image found for {url}")
        return None
    
    def _fetch_twitter_image(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Twitter Card画像を取得"""
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            image_url = self._normalize_image_url(twitter_image['content'], url)
            logger.debug(f"🖼️ [PERPLEXITY] Found Twitter image for {url}: {image_url}")
            return image_url
        return None
    
    def _fetch_kurashiru_image(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """クラシル専用画像を取得"""
        logger.debug(f"🔍 [PERPLEXITY] Searching for Kurashiru image in {url}")
        all_imgs = soup.find_all('img')
        logger.debug(f"🔍 [PERPLEXITY] Found {len(all_imgs)} img tags in Kurashiru page")
        
        img_tag = soup.find('img', class_=lambda x: x and ('recipe-image' in str(x).lower() or 'main-image' in str(x).lower() or 'hero-image' in str(x).lower()))
        if not img_tag:
            img_tag = soup.find('img', attrs={'data-src': True})
        if not img_tag:
            video_tag = soup.find('video')
            if video_tag and video_tag.get('poster'):
                image_url = self._normalize_image_url(video_tag['poster'], url)
                logger.info(f"🖼️ [PERPLEXITY] Found Kurashiru video poster for {url}: {image_url}")
                return image_url
        if img_tag:
            image_url = img_tag.get('src') or img_tag.get('data-src')
            if image_url:
                image_url = self._normalize_image_url(image_url, url)
                logger.info(f"🖼️ [PERPLEXITY] Found Kurashiru image for {url}: {image_url}")
                return image_url
        logger.debug(f"⚠️ [PERPLEXITY] No Kurashiru-specific image found for {url}")
        return None
    
    def _fetch_delishkitchen_image(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """デリッシュキッチン専用画像を取得"""
        img_tag = soup.find('img', class_=lambda x: x and ('recipe-image' in str(x).lower() or 'main-image' in str(x).lower() or 'hero-image' in str(x).lower()))
        if not img_tag:
            img_tag = soup.find('img', attrs={'data-src': True})
        if img_tag:
            image_url = img_tag.get('src') or img_tag.get('data-src')
            if image_url:
                image_url = self._normalize_image_url(image_url, url)
                logger.debug(f"🖼️ [PERPLEXITY] Found DelishKitchen image for {url}: {image_url}")
                return image_url
        return None
    
    def _fetch_fallback_image(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """フォールバック画像を取得（アイコンやロゴを除外）"""
        img_tags = soup.find_all('img')
        skip_keywords = ['icon', 'logo', 'avatar', 'button', 'badge', 'spinner', 'loading']
        
        for img in img_tags:
            src = img.get('src') or img.get('data-src')
            if not src:
                continue
            
            # アイコンやロゴを除外
            if any(skip in src.lower() for skip in skip_keywords):
                continue
            
            # サイズが大きそうな画像を優先
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    w = int(str(width).replace('px', ''))
                    h = int(str(height).replace('px', ''))
                    if w < 100 or h < 100:
                        continue
                except ValueError:
                    pass
            
            image_url = self._normalize_image_url(src, url)
            logger.debug(f"🖼️ [PERPLEXITY] Found fallback image for {url}: {image_url}")
            return image_url
        
        return None
    
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
            image_url = self._fetch_ogp_image(soup, url)
            if image_url:
                return image_url
            
            # 2. Twitter Card画像
            image_url = self._fetch_twitter_image(soup, url)
            if image_url:
                return image_url
            
            # 3. クラシル専用画像
            if 'kurashiru.com' in url:
                image_url = self._fetch_kurashiru_image(soup, url)
                if image_url:
                    return image_url
            
            # 4. デリッシュキッチン専用画像
            if 'delishkitchen.tv' in url:
                image_url = self._fetch_delishkitchen_image(soup, url)
                if image_url:
                    return image_url
            
            # 5. フォールバック画像
            image_url = self._fetch_fallback_image(soup, url)
            if image_url:
                return image_url
            
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

