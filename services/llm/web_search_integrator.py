#!/usr/bin/env python3
"""
WebSearchResultIntegrator - Web検索結果統合

Web検索結果と候補リストを統合する処理を担当
"""

from typing import Dict, Any, List, Optional
from config.loggers import GenericLogger


class WebSearchResultIntegrator:
    """Web検索結果統合ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.web_integrator")
    
    def integrate(self, candidates: List[Dict[str, Any]], task_id: str, task4_data: Optional[Dict[str, Any]] = None, utils = None) -> List[Dict[str, Any]]:
        """
        Web検索結果を主菜提案結果に統合
        
        Args:
            candidates: 主菜提案の候補リスト
            task_id: タスクID
            task4_data: task4の実行結果データ
            utils: ResponseProcessorUtilsインスタンス
        
        Returns:
            URL情報が統合された候補リスト
        """
        try:
            # task4の結果からWeb検索結果を取得
            web_search_results = []
            search_title_to_recipes = {}  # 検索タイトルと検索結果の対応関係を保持
            if task4_data and task4_data.get("success") and task4_data.get("data"):
                web_data = task4_data["data"]
                # Web検索結果からレシピリストを抽出
                # 単一カテゴリ提案の場合: {"main_dish": {"title": "検索タイトル", "recipes": [...]}}
                # 一括提案の場合: {"llm_menu": {...}, "rag_menu": {...}}
                # 主菜・副菜・汁物のいずれかが直接存在する場合（単一カテゴリ提案）
                for category in ["main_dish", "side_dish", "soup"]:
                    if category in web_data and isinstance(web_data[category], dict) and "recipes" in web_data[category]:
                        category_data = web_data[category]
                        recipes = category_data.get("recipes", [])
                        search_title = category_data.get("title", "")  # 検索タイトルを取得
                        web_search_results = recipes
                        # 検索タイトルと検索結果の対応関係を保持
                        if search_title:
                            search_title_to_recipes[search_title] = recipes
                        break
                # 一括提案の場合（後方互換性のため）
                if not web_search_results and "rag_menu" in web_data and "main_dish" in web_data["rag_menu"]:
                    recipes = web_data["rag_menu"]["main_dish"].get("recipes", [])
                    web_search_results = recipes
            
            if not web_search_results:
                self.logger.debug(f"🔍 [WebSearchResultIntegrator] No web search results found for task {task_id}")
                return candidates
            
            # 使用済みのWeb検索結果を記録（重複を避けるため）
            used_web_results = set()
            
            # タイトルマッチング用のヘルパー関数
            def normalize_title(title: str) -> str:
                """タイトルを正規化（比較用）"""
                if not title:
                    return ""
                # 空白を除去、小文字に変換
                return title.strip().lower()
            
            def find_matching_web_result(candidate_title: str) -> Optional[Dict[str, Any]]:
                """候補のタイトルに一致するWeb検索結果を探す"""
                normalized_candidate_title = normalize_title(candidate_title)
                
                # 0. 検索タイトルと候補タイトルをマッチング（LLM分のレシピで検索タイトルと候補タイトルが一致する場合）
                # 検索タイトルと候補タイトルが一致した場合、その検索結果の最初の1件を返す
                for search_title, recipes in search_title_to_recipes.items():
                    if normalize_title(search_title) == normalized_candidate_title:
                        # 検索タイトルと候補タイトルが一致した場合、その検索結果の最初の1件を返す
                        if recipes:
                            # 使用済みでない最初のレシピを探す
                            for idx, recipe in enumerate(web_search_results):
                                if idx in used_web_results:
                                    continue
                                # 検索結果のリスト内で、このレシピが含まれているか確認
                                if recipe in recipes:
                                    used_web_results.add(idx)
                                    self.logger.debug(f"🔗 [WebSearchResultIntegrator] Search title match: '{candidate_title}' <-> search title '{search_title}', using first result")
                                    return recipe
                            # 見つからない場合は、検索結果の最初の1件を使用
                            if recipes:
                                # web_search_resultsから該当するレシピを探す
                                for recipe in recipes:
                                    try:
                                        idx = web_search_results.index(recipe)
                                        if idx not in used_web_results:
                                            used_web_results.add(idx)
                                            self.logger.debug(f"🔗 [WebSearchResultIntegrator] Search title match: '{candidate_title}' <-> search title '{search_title}', using first result")
                                            return recipe
                                    except ValueError:
                                        continue
                
                # 1. 完全一致を探す（検索結果タイトルと候補タイトル）
                for idx, web_result in enumerate(web_search_results):
                    if idx in used_web_results:
                        continue
                    web_title = web_result.get("title", "")
                    if normalize_title(web_title) == normalized_candidate_title:
                        used_web_results.add(idx)
                        self.logger.debug(f"🔗 [WebSearchResultIntegrator] Exact title match: '{candidate_title}' <-> '{web_title}'")
                        return web_result
                
                # 2. 部分一致を探す（候補のタイトルがWeb検索結果のタイトルに含まれる、またはその逆）
                for idx, web_result in enumerate(web_search_results):
                    if idx in used_web_results:
                        continue
                    web_title = web_result.get("title", "")
                    normalized_web_title = normalize_title(web_title)
                    
                    # 候補のタイトルがWeb検索結果のタイトルに含まれる
                    if normalized_candidate_title in normalized_web_title:
                        used_web_results.add(idx)
                        self.logger.debug(f"🔗 [WebSearchResultIntegrator] Partial match (candidate in web): '{candidate_title}' in '{web_title}'")
                        return web_result
                    
                    # Web検索結果のタイトルが候補のタイトルに含まれる
                    if normalized_web_title in normalized_candidate_title:
                        used_web_results.add(idx)
                        self.logger.debug(f"🔗 [WebSearchResultIntegrator] Partial match (web in candidate): '{web_title}' in '{candidate_title}'")
                        return web_result
                
                return None
            
            # 候補とWeb検索結果を統合（タイトルベースのマッチング）
            integrated_candidates = []
            for i, candidate in enumerate(candidates):
                integrated_candidate = candidate.copy()
                
                # sourceフィールドが存在しない場合はデフォルト値"web"を設定
                if "source" not in integrated_candidate:
                    integrated_candidate["source"] = "web"
                
                # タイトルベースで対応するWeb検索結果を取得
                candidate_title = candidate.get("title", "")
                
                # 単一カテゴリ提案の場合、候補のインデックスと検索結果のインデックスが対応している
                # まず、インデックスベースでマッチングを試みる（LLM分のレシピで検索タイトルと候補タイトルが一致する場合）
                web_result = None
                if search_title_to_recipes and i < len(web_search_results):
                    # 検索タイトルと候補タイトルが一致するか確認
                    # 単一カテゴリ提案の場合、recipes配列の順序がrecipe_titlesの順序と対応している
                    # つまり、recipes[0]はrecipe_titles[0]の検索結果、recipes[1]はrecipe_titles[1]の検索結果
                    # したがって、候補のインデックスと検索結果のインデックスを対応させる
                    for search_title in search_title_to_recipes.keys():
                        if normalize_title(search_title) == normalize_title(candidate_title):
                            # 検索タイトルと候補タイトルが一致した場合、インデックスベースで対応する検索結果を使用
                            # ただし、検索結果のインデックスが候補のインデックスと対応していることを前提とする
                            if i < len(web_search_results) and i not in used_web_results:
                                web_result = web_search_results[i]
                                used_web_results.add(i)
                                self.logger.debug(f"🔗 [WebSearchResultIntegrator] Index-based match: candidate[{i}] '{candidate_title}' <-> search title '{search_title}'")
                                break
                    # 検索タイトルと候補タイトルが一致しない場合でも、インデックスベースでマッチングを試みる
                    # （単一カテゴリ提案の場合、候補の順序と検索結果の順序が対応している）
                    if not web_result and i < len(web_search_results) and i not in used_web_results:
                        # 候補のインデックスと検索結果のインデックスが対応している場合
                        web_result = web_search_results[i]
                        used_web_results.add(i)
                        self.logger.debug(f"🔗 [WebSearchResultIntegrator] Index-based match (fallback): candidate[{i}] '{candidate_title}'")
                
                # インデックスベースでマッチングできなかった場合、タイトルベースでマッチング
                if not web_result:
                    web_result = find_matching_web_result(candidate_title)
                
                if web_result and web_result.get("url"):
                    # URL情報を統合（sourceは既存の値を保持）
                    domain = utils.extract_domain(web_result.get("url", "")) if utils else ""
                    url_info = {
                        "title": web_result.get("title", ""),
                        "url": web_result.get("url", ""),
                        "domain": domain
                    }
                    # 画像URLが存在する場合は追加
                    if web_result.get("image_url"):
                        url_info["image_url"] = web_result.get("image_url")
                        self.logger.debug(f"🖼️ [WebSearchResultIntegrator] Found image URL for candidate '{candidate_title}': {web_result.get('image_url')}")
                    integrated_candidate["urls"] = [url_info]
                    # URLが存在する場合でも、元のsource（llm/rag）を保持
                    # Web検索はレシピ詳細取得のための補助情報であり、出典は変えない
                    self.logger.debug(f"🔗 [WebSearchResultIntegrator] Integrated URLs for candidate '{candidate_title}': {integrated_candidate.get('urls', [])}, source: {integrated_candidate.get('source', 'N/A')}")
                elif web_result:
                    self.logger.warning(f"⚠️ [WebSearchResultIntegrator] Web search result matched for '{candidate_title}' but has no URL")
                else:
                    self.logger.debug(f"🔍 [WebSearchResultIntegrator] No matching web search result found for candidate '{candidate_title}'")
                
                integrated_candidates.append(integrated_candidate)
            
            self.logger.debug(f"✅ [WebSearchResultIntegrator] Successfully integrated web search results for {len(integrated_candidates)} candidates")
            return integrated_candidates
            
        except Exception as e:
            self.logger.error(f"❌ [WebSearchResultIntegrator] Error integrating web search results: {e}")
            return candidates

