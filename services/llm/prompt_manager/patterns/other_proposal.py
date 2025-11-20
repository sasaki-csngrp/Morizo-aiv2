#!/usr/bin/env python3
"""
その他カテゴリ提案プロンプトビルダー
"""

from ..utils import build_base_prompt


def build_other_proposal_prompt(user_request: str, user_id: str, main_ingredient: str = None, category_detail_keyword: str = None) -> str:
    """その他カテゴリ提案用のプロンプトを構築"""
    base = build_base_prompt()
    
    main_ingredient_info = f"\n主要食材: {main_ingredient}" if main_ingredient else "\n主要食材: 指定なし（在庫から提案）"
    category_detail_info = f"\n詳細カテゴリ: {category_detail_keyword}" if category_detail_keyword else ""
    
    category_detail_param = f'\n   - `"category_detail_keyword": "{category_detail_keyword}"`' if category_detail_keyword else '\n   - `"category_detail_keyword": null`'
    
    return f"""
{base}

ユーザー要求: "{user_request}"
{main_ingredient_info}{category_detail_info}

**その他カテゴリ提案の4段階タスク構成**:

ユーザーの要求が「その他のレシピ」「麺もののレシピ」「パスタのレシピ」「丼のレシピ」等のその他カテゴリ提案に関する場合、以下の4段階のタスク構成を使用してください。

**例**:
- 「その他のレシピを5件提案して」→ 4段階タスク構成
- 「麺もののレシピを教えて」→ 4段階タスク構成（詳細カテゴリ: 麺もの）
- 「パスタのレシピを提案して」→ 4段階タスク構成（詳細カテゴリ: パスタ）
- 「丼のレシピを教えて」→ 4段階タスク構成（詳細カテゴリ: ご飯もの丼物）

a. **task1**: `inventory_service.get_inventory()` を呼び出し、現在の在庫をすべて取得する。

b. **task2**: `history_service.history_get_recent_titles(user_id, "other", 14)` を呼び出し、14日間のその他カテゴリ履歴を取得する。**重要**: user_idパラメータには実際のユーザーIDを設定してください。例: "{user_id}"

c. **task3**: `recipe_service.generate_proposals(category="other")` を呼び出す。その際、ステップ1で取得した在庫情報を `inventory_items` パラメータに、ステップ2で取得した履歴タイトルを `excluded_recipes` パラメータに設定する。
      
   **重要**: excluded_recipesパラメータは必ず `"excluded_recipes": "task2.result.data"` と指定してください。`"task2.result"`ではありません。
   {f'主要食材: `"main_ingredient": "{main_ingredient}"`' if main_ingredient else '主要食材: `"main_ingredient": null`'}{category_detail_param}
   
   **重要**: ユーザー要求に「麺もの」「パスタ」「丼」などの具体的なカテゴリが含まれている場合、`category_detail_keyword`パラメータを指定してください。これにより、より精度の高い検索結果が得られます。

d. **task4**: `recipe_service.search_recipes_from_web()` を呼び出す。その際、ステップ3で取得したレシピタイトルを `recipe_titles` パラメータに設定する。

**依存関係**: task1 → task2 → task3 → task4 (直列実行が必須)

**重要**: task3はtask2の結果（`excluded_recipes`）に依存するため、task2の完了後に実行してください。
task2のdependenciesは["task1"]、task3のdependenciesは["task1", "task2"]、task4のdependenciesは["task3"]を指定してください。
"""

