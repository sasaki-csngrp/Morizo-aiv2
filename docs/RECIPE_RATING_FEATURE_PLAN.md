# レシピ評価機能実装プラン

## 概要

ユーザーが過去に作ったレシピに対して評価とコメントを登録できる機能を実装します。評価はレシピ提案時に考慮され、評価が低い（好きじゃない）レシピは提案から除外されます。

## 要件定義

### 評価の値

- **5**: 好き
- **3**: 普通
- **1**: 好きじゃない

既存の`rating`カラムの制約（1-5）をそのまま利用可能です。

### 機能要件

1. **評価・コメント登録機能**
   - 履歴画面でレシピをタップすると評価モーダルが表示される
   - 評価選択：赤ハート（5=好き）、白ハート（3=普通）、ハートブレイク（1=好きじゃない）
   - コメント入力：テキストエリア
   - 登録・キャンセルボタン

2. **評価表示機能**
   - 履歴欄に評価がある場合は♡マークを表示
   - コメントがある場合はコメントマークを表示

3. **レシピ画像表示**
   - 評価モーダルにレシピ画像を表示
   - 画像をクリックするとレシピURLへ別タブで遷移
   - 画像URLはバックエンド側でOGP画像URLを生成（本番環境でのボットチャレンジ回避のため）

4. **レシピ提案時の除外機能**
   - （将来実装）`rating = 1`（好きじゃない）のレシピは提案から除外
   - `rating IS NULL`の場合は提案に含める（評価未設定）

## 実装詳細

### 1. データベース

#### 1.1 テーブル構造

既存の`recipe_historys`テーブルを使用：
- `rating`: INTEGER（既存、1-5の制約あり、そのまま使用）
- `notes`: TEXT（既存、そのまま使用）

**変更不要** - 既存のカラムをそのまま利用します。

---

### 2. バックエンド実装

#### 2.1 画像URL生成ユーティリティの共通化

**修正場所**: `mcp_servers/utils.py`または`mcp_servers/recipe_web_utils.py`（既存のutilsファイルに追加）

**現状**:
- `mcp_servers/recipe_web_google.py`に`_build_cookpad_ogp_image_url`と`_extract_cookpad_recipe_id`メソッドが存在
- `mcp_servers/services/recipe_service.py`にも同様のロジックがインライン実装されている

**修正内容**:
- 既存の2か所の実装を共通ユーティリティ関数としてまとめる
- `mcp_servers/utils.py`または`mcp_servers/recipe_web_utils.py`に共通関数を追加
- 既存の実装箇所を共通関数の呼び出しに置き換える

```python
"""
既存の実装を共通化
"""
import re
from typing import Optional
from config.constants import DEFAULT_RECIPE_IMAGE_URL


def build_recipe_image_url(url: str) -> str:
    """
    レシピURLから画像URLを生成（共通ユーティリティ）
    
    Args:
        url: レシピのURL
        
    Returns:
        str: 画像URL（OGP画像URLまたはデフォルト画像URL）
    """
    if not url:
        return DEFAULT_RECIPE_IMAGE_URL
    
    # CookpadのURLの場合
    if "cookpad.com" in url:
        recipe_id = extract_cookpad_recipe_id(url)
        if recipe_id:
            return f"https://og-image.cookpad.com/global/jp/recipe/{recipe_id}"
    
    # その他のサイトの場合はデフォルト画像を使用
    return DEFAULT_RECIPE_IMAGE_URL


def extract_cookpad_recipe_id(url: str) -> Optional[str]:
    """CookpadのURLからレシピIDを抽出（共通ユーティリティ）"""
    match = re.search(r'/recipes/(\d+)', url)
    return match.group(1) if match else None
```

**既存実装の置き換え**:
1. `mcp_servers/recipe_web_google.py`の`_build_cookpad_ogp_image_url`と`_extract_cookpad_recipe_id`を共通関数の呼び出しに変更
2. `mcp_servers/services/recipe_service.py`のインライン実装を共通関数の呼び出しに変更

**修正理由**: 重複コードを削減し、保守性を向上させるため

**修正の影響**: 既存の実装を共通関数に置き換えるため、既存機能への影響は最小限（動作は同じ）

---

#### 2.2 CRUD層: 評価・コメント更新メソッド

**修正場所**: `mcp_servers/recipe_history_crud.py`の`RecipeHistoryCRUD`クラス

**修正内容**:
- `update_history_by_id`メソッドに`rating`と`notes`パラメータを追加
- 既存のメソッドを拡張して後方互換性を維持

```python
async def update_history_by_id(
    self, 
    client: Client, 
    user_id: str, 
    history_id: str,
    title: Optional[str] = None,
    source: Optional[str] = None,
    url: Optional[str] = None,
    rating: Optional[int] = None,  # 追加
    notes: Optional[str] = None     # 追加
) -> Dict[str, Any]:
```

**修正理由**: 評価・コメント更新をCRUD層で処理するため

**修正の影響**: 既存の`update_history_by_id`の呼び出しは後方互換性により影響なし（オプショナルパラメータのため）

---

#### 2.3 APIエンドポイント: 評価・コメント更新

**修正場所**: `api/routes/menu.py`（新規エンドポイント追加）

**修正内容**:
- `PUT /api/menu/history/{history_id}/rating`エンドポイントを追加
- リクエストボディ: `{"rating": int, "notes": str}`
- レスポンス: 更新後のレシピ履歴データ

```python
@router.put("/menu/history/{history_id}/rating")
async def update_recipe_rating(
    history_id: str,
    request: RecipeRatingUpdateRequest,
    http_request: Request = None
):
    """レシピ履歴の評価・コメントを更新"""
    # 認証処理
    # CRUD層のupdate_history_by_idを呼び出し
    # 画像URLを生成してレスポンスに含める
```

**修正理由**: フロントエンドから評価・コメントを保存するため

**修正の影響**: 新規エンドポイントのため既存機能への影響なし

---

#### 2.4 リクエスト/レスポンスモデル

**修正場所**: `api/models/responses.py`

**修正内容**:

1. **リクエストモデル追加**:
```python
class RecipeRatingUpdateRequest(BaseModel):
    rating: Optional[int] = Field(None, description="評価（5=好き、3=普通、1=好きじゃない）")
    notes: Optional[str] = Field(None, description="コメント")
```

2. **HistoryRecipeモデル拡張**:
```python
class HistoryRecipe(BaseModel):
    """履歴レシピ情報"""
    category: Optional[str] = Field(None, description="カテゴリ（main, sub, soup, None）")
    title: str = Field(..., description="レシピのタイトル")
    source: str = Field(..., description="レシピの出典（web, rag等）")
    url: Optional[str] = Field(None, description="レシピのURL")
    history_id: str = Field(..., description="レシピ履歴のID")
    rating: Optional[int] = Field(None, description="評価（5=好き、3=普通、1=好きじゃない）")  # 追加
    notes: Optional[str] = Field(None, description="コメント")  # 追加
    image_url: Optional[str] = Field(None, description="レシピ画像URL")  # 追加
```

**修正理由**: APIリクエスト/レスポンスの型定義を明確化するため

**修正の影響**: レスポンス構造の変更。既存のフロントエンドコードに影響する可能性あり

---

#### 2.5 履歴取得API: rating/notes/image_urlを含める

**修正場所**: `api/routes/menu.py`の`get_menu_history`関数

**修正内容**:
- データベース取得時に`rating`と`notes`を含める
- 各レシピの`url`から`image_url`を生成してレスポンスに含める

```python
# 画像URL生成ユーティリティをインポート（共通化後の関数）
from mcp_servers.utils import build_recipe_image_url
# または
# from mcp_servers.recipe_web_utils import build_recipe_image_url

# 履歴エントリ作成時に画像URLを生成
history_by_date[date_key].append(HistoryRecipe(
    category=recipe_category,
    title=title,
    source=item.get("source", "web"),
    url=item.get("url"),
    history_id=item.get("id"),
    rating=item.get("rating"),  # 追加
    notes=item.get("notes"),    # 追加
    image_url=build_recipe_image_url(item.get("url"))  # 追加
))
```

**修正理由**: フロントエンドで評価・コメント・画像を表示するため

**修正の影響**: レスポンス構造の変更。既存のフロントエンドコードに影響する可能性あり

---

### 3. フロントエンド実装

#### 3.1 評価モーダルコンポーネント

**新規作成**: `/app/Morizo-web/components/RecipeRatingModal.tsx`

**実装内容**:
- レシピ画像表示（`image_url`を使用）
- 画像クリックでレシピURLへ別タブで遷移
- 評価選択UI（赤ハート=5、白ハート=3、ハートブレイク=1）
- コメント入力（テキストエリア）
- 登録・キャンセルボタン
- API呼び出しで評価・コメントを保存

**主要な機能**:
```typescript
interface RecipeRatingModalProps {
  isOpen: boolean;
  onClose: () => void;
  recipe: {
    history_id: string;
    title: string;
    url?: string;
    image_url?: string;
    rating?: number;
    notes?: string;
  };
  onSave: (rating: number | null, notes: string) => void;
}
```

**修正理由**: ユーザーが評価・コメントを入力するUIを提供するため

**修正の影響**: 新規コンポーネントのため既存機能への影響なし

---

#### 3.2 HistoryPanel: 評価表示とモーダル統合

**修正場所**: `/app/Morizo-web/components/HistoryPanel.tsx`

**修正内容**:

1. **インターフェース拡張**:
```typescript
interface HistoryRecipe {
  category: string | null;
  title: string;
  source: string;
  url?: string;
  history_id: string;
  duplicate_warning?: string;
  rating?: number;      // 追加
  notes?: string;       // 追加
  image_url?: string;   // 追加
}
```

2. **評価・コメントアイコン表示**:
```typescript
// 評価がある場合
{recipe.rating && (
  <span className="text-red-500">♡</span>
)}

// コメントがある場合
{recipe.notes && (
  <span className="text-blue-500">💬</span>
)}
```

3. **クリックイベントとモーダル表示**:
```typescript
const [selectedRecipe, setSelectedRecipe] = useState<HistoryRecipe | null>(null);
const [isRatingModalOpen, setIsRatingModalOpen] = useState(false);

// レシピクリック時にモーダルを開く
<div
  onClick={() => {
    setSelectedRecipe(recipe);
    setIsRatingModalOpen(true);
  }}
  className="cursor-pointer"
>
  {/* レシピ表示 */}
</div>

// 評価モーダル
<RecipeRatingModal
  isOpen={isRatingModalOpen}
  onClose={() => setIsRatingModalOpen(false)}
  recipe={selectedRecipe}
  onSave={handleRatingSave}
/>
```

4. **評価保存処理**:
```typescript
const handleRatingSave = async (rating: number | null, notes: string) => {
  if (!selectedRecipe) return;
  
  const response = await authenticatedFetch(
    `/api/menu/history/${selectedRecipe.history_id}/rating`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating, notes })
    }
  );
  
  if (response.ok) {
    // 履歴を再読み込み
    loadHistory();
    setIsRatingModalOpen(false);
  }
};
```

**修正理由**: 履歴画面で評価を表示・編集できるようにするため

**修正の影響**: 既存の履歴表示UIの変更。クリック可能になる

---

## 実装順序

### Phase 1: バックエンド基盤
1. 画像URL生成ユーティリティの共通化（既存実装の統合）
2. CRUD層の拡張（評価・コメント更新）
3. リクエスト/レスポンスモデルの追加・拡張
4. 履歴取得APIの拡張（rating/notes/image_urlを含める）
5. 評価更新APIエンドポイントの追加

### Phase 2: フロントエンド
7. 評価モーダルコンポーネントの作成
8. HistoryPanelの拡張（評価表示・モーダル統合）

---

## テスト計画

### バックエンドテスト
1. 画像URL生成のテスト（Cookpad URL、その他のURL）
2. 評価・コメント更新APIのテスト
3. 履歴取得APIのテスト（rating/notes/image_urlが含まれること）

### フロントエンドテスト
1. 評価モーダルの表示・操作テスト
2. 評価・コメントの保存テスト
3. 履歴画面での評価・コメント表示テスト
4. 画像クリックでURL遷移のテスト

---

## 注意事項

1. **後方互換性**: 既存の`update_history_by_id`メソッドは後方互換性を維持（オプショナルパラメータ）
2. **評価未設定**: `rating IS NULL`の場合は提案に含める
3. **画像URL**: バックエンド側でOGP画像URLを生成することで、本番環境でのボットチャレンジを回避
4. **モバイル対応**: 既存のスタイルに合わせて実装（ネイティブアプリは別途対応）

---

## 参考実装

### OGP画像URL生成の参考コード

- `mcp_servers/recipe_web_google.py`の`_build_cookpad_ogp_image_url`メソッド
- `mcp_servers/services/recipe_service.py`のCookpad OGP画像URL構築処理

### 評価アイコンの参考

- 赤ハート: `❤️` または `<Heart className="text-red-500" />`（アイコンライブラリ使用）
- 白ハート: `🤍` または `<Heart className="text-gray-400" />`
- ハートブレイク: `💔` または `<HeartBreak className="text-purple-800 dark:text-purple-600" />`（濃い紫の毒々しい色）

---

## 将来実装

### レシピ提案時の除外機能（rating=1の除外）

**修正場所**: `mcp_servers/recipe_history_crud.py`の`get_recent_recipe_titles`メソッド

**実装内容**:
- 履歴取得時に`rating != 1`の条件を追加
- `rating IS NULL OR rating != 1`で評価未設定も含める

```python
result = client.table("recipe_historys")\
    .select("title")\
    .eq("user_id", user_id)\
    .gte("cooked_at", cutoff_date.isoformat())\
    .or_("rating.is.null,rating.neq.1")\  # 追加
    .execute()
```

**実装理由**: 評価1（好きじゃない）のレシピを提案から除外するため

**実装の影響**: 提案ロジックの変更。評価1のレシピは提案されなくなる

**注意**: 今回は実装対象外。評価機能の実装完了後、別途実装を検討する。

