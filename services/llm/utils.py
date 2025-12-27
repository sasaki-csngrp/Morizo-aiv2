#!/usr/bin/env python3
"""
ResponseProcessor Utils - ユーティリティ関数

レスポンス処理で使用する共通のユーティリティ関数を提供
"""

from typing import Dict, Any
from config.loggers import GenericLogger


class ResponseProcessorUtils:
    """レスポンス処理ユーティリティクラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = GenericLogger("service", "llm.response.utils")
    
    def is_menu_scenario(self, results: Dict[str, Any]) -> bool:
        """
        献立提案シナリオかどうかを判定
        
        注意: 副菜・汁物提案でも`search_recipes_from_web`が使用されるため、
        `generate_menu_plan`または`search_menu_from_rag`が含まれている場合のみ献立提案と判定する。
        """
        # 献立提案専用のサービスのみをチェック
        menu_services = [
            "recipe_service.generate_menu_plan",
            "recipe_service.search_menu_from_rag"
        ]
        
        for task_result in results.values():
            service = task_result.get("service", "")
            method = task_result.get("method", "")
            service_method = f"{service}.{method}"
            
            if service_method in menu_services:
                return True
        
        return False
    
    def extract_actual_menu_title(self, web_data: Dict, category: str, menu_type: str) -> str:
        """実際の献立提案からタイトルを抽出"""
        try:
            # カテゴリマッピング
            category_mapping = {
                'main': 'main_dish',
                'side': 'side_dish',
                'soup': 'soup'
            }
            
            # メニュータイプに応じてデータソースを決定
            if menu_type == 'llm':
                menu_source = 'llm_menu'
            elif menu_type == 'rag':
                menu_source = 'rag_menu'
            else:
                # mixedの場合、カテゴリに応じて決定
                # 汁物もLLM/RAGの両方から取得する必要がある
                if category in ['main', 'side', 'soup']:
                    menu_source = 'llm_menu'  # 最初の3つ（main, side, soup）はLLM
                else:
                    menu_source = 'rag_menu'  # 次の3つ（main, side, soup）はRAG
            
            # 実際のタイトルを抽出
            if menu_source in web_data:
                menu_data = web_data[menu_source]
                dish_key = category_mapping.get(category, category)
                
                if dish_key in menu_data:
                    dish_data = menu_data[dish_key]
                    if isinstance(dish_data, str):
                        return dish_data
                    elif isinstance(dish_data, dict) and 'title' in dish_data:
                        return dish_data['title']
            
            return ""
            
        except Exception as e:
            self.logger.error(f"❌ [ResponseProcessorUtils] 実際のメニュータイトルの抽出でエラー: {e}")
            return ""
    
    def extract_domain(self, url: str) -> str:
        """
        URLからドメイン名を抽出
        
        Args:
            url: URL文字列
        
        Returns:
            ドメイン名
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return "unknown"


# 共通の定数とマッピング
MENU_SERVICES = [
    "recipe_service.generate_menu_plan",
    "recipe_service.search_menu_from_rag", 
    "recipe_service.search_recipes_from_web"
]

# 用途別に2つのマッピングを定義
CATEGORY_TO_DISH_MAPPING = {  # カテゴリ → データキー（_extract_actual_menu_title用）
    'main': 'main_dish',
    'side': 'side_dish',
    'soup': 'soup'
}

DISH_TO_CATEGORY_MAPPING = {  # データキー → カテゴリ（_extract_recipes_by_type用）
    'main_dish': 'main',
    'side_dish': 'side',
    'soup': 'soup'
}

CATEGORY_LABELS = {
    'main': '主菜',
    'side': '副菜',
    'soup': '汁物'
}

EMOJI_MAP = {
    'main': '🍖',
    'side': '🥗',
    'soup': '🍵'
}

STORAGE_EMOJI_MAP = {
    "冷蔵庫": "🧊", 
    "冷凍": "❄️", 
    "常温": "🌡️"
}

# 食材カテゴリマッピング（肉→野菜→その他の順序でソート）
FOOD_CATEGORY_MAPPING = {
    '肉': [
        # 肉類キーワード（「肉」「牛」「豚」「鶏」を含むもの）
        '肉', '牛肉', '豚肉', '鶏肉', 'ハム', 'ソーセージ', 'ベーコン', 'ウィンナー', 'ハンバーグ',
        'ミンチ', 'ロース', 'ヒレ', 'モモ', '胸肉', 'もも肉', 'ささみ', '手羽先',
        '牛すね', '豚バラ', '鶏もも', '牛ロース', '豚ロース', '鶏胸', '牛もも', '豚もも',
        'チーズ', 'バター', 'ヨーグルト', '生クリーム', '卵', 'たまご'
    ],
    '野菜': [
        'ピーマン', '玉ねぎ', 'にんじん', '人参', 'じゃがいも', 'ジャガイモ', 'キャベツ', 'トマト', 'きゅうり',
        'なす', 'かぼちゃ', 'さつまいも', '大根', '白菜', 'レタス', 'ほうれん草',
        'ブロッコリー', 'カリフラワー', 'アスパラガス', 'もやし', '豆苗', '小松菜',
        '春菊', '水菜', 'みつば', 'しそ', '大葉', 'ねぎ', '長ねぎ', '玉ねぎ',
        'にんにく', 'しょうが', 'パセリ', 'セロリ', 'きのこ', 'しいたけ', 'えのき',
        'しめじ', 'まいたけ', 'エリンギ', 'マッシュルーム'
    ],
    'その他': [
        '牛乳', '米', 'パン', '調味料', 'スパイス'
    ]
}

# カテゴリ別絵文字マッピング
CATEGORY_EMOJI_MAP = {
    '肉': '🍖',
    '野菜': '🥗', 
    'その他': '📦'
}
