# Cookpad画像表示問題の修正プラン

## 問題の概要

### 現状
- **ローカル環境**: Cookpadのレシピ画像が正常に表示される
- **本番環境**: 画像が×（エラー）で表示される

### 原因
1. **Next.js API Route経由でのHTML取得が失敗**
   - 本番環境のNext.jsサーバーからCookpadにアクセスすると、Cloudflareの「Client Challenge」ページが返される
   - ローカル環境では正常にHTMLが取得できている
   - 本番環境のIPアドレスがBotとして検出されている可能性

2. **バックエンドからの画像URL提供がない**
   - Google Searchクライアントには画像URL取得機能がない
   - Perplexityクライアントには画像取得機能があるが、現在は使用されていない

## 解決策

### 方法1: バックエンドで画像URLを取得（推奨・モバイル対応）

Google Searchクライアントに画像取得機能を追加する方法。

#### メリット
- **モバイルアプリ対応**: モバイルアプリがバックエンドAPIを直接呼ぶため、バックエンドで実装すれば両方で使える
- **コードの一元管理**: Webアプリとモバイルアプリで同じロジックを使用できる
- **メンテナンス性**: 1箇所の修正で両方に反映される
- **他のレシピサイトにも対応可能**: 将来的に拡張しやすい

#### 実装内容

**1. レシピURLからレシピIDを抽出**
```
URL例: https://cookpad.com/jp/recipes/18584308
レシピID: 18584308
正規表現: /recipes/(\d+)/
```

**2. OGP画像URLを構築**
```
パターン: https://og-image.cookpad.com/global/jp/recipe/{RECIPE_ID}
例: https://og-image.cookpad.com/global/jp/recipe/18584308
```

**3. 実装場所**
- `/app/Morizo-aiv2/mcp_servers/recipe_web_google.py`に画像URL構築機能を追加
- `/app/Morizo-aiv2/services/llm/web_search_integrator.py`で画像URLを統合

### 方法2: Next.jsサーバーサイドで実装（代替案）

Next.jsのAPI Routeで画像URLを構築する方法。

#### メリット
- 実装が簡単
- Webアプリ専用なら十分

#### デメリット
- **モバイルアプリ対応が必要**: モバイルアプリがNext.js API Routeを呼べるか確認が必要
- **コードの重複**: モバイルアプリでも同じロジックが必要になる可能性
- **メンテナンス性**: 2箇所で管理する必要がある

## 実装プラン（方法1: バックエンド実装・推奨）

### アーキテクチャの確認

- **Webアプリ**: Next.js API Route → バックエンドAPI（`MORIZO_AI_URL`）
- **モバイルアプリ**: バックエンドAPIを直接呼び出し（推測）
- **バックエンド**: FastAPI、CORS設定で直接アクセス可能

**結論**: バックエンドで実装すれば、Webアプリとモバイルアプリの両方で使用可能

### ステップ1: Google Searchクライアントに画像URL構築機能を追加

**ファイル**: `/app/Morizo-aiv2/mcp_servers/recipe_web_google.py`

**追加するメソッド**:
```python
def _extract_cookpad_recipe_id(self, url: str) -> Optional[str]:
    """CookpadのURLからレシピIDを抽出"""
    import re
    match = re.search(r'/recipes/(\d+)', url)
    return match.group(1) if match else None

def _build_cookpad_ogp_image_url(self, url: str) -> Optional[str]:
    """CookpadのOGP画像URLを構築"""
    recipe_id = self._extract_cookpad_recipe_id(url)
    if not recipe_id:
        return None
    return f"https://og-image.cookpad.com/global/jp/recipe/{recipe_id}"
```

**修正するメソッド**: `_parse_search_results`
```python
def _parse_search_results(self, items: List[Dict]) -> List[Dict[str, Any]]:
    """検索結果を解析・整形"""
    recipes = []
    
    for item in items:
        # サイト名を特定
        site_name = identify_site(item.get('link', ''))
        
        recipe = {
            'title': item.get('title', ''),
            'url': item.get('link', ''),
            'description': item.get('snippet', ''),
            'site': site_name,
            'source': RECIPE_SITES.get(site_name, 'Unknown')
        }
        
        # CookpadのURLの場合は、OGP画像URLを追加
        if site_name == 'cookpad.com':
            image_url = self._build_cookpad_ogp_image_url(recipe['url'])
            if image_url:
                recipe['image_url'] = image_url
                logger.debug(f"🖼️ [GOOGLE] Built Cookpad OGP image URL: {image_url}")
        
        recipes.append(recipe)
    
    return recipes
```

### ステップ2: web_search_integrator.pyの確認

**ファイル**: `/app/Morizo-aiv2/services/llm/web_search_integrator.py`

**確認事項**:
- 行185-187で`image_url`が正しく統合されているか
- CookpadのURLの場合、`image_url`が設定されているか

**現在の実装**（行184-188）:
```python
# 画像URLが存在する場合は追加
if web_result.get("image_url"):
    url_info["image_url"] = web_result.get("image_url")
    self.logger.debug(f"🖼️ [WebSearchResultIntegrator] Found image URL for candidate '{candidate_title}': {web_result.get('image_url')}")
```

この部分は既に実装済み（修正不要）

### ステップ3: モバイルアプリでの使用確認

**確認事項**:
- モバイルアプリがバックエンドAPIからレスポンスを受け取る際、`image_url`フィールドが含まれているか
- モバイルアプリ側で`image_url`を使用して画像を表示しているか

### ステップ4: テスト

**テストケース**:
1. CookpadのレシピURLからOGP画像URLが正しく構築されるか
2. 構築されたURLで画像が表示されるか
3. 非CookpadのURLでは既存の処理が動作するか
4. エラーハンドリングが適切か

**テストコマンド**:
```bash
# レシピID抽出のテスト
node -e "const url = 'https://cookpad.com/jp/recipes/18584308'; const match = url.match(/\/recipes\/(\d+)/); console.log('Recipe ID:', match ? match[1] : 'Not found');"

# OGP画像URL構築のテスト
node -e "const recipeId = '18584308'; console.log('OGP URL:', \`https://og-image.cookpad.com/global/jp/recipe/\${recipeId}\`);"

# 画像URLのアクセステスト
curl -I "https://og-image.cookpad.com/global/jp/recipe/18584308"
```

## 実装プラン（方法2: Next.jsサーバーサイド実装・代替案）

### ステップ1: image-extractor.tsにCookpad用関数を追加

**ファイル**: `/app/Morizo-web/lib/image-extractor.ts`

**追加する関数**:
```typescript
/**
 * CookpadのレシピURLからOGP画像URLを直接構築
 * @param url CookpadのレシピURL
 * @returns OGP画像URL（取得失敗時はnull）
 */
export function buildCookpadOGPImageUrl(url: string): string | null {
  try {
    // レシピIDを抽出
    const recipeIdMatch = url.match(/\/recipes\/(\d+)/);
    if (!recipeIdMatch || !recipeIdMatch[1]) {
      return null;
    }
    
    const recipeId = recipeIdMatch[1];
    
    // OGP画像URLを構築
    return `https://og-image.cookpad.com/global/jp/recipe/${recipeId}`;
  } catch (error) {
    console.warn(`Cookpad OGP画像URL構築に失敗しました (${url}):`, error);
    return null;
  }
}

/**
 * URLがCookpadのレシピURLかどうかを判定
 */
export function isCookpadUrl(url: string): boolean {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.includes('cookpad.com') && 
           urlObj.pathname.includes('/recipes/');
  } catch {
    return false;
  }
}
```

### ステップ2: extractImageFromUrl関数を修正

**ファイル**: `/app/Morizo-web/lib/image-extractor.ts`

**修正内容**:
```typescript
export async function extractImageFromUrl(url: string): Promise<string | null> {
  try {
    // CookpadのURLの場合は、OGP画像URLを直接構築
    if (isCookpadUrl(url)) {
      const ogpImageUrl = buildCookpadOGPImageUrl(url);
      if (ogpImageUrl) {
        return ogpImageUrl;
      }
    }
    
    // 既存の処理（他のサイト用）
    // ... 既存のコード ...
  } catch (error) {
    // ... 既存のエラーハンドリング ...
  }
}
```

### ステップ3: モバイルアプリでの対応

**注意事項**:
- モバイルアプリがNext.js API Routeを呼べるか確認が必要
- 呼べない場合は、モバイルアプリ側でも同じロジックを実装する必要がある

## 推奨実装順序

1. **方法1（バックエンド側）を優先実装** ⭐推奨
   - **モバイルアプリ対応**: Webアプリとモバイルアプリの両方で使用可能
   - **コードの一元管理**: 1箇所の修正で両方に反映される
   - **メンテナンス性**: 将来的な拡張が容易
   - **本番環境でも確実に動作**: OGP画像URLの直接構築により、Cloudflareのチャレンジを回避

2. **方法2（Next.js側）は代替案**
   - Webアプリ専用の場合に検討
   - モバイルアプリがNext.js API Routeを呼べる場合に検討

## 注意事項

### CookpadのOGP画像URLの仕様
- パターン: `https://og-image.cookpad.com/global/jp/recipe/{RECIPE_ID}`
- タイムスタンプは不要（HTTP 304でも正常）
- レシピIDは数値のみ

### エラーハンドリング
- レシピIDが抽出できない場合: `null`を返す
- 画像URLが構築できない場合: 既存のHTML取得方法にフォールバック
- 画像が読み込めない場合: プレースホルダー画像を表示

### パフォーマンス
- OGP画像URLの直接構築は高速（HTML取得不要）
- 画像の読み込みテストはオプション（タイムアウトに注意）

## 参考情報

### 調査結果
- ローカル環境: Cookpadへの直接アクセス成功（HTTP 200）
- 本番環境: Next.js API Route経由でCloudflareチャレンジページが返される
- OGP画像URLの直接構築: 成功（HTTP 200/304）

### 関連ファイル
- `/app/Morizo-web/lib/image-extractor.ts`: 画像抽出ロジック
- `/app/Morizo-web/components/ImageHandler.tsx`: 画像表示コンポーネント
- `/app/Morizo-web/app/api/image-proxy/route.ts`: 画像プロキシAPI
- `/app/Morizo-aiv2/mcp_servers/recipe_web_google.py`: Google Searchクライアント

### テスト結果
```bash
# レシピID抽出テスト
URL: https://cookpad.com/jp/recipes/18584308
レシピID: 18584308 ✅

# OGP画像URL構築テスト
URL: https://og-image.cookpad.com/global/jp/recipe/18584308
HTTP Status: 200 ✅
```

## 実装チェックリスト（方法1: バックエンド実装）

- [ ] `recipe_web_google.py`に`_extract_cookpad_recipe_id`メソッドを追加
- [ ] `recipe_web_google.py`に`_build_cookpad_ogp_image_url`メソッドを追加
- [ ] `_parse_search_results`メソッドを修正（Cookpad判定と画像URL追加）
- [ ] `web_search_integrator.py`で`image_url`が正しく統合されることを確認
- [ ] テストケースを作成・実行
- [ ] ローカル環境で動作確認（Webアプリ）
- [ ] ローカル環境で動作確認（モバイルアプリ・可能であれば）
- [ ] 本番環境で動作確認（Webアプリ）
- [ ] 本番環境で動作確認（モバイルアプリ）
- [ ] エラーハンドリングの確認
- [ ] パフォーマンステスト

## 実装チェックリスト（方法2: Next.js実装・代替案）

- [ ] `image-extractor.ts`に`buildCookpadOGPImageUrl`関数を追加
- [ ] `image-extractor.ts`に`isCookpadUrl`関数を追加
- [ ] `extractImageFromUrl`関数を修正（Cookpad判定を追加）
- [ ] モバイルアプリがNext.js API Routeを呼べるか確認
- [ ] モバイルアプリ側でも同じロジックを実装（必要に応じて）
- [ ] テストケースを作成・実行
- [ ] ローカル環境で動作確認
- [ ] 本番環境で動作確認
- [ ] エラーハンドリングの確認
- [ ] パフォーマンステスト

## アーキテクチャの考慮事項

### WebアプリとモバイルアプリのAPI呼び出しパターン

**確認結果**:
- **Webアプリ**: Next.js API Route → バックエンドAPI（`MORIZO_AI_URL`）
- **モバイルアプリ**: バックエンドAPIを直接呼び出し（推測、CORS設定から判断）
- **バックエンド**: FastAPI、CORS設定で`allow_origins=["*"]`により直接アクセス可能

**結論**:
- バックエンドで実装すれば、Webアプリとモバイルアプリの両方で使用可能
- Next.js API Routeで実装した場合、モバイルアプリが呼べるか確認が必要
- **推奨**: バックエンドで実装（方法1）

### Next.js API Routeをモバイルアプリから呼べるか？

**技術的には可能**:
- Next.js API RouteはREST APIとして公開できる
- CORS設定により、モバイルアプリからも呼び出し可能

**ただし**:
- モバイルアプリがNext.jsのURLを知っている必要がある
- モバイルアプリがバックエンドを直接呼ぶ設計の場合、Next.js API Routeは使えない
- コードの重複が発生する可能性がある

## 更新履歴

- 2025-11-21: 初版作成
  - 問題の調査結果をまとめ
  - 解決策を2つ提示
  - 方法1（推奨）の詳細実装プランを作成
- 2025-11-21: モバイルアプリ対応を考慮して更新
  - 方法1をバックエンド実装に変更（モバイル対応のため）
  - 方法2をNext.js実装に変更（代替案）
  - アーキテクチャの考慮事項を追加

