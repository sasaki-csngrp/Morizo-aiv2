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
            if task4_data and task4_data.get("success") and task4_data.get("data"):
                web_data = task4_data["data"]
                # Web検索結果からレシピリストを抽出
                # 単一カテゴリ提案の場合: {"main_dish": {...}}, {"side_dish": {...}}, {"soup": {...}}
                # 一括提案の場合: {"llm_menu": {...}, "rag_menu": {...}}
                # 主菜・副菜・汁物のいずれかが直接存在する場合（単一カテゴリ提案）
                for category in ["main_dish", "side_dish", "soup"]:
                    if category in web_data and isinstance(web_data[category], dict) and "recipes" in web_data[category]:
                        recipes = web_data[category].get("recipes", [])
                        web_search_results = recipes
                        break
                # 一括提案の場合（後方互換性のため）
                if not web_search_results and "rag_menu" in web_data and "main_dish" in web_data["rag_menu"]:
                    recipes = web_data["rag_menu"]["main_dish"].get("recipes", [])
                    web_search_results = recipes
            
            if not web_search_results:
                self.logger.debug(f"🔍 [WebSearchResultIntegrator] No web search results found for task {task_id}")
                return candidates
            
            # 候補とWeb検索結果を統合（sourceフィールドを保持）
            integrated_candidates = []
            for i, candidate in enumerate(candidates):
                integrated_candidate = candidate.copy()
                
                # sourceフィールドが存在しない場合はデフォルト値"web"を設定
                if "source" not in integrated_candidate:
                    integrated_candidate["source"] = "web"
                
                # 対応するWeb検索結果を取得
                if i < len(web_search_results):
                    web_result = web_search_results[i]
                    if web_result.get("url"):
                        # URL情報を統合（sourceは既存の値を保持）
                        domain = utils.extract_domain(web_result.get("url", "")) if utils else ""
                        integrated_candidate["urls"] = [{
                            "title": web_result.get("title", ""),
                            "url": web_result.get("url", ""),
                            "domain": domain
                        }]
                        # URLが存在する場合でも、元のsource（llm/rag）を保持
                        # Web検索はレシピ詳細取得のための補助情報であり、出典は変えない
                        self.logger.debug(f"🔗 [WebSearchResultIntegrator] Integrated URLs for candidate {i}: {integrated_candidate.get('urls', [])}, source: {integrated_candidate.get('source', 'N/A')}")
                    else:
                        self.logger.warning(f"⚠️ [WebSearchResultIntegrator] Web search result has no URL for candidate {i}")
                else:
                    self.logger.warning(f"⚠️ [WebSearchResultIntegrator] No web search result for candidate {i}")
                
                integrated_candidates.append(integrated_candidate)
            
            self.logger.debug(f"✅ [WebSearchResultIntegrator] Successfully integrated web search results for {len(integrated_candidates)} candidates")
            return integrated_candidates
            
        except Exception as e:
            self.logger.error(f"❌ [WebSearchResultIntegrator] Error integrating web search results: {e}")
            return candidates

