#!/usr/bin/env python3
"""
SessionInfoHandler - セッション情報処理

セッションから段階情報を取得する処理を担当
"""

from typing import Dict, Any, Optional
from config.loggers import GenericLogger


class SessionInfoHandler:
    """セッション情報処理ハンドラー"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.session_info")
    
    async def get_stage_info(self, sse_session_id: Optional[str] = None, session_service = None) -> Dict[str, Any]:
        """
        セッションから段階情報を取得
        
        Args:
            sse_session_id: SSEセッションID
            session_service: セッションサービスインスタンス
        
        Returns:
            段階情報辞書（current_stage, used_ingredients, menu_category）
        """
        stage_info = {}
        if sse_session_id and session_service:
            session = await session_service.get_session(sse_session_id, user_id=None)
            if session:
                current_stage = session.get_current_stage()
                self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: current_stage={current_stage}")
                stage_info["current_stage"] = current_stage
                
                # 使い残し食材を計算（在庫食材 - 使用済み食材）
                used_ingredients = session.get_used_ingredients()
                inventory_items = session.context.get("inventory_items", [])
                
                # 使い残し食材 = 在庫食材から使用済み食材を除外
                # 表記ゆれ（「レンコン」と「れんこん」など）に対応するため、正規化して比較
                # Sessionクラスの正規化メソッドを使用
                used_ingredients_normalized = {
                    session._normalize_ingredient_name(item) for item in used_ingredients
                }
                
                remaining_ingredients = []
                remaining_normalized = set()  # 重複除去用
                
                for item in inventory_items:
                    item_normalized = session._normalize_ingredient_name(item)
                    if item_normalized not in used_ingredients_normalized:
                        # 重複除去：正規化後の名前で既に追加済みかチェック
                        if item_normalized not in remaining_normalized:
                            remaining_ingredients.append(item)  # 元の在庫名を保持
                            remaining_normalized.add(item_normalized)
                
                self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: used_ingredients={used_ingredients}")
                self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: inventory_items={inventory_items}")
                self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: remaining_ingredients={remaining_ingredients}")
                
                if remaining_ingredients:
                    stage_info["used_ingredients"] = remaining_ingredients  # 使い残し食材を返す（フィールド名は変更しない）
                
                # メニューカテゴリを取得
                menu_category = session.get_menu_category()
                self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: menu_category={menu_category}")
                if menu_category:
                    stage_info["menu_category"] = menu_category
            
            self.logger.debug(f"🔍 [SessionInfoHandler] Phase 3D: stage_info={stage_info}")
        
        return stage_info

