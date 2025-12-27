#!/usr/bin/env python3
"""
InventoryFormatter - 在庫フォーマット処理

在庫関連のレスポンスフォーマット処理を担当
"""

from typing import Dict, Any, List
from .base import BaseFormatter
from ..utils import FOOD_CATEGORY_MAPPING, CATEGORY_EMOJI_MAP


class InventoryFormatter(BaseFormatter):
    """在庫フォーマット処理クラス"""
    
    def __init__(self):
        """初期化"""
        super().__init__("service", "llm.response.formatters.inventory")
    
    def format_inventory_list(self, data: Dict, is_menu_scenario: bool = False) -> List[str]:
        """在庫一覧のフォーマット（同一アイテム合算表示・カテゴリ別ソート対応）"""
        response_parts = []
        
        # 修正: success判定を追加
        if isinstance(data, dict) and data.get("success"):
            # 成功時: dataから在庫データを取得
            inventory_data = data.get("data", [])
            
            if not inventory_data:
                return []
            
            # 献立提案シナリオの場合は表示しない
            if is_menu_scenario:
                return []
            
            # 同一アイテムの合算処理
            grouped_items = self._group_items_by_name(inventory_data)
            
            # カテゴリ別に分類・ソート
            categorized_items = self._categorize_and_sort_items(grouped_items)
            
            # 通常の在庫表示（詳細）
            response_parts.append("📋 **現在の在庫一覧**")
            response_parts.append(f"総アイテム数: {len(grouped_items)}種類")
            response_parts.append("")
            
            # カテゴリ別に表示（肉→野菜→その他の順序）
            for category in ['肉', '野菜', 'その他']:
                if category in categorized_items and categorized_items[category]:
                    category_emoji = CATEGORY_EMOJI_MAP.get(category, "📦")
                    response_parts.append(f"{category_emoji} **{category}類**")
                    response_parts.append("")  # セクションタイトル後の空行
                    
                    for item_name, item_info in categorized_items[category]:
                        # アイテム情報の表示
                        display_text = self._format_item_display(item_name, item_info)
                        response_parts.append(f"  • {display_text}")
                    
                    response_parts.append("")  # セクション終了後の空行
            
            return response_parts
        else:
            # エラー時の表示
            error_msg = data.get("error", "不明なエラー") if isinstance(data, dict) else "不明なエラー"
            response_parts.append("❌ **在庫一覧の取得に失敗しました**")
            response_parts.append("")
            response_parts.append(f"エラー: {error_msg}")
            response_parts.append("")
            response_parts.append("もう一度お試しください。")
            
            return response_parts
    
    def _group_items_by_name(self, inventory_data: List[Dict]) -> Dict[str, Dict]:
        """同一アイテム名でグループ化して数量を合算"""
        grouped_items = {}
        
        for item in inventory_data:
            item_name = item.get('item_name', '')
            if not item_name:
                continue
                
            if item_name not in grouped_items:
                grouped_items[item_name] = {
                    'total_quantity': 0,
                    'unit': item.get('unit', '個'),
                    'locations': [],
                    'expiry_dates': [],
                    'items': []  # 元のアイテム情報を保持
                }
            
            # 数量合算
            grouped_items[item_name]['total_quantity'] += float(item.get('quantity', 0))
            
            # 保管場所情報を収集
            storage_location = item.get('storage_location', 'その他')
            if storage_location not in grouped_items[item_name]['locations']:
                grouped_items[item_name]['locations'].append(storage_location)
            
            # 期限情報を収集
            expiry_date = item.get('expiry_date')
            if expiry_date and expiry_date not in grouped_items[item_name]['expiry_dates']:
                grouped_items[item_name]['expiry_dates'].append(expiry_date)
            
            # 元のアイテム情報を保持
            grouped_items[item_name]['items'].append(item)
        
        return grouped_items
    
    def _categorize_and_sort_items(self, grouped_items: Dict[str, Dict]) -> Dict[str, List]:
        """アイテムをカテゴリ別に分類し、ソート"""
        categorized_items = {
            '肉': [],
            '野菜': [],
            'その他': []
        }
        
        for item_name, item_info in grouped_items.items():
            category = self._get_item_category(item_name)
            categorized_items[category].append((item_name, item_info))
        
        # 各カテゴリ内でアイテム名順にソート
        for category in categorized_items:
            categorized_items[category].sort(key=lambda x: x[0])
        
        return categorized_items
    
    def _get_item_category(self, item_name: str) -> str:
        """アイテム名からカテゴリを判定"""
        for category, keywords in FOOD_CATEGORY_MAPPING.items():
            if any(keyword in item_name for keyword in keywords):
                return category
        return 'その他'
    
    def _format_item_display(self, item_name: str, item_info: Dict) -> str:
        """アイテムの表示形式を生成"""
        total_quantity = item_info['total_quantity']
        unit = item_info['unit']
        locations = item_info['locations']
        expiry_dates = item_info['expiry_dates']
        
        # 数量の表示形式を調整（整数の場合は小数点を表示しない）
        if total_quantity == int(total_quantity):
            quantity_str = str(int(total_quantity))
        else:
            quantity_str = str(total_quantity)
        
        # 基本表示
        display_text = f"{item_name}: {quantity_str}{unit}"
        
        # 保管場所情報の追加
        if len(locations) > 1:
            location_text = ", ".join(locations)
            display_text += f" ({location_text})"
        elif len(locations) == 1:
            display_text += f" ({locations[0]})"
        
        # 期限情報の追加
        if expiry_dates:
            if len(expiry_dates) == 1:
                display_text += f" [期限: {expiry_dates[0]}]"
            else:
                # 複数の期限がある場合は最短期限を表示
                sorted_dates = sorted(expiry_dates)
                display_text += f" [期限: {sorted_dates[0]}他]"
        
        return display_text
    
    def format_inventory_add(self, data: Dict) -> List[str]:
        """在庫追加のフォーマット"""
        response_parts = []
        
        # デバッグログ: 受信データの構造を確認
        self.logger.info(f"🔍 [DEBUG] format_inventory_addがデータを受信: {data}")
        self.logger.info(f"🔍 [DEBUG] データ型: {type(data)}")
        self.logger.info(f"🔍 [DEBUG] データキー: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # 修正: success判定を追加
        if isinstance(data, dict) and data.get("success"):
            # 成功時の表示
            self.logger.info(f"🔍 [DEBUG] 成功分岐を実行")
            item_data = data.get("data", {})
            self.logger.info(f"🔍 [DEBUG] item_data: {item_data}")
            item_name = item_data.get("item_name", "アイテム")
            quantity = item_data.get("quantity", 0)
            unit = item_data.get("unit", "個")
            storage = item_data.get("storage_location", "冷蔵庫")
            
            response_parts.append("✅ **在庫を追加しました**")
            response_parts.append("")
            response_parts.append(f"📦 **{item_name}**: {quantity}{unit}")
            response_parts.append(f"📍 **保管場所**: {storage}")
            
            if item_data.get("expiry_date"):
                response_parts.append(f"📅 **賞味期限**: {item_data['expiry_date']}")
            
            response_parts.append("")
            response_parts.append("在庫に正常に追加されました。")
        else:
            # エラー時の表示
            self.logger.info(f"🔍 [DEBUG] エラー分岐を実行")
            error_msg = data.get("error", "不明なエラー") if isinstance(data, dict) else "不明なエラー"
            self.logger.info(f"🔍 [DEBUG] error_msg: {error_msg}")
            response_parts.append("❌ **在庫の追加に失敗しました**")
            response_parts.append("")
            response_parts.append(f"エラー: {error_msg}")
            response_parts.append("")
            response_parts.append("もう一度お試しください。")
        
        return response_parts
    
    def format_inventory_update(self, data: Dict) -> List[str]:
        """在庫更新のフォーマット"""
        # 成功判定
        if isinstance(data, dict) and data.get("success"):
            return self._format_success_response(data, "更新")
        else:
            # エラー時の表示
            error_msg = data.get("error", "不明なエラー") if isinstance(data, dict) else "不明なエラー"
            
            # AMBIGUITY_DETECTEDエラーの特別処理
            if error_msg == "AMBIGUITY_DETECTED":
                return self._format_ambiguity_error(data, "更新")
            else:
                return self._format_general_error(error_msg, "更新")
    
    def format_inventory_delete(self, data: Dict) -> List[str]:
        """在庫削除のフォーマット"""
        # 成功判定
        if isinstance(data, dict) and data.get("success"):
            return self._format_success_response(data, "削除")
        else:
            # エラー時の表示
            error_msg = data.get("error", "不明なエラー") if isinstance(data, dict) else "不明なエラー"
            
            # AMBIGUITY_DETECTEDエラーの特別処理
            if error_msg == "AMBIGUITY_DETECTED":
                return self._format_ambiguity_error(data, "削除")
            else:
                return self._format_general_error(error_msg, "削除")
    
    def _format_success_response(self, data: Dict, operation_type: str) -> List[str]:
        """成功時の共通フォーマット処理"""
        response_parts = []
        item_data = data.get("data", {})
        
        # 複数件の処理結果に対応
        if isinstance(item_data, list):
            # 複数件の場合
            response_parts.append(f"✅ **在庫を{operation_type}しました**")
            response_parts.append("")
            response_parts.append(f"📦 **{operation_type}件数**: {len(item_data)}件")
            response_parts.append("")
            
            # 各アイテムの情報を表示
            for i, item in enumerate(item_data, 1):
                if isinstance(item, dict):
                    item_name = item.get("item_name", "アイテム")
                    if operation_type == "削除":
                        response_parts.append(f"{i}. 🗑️ **{item_name}**")
                    else:
                        quantity = item.get("quantity", 0)
                        unit = item.get("unit", "個")
                        response_parts.append(f"{i}. **{item_name}**: {quantity}{unit}")
            
            response_parts.append("")
            response_parts.append(f"在庫から正常に{operation_type}されました。")
        else:
            # 単一件の場合
            item_name = item_data.get("item_name", "アイテム")
            
            response_parts.append(f"✅ **在庫を{operation_type}しました**")
            response_parts.append("")
            
            if operation_type == "削除":
                response_parts.append(f"🗑️ **{item_name}** を在庫から{operation_type}しました。")
            else:
                quantity = item_data.get("quantity", 0)
                unit = item_data.get("unit", "個")
                response_parts.append(f"📦 **{item_name}**: {quantity}{unit}")
            
            response_parts.append("")
            response_parts.append(f"在庫から正常に{operation_type}されました。")
        
        return response_parts
    
    def _format_ambiguity_error(self, data: Dict, operation_type: str) -> List[str]:
        """AMBIGUITY_DETECTEDエラーの共通処理"""
        response_parts = []
        message = data.get("message", f"在庫が複数あるため{operation_type}できません。")
        items = data.get("items", [])
        
        response_parts.append(f"⚠️ **在庫の{operation_type}について**")
        response_parts.append("")
        response_parts.append(message)
        response_parts.append("")
        
        if items:
            response_parts.append("**現在の在庫:**")
            for i, item in enumerate(items, 1):
                item_name = item.get("item_name", "アイテム")
                quantity = item.get("quantity", 0)
                unit = item.get("unit", "")
                storage_location = item.get("storage_location", "未設定")
                expiry_date = item.get("expiry_date", "未設定")
                created_at = item.get("created_at", "")
                
                # 日付のフォーマット
                if created_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_str = dt.strftime("%m/%d")
                    except:
                        created_str = created_at[:10] if len(created_at) >= 10 else created_at
                else:
                    created_str = "不明"
                
                response_parts.append(f"{i}. **{item_name}**")
                response_parts.append(f"   - 数量: {quantity}{unit}")
                response_parts.append(f"   - 保存場所: {storage_location}")
                response_parts.append(f"   - 期限: {expiry_date}")
                response_parts.append(f"   - 作成日: {created_str}")
                response_parts.append("")
        
        if operation_type == "更新":
            response_parts.append("**選択肢:**")
            response_parts.append("- 「最新の○○を変えて」")
            response_parts.append("- 「一番古い○○を変えて」")
            response_parts.append("- 「全部の○○を変えて」")
        else:
            response_parts.append(f"{operation_type}対象を特定するため、「最新の」「一番古い」「全部」などを指定してください。")
        
        return response_parts
    
    def _format_general_error(self, error_msg: str, operation_type: str) -> List[str]:
        """通常エラーの共通処理"""
        response_parts = []
        response_parts.append(f"❌ **在庫の{operation_type}に失敗しました**")
        response_parts.append("")
        response_parts.append(f"エラー: {error_msg}")
        response_parts.append("")
        response_parts.append("もう一度お試しください。")
        return response_parts

