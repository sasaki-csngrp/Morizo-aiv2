#!/usr/bin/env python3
"""
追加提案プロンプトビルダー（主菜・副菜・汁物共通）
"""

from ..utils import build_base_prompt


def build_additional_proposal_prompt(user_request: str, user_id: str, sse_session_id: str, category: str) -> str:
    """追加提案用のプロンプトを構築（主菜・副菜・汁物・その他共通）"""
    base = build_base_prompt()
    
    category_name = {"main": "主菜", "sub": "副菜", "soup": "汁物", "other": "その他"}.get(category, "レシピ")
    
    return f"""
{base}

ユーザー要求: "{user_request}"

現在のSSEセッションID: {sse_session_id}

**{category_name}追加提案の4段階タスク構成**:

ユーザーの要求に「もう5件」「もっと」「他の提案」等の追加提案キーワードが含まれる場合、以下の4段階のタスク構成を使用してください。

**認識パターン**:
- 「もう5件提案して」「もう5件教えて」
- 「もっと他の{category_name}」「もっと提案して」「他の提案を見る」

**タスク構成**:
a. **task1**: `history_service.history_get_recent_titles(user_id, "{category}", 14)` を呼び出し、14日間の{category_name}履歴を取得する。
   - user_id: "{user_id}"

b. **task2**: `session_service.session_get_proposed_titles(sse_session_id, "{category}")` を呼び出し、セッション内で提案済みのタイトルを取得する。
   - **重要**: sse_session_idパラメータには、上記の「現在のSSEセッションID」の値を使用してください。決して固定値（例: "session123"）を使用しないでください。

c. **task3**: `recipe_service.generate_proposals(category="{category}")` を呼び出す。その際:
   - `inventory_items`: 文字列リテラルとして "session.context.inventory_items" と指定（システムが自動的にセッションから取得）
   - `excluded_recipes`: "task1.result.data + task2.result.data"（履歴 + セッション提案済み）
   - `main_ingredient`: 文字列リテラルとして "session.context.main_ingredient" と指定
   - `menu_type`: 文字列リテラルとして "session.context.menu_type" と指定
   - **重要**: inventory_itemsパラメータには絶対に "session_inventory" という名前を使用しないこと
   - `category`: "{category}"
   {f'   - `category_detail_keyword`: 文字列リテラルとして "session.context.category_detail_keyword" と指定（otherカテゴリの場合のみ）' if category == "other" else ''}

d. **task4**: `recipe_service.search_recipes_from_web()` を呼び出す。その際、task3で取得したレシピタイトルを `recipe_titles` パラメータに設定する。

**重要**: 
- 追加提案の場合、在庫取得タスク（inventory_service.get_inventory）は生成しないでください。セッション内に保存された在庫情報を再利用してください。
- session_get_proposed_titlesのsse_session_idパラメータには、必ずプロンプトに示された「現在のSSEセッションID」を使用してください。

**パラメータ注入のルール（追加提案対応）**:
- 履歴除外リスト: `"excluded_recipes": "task1.result.data"`
- セッション提案済み除外リスト: 上記に追加で `+ task2.result.data`
- 在庫情報: セッションコンテキストから取得（タスクではなくコンテキスト参照）
- 主要食材: セッションコンテキストから取得
"""

