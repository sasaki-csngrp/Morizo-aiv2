# モバイルアプリ向け：レシピ画像URL対応の更新メモ

## 概要

Webアプリ（Morizo-web）で実装したレシピ画像URL対応を、モバイルアプリにも反映する必要があります。

## 背景

Perplexity検索でクラシル・デリッシュキッチンのレシピがヒットするようになりましたが、これらのサイトではプレビュー画像が表示できませんでした。バックエンドでHTMLをスクレイピングして画像URLを取得し、フロントエンドで直接使用できるようにしました。

## Webアプリでの修正内容

### 1. 型定義の更新

**ファイル**: `/app/Morizo-web/types/menu.ts`

`RecipeUrl`インターフェースに`image_url`フィールドを追加：

```typescript
export interface RecipeUrl {
  /** URLのタイトル */
  title: string;
  /** 実際のURL */
  url: string;
  /** ドメイン名 */
  domain: string;
  /** 画像URL（オプション、バックエンドから提供される場合がある） */
  image_url?: string;  // ← 新規追加
}
```

### 2. ImageHandlerコンポーネントの修正

**ファイル**: `/app/Morizo-web/components/ImageHandler.tsx`

画像取得ロジックを修正し、バックエンドから提供された`image_url`を優先的に使用するように変更：

```typescript
// 修正前
const extractedImageUrl = await extractImageFromUrl(urls[0].url);

// 修正後
// バックエンドから提供されたimage_urlを優先的に使用
if (urls[0]?.image_url) {
  setImageUrl(urls[0].image_url);
  setImageLoading(false);
  return;
}

// image_urlが存在しない場合のみ、URLから画像を抽出
const extractedImageUrl = await extractImageFromUrl(urls[0].url);
```

## バックエンドの変更

### 画像URLの提供

バックエンド（Morizo-aiv2）から以下の形式でレスポンスが返されます：

```json
{
  "candidates": [
    {
      "title": "レシピタイトル",
      "ingredients": ["食材1", "食材2"],
      "source": "llm",
      "urls": [
        {
          "title": "レシピタイトル",
          "url": "https://www.kurashiru.com/recipes/...",
          "domain": "www.kurashiru.com",
          "image_url": "https://video.kurashiru.com/production/videos/.../compressed_thumbnail_square_large.jpg"  // ← 新規追加
        }
      ]
    }
  ]
}
```

## モバイルアプリで必要な対応

### 1. 型定義の更新

モバイルアプリの`RecipeUrl`型（または相当する型）に`image_url`フィールドを追加してください。

**例（TypeScript/TypeScript React Nativeの場合）**：

```typescript
interface RecipeUrl {
  title: string;
  url: string;
  domain: string;
  image_url?: string;  // ← 追加
}
```

### 2. 画像表示コンポーネントの修正

レシピ画像を表示するコンポーネントで、以下の優先順位で画像URLを取得するように修正してください：

1. **優先**: `urls[0].image_url`が存在する場合は、それを直接使用
2. **フォールバック**: `image_url`が存在しない場合のみ、URLから画像を抽出（既存のロジック）

**実装例**：

```typescript
// 画像URLを取得
const getImageUrl = async (urls: RecipeUrl[]) => {
  // バックエンドから提供されたimage_urlを優先的に使用
  if (urls[0]?.image_url) {
    return urls[0].image_url;
  }
  
  // image_urlが存在しない場合のみ、URLから画像を抽出
  return await extractImageFromUrl(urls[0].url);
};
```

### 3. 対応サイト

以下のサイトで画像URLが提供されます：

- **クラシル** (`kurashiru.com`)
- **デリッシュキッチン** (`delishkitchen.tv`)
- **Cookpad** (`cookpad.com`)
- **楽天レシピ** (`recipe.rakuten.co.jp`)

その他のサイトでも、OGP画像が取得できる場合は`image_url`が提供されます。

## メリット

1. **パフォーマンス向上**: URLから画像を抽出する処理が不要になり、表示が高速化
2. **確実性向上**: バックエンドで事前に取得した画像URLを使用するため、表示成功率が向上
3. **クラシル・デリッシュキッチン対応**: これらのサイトの画像が正しく表示される

## 注意事項

- `image_url`はオプショナルフィールドです。存在しない場合は既存のロジック（URLから画像抽出）にフォールバックしてください
- バックエンドで画像取得に失敗した場合、`image_url`は`null`または未定義になります
- 画像URLは絶対URLで提供されます（相対URLの変換は不要）

## 関連ファイル

### Webアプリ
- `/app/Morizo-web/types/menu.ts` - 型定義
- `/app/Morizo-web/components/ImageHandler.tsx` - 画像表示コンポーネント

### バックエンド
- `/app/Morizo-aiv2/mcp_servers/recipe_web.py` - 画像スクレイピング機能
- `/app/Morizo-aiv2/services/llm/web_search_integrator.py` - Web検索結果統合

## 実装日

- Webアプリ修正: 2025-11-20
- バックエンド実装: 2025-11-20

## 確認事項

モバイルアプリで実装後、以下を確認してください：

1. クラシルのレシピで画像が表示されること
2. デリッシュキッチンのレシピで画像が表示されること
3. `image_url`が存在しない場合でも、既存の動作（URLから画像抽出）が正常に動作すること
4. 画像の読み込みエラーが適切にハンドリングされていること

