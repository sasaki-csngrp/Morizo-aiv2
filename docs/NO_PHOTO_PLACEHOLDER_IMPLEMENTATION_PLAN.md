# No Photo プレースホルダー画像実装プラン

## 概要

Cookpadレシピの画像を生成する際に、`image_url`が`None`になるケースでエラー画像が表示される問題を解決するため、バックエンド側に「No Photo」プレースホルダー画像を配置し、`image_url`が`None`の場合にその画像URLを設定する。

## 解決方針

1. **バックエンド側にNo Photo画像を配置**
   - `/app/Morizo-aiv2/static`ディレクトリに`no-photo.png`を配置
   - FastAPIで静的ファイル配信を設定

2. **`image_url`が`None`の場合の処理**
   - `image_url`が`None`の場合、デフォルト画像URL（`http://localhost:8000/static/no-photo.png`）を設定

3. **フロントエンド側の対応**
   - フロントエンド側は変更不要
   - バックエンドから渡された`image_url`をそのまま表示するだけ

## 環境について

- **開発環境**: フロント・バックは同じコンテナなので、`localhost`でアクセス可能
- **本番環境**: フロント・バックは同じGCP VMに配置するので、同様に`localhost`でアクセス可能

## 実装内容

### 1. 静的ファイルの配置

#### 1-1. ディレクトリ作成
- パス: `/app/Morizo-aiv2/static`
- 用途: 静的ファイル（画像など）を配置するディレクトリ

#### 1-2. No Photo画像の配置
- ファイル名: `no-photo.png`（または`no-photo.svg`）
- パス: `/app/Morizo-aiv2/static/no-photo.png`
- 仕様:
  - サイズ: 推奨 300x200px（レシピ画像と同じアスペクト比）
  - 形式: PNGまたはSVG
  - 内容: 「No Photo」または「画像なし」を表示するプレースホルダー

### 2. 静的ファイル配信の設定

#### 2-1. 修正ファイル
- `/app/Morizo-aiv2/main.py`

#### 2-2. 修正内容
FastAPIの`StaticFiles`を使用して`/static`パスで静的ファイルを配信する設定を追加。

```python
from fastapi.staticfiles import StaticFiles

# 静的ファイルの配信設定
app.mount("/static", StaticFiles(directory="static"), name="static")
```

#### 2-3. アクセスURL
- 開発環境: `http://localhost:8000/static/no-photo.png`
- 本番環境: 環境変数でホスト/ポートを設定可能（デフォルト: `http://localhost:8000/static/no-photo.png`）

### 3. `image_url`が`None`の場合の処理

#### 3-1. デフォルト画像URLの定義

設定ファイルまたは定数として定義：

```python
# config/constants.py または適切な場所
DEFAULT_RECIPE_IMAGE_URL = "http://localhost:8000/static/no-photo.png"
```

環境変数で設定可能にする場合：

```python
import os
DEFAULT_RECIPE_IMAGE_URL = os.getenv(
    "DEFAULT_RECIPE_IMAGE_URL",
    "http://localhost:8000/static/no-photo.png"
)
```

#### 3-2. 修正箇所

##### 3-2-1. `mcp_servers/models/recipe_models.py`

**修正内容**: `WebSearchResult.to_dict()`メソッドで、`image_url`が`None`の場合にデフォルト画像URLを設定

```python
def to_dict(self) -> Dict[str, Any]:
    """辞書形式に変換"""
    from config.constants import DEFAULT_RECIPE_IMAGE_URL
    
    result = {
        "title": self.title,
        "url": self.url,
        "source": self.source
    }
    if self.description:
        result["description"] = self.description
    if self.site:
        result["site"] = self.site
    
    # image_urlがNoneの場合はデフォルト画像URLを設定
    result["image_url"] = self.image_url if self.image_url else DEFAULT_RECIPE_IMAGE_URL
    
    return result
```

##### 3-2-2. `mcp_servers/services/recipe_service.py`

**修正箇所1**: `_search_single_recipe_with_rag_fallback()`メソッド内（169行目付近）

```python
# 修正前
image_url=image_url

# 修正後
from config.constants import DEFAULT_RECIPE_IMAGE_URL
image_url=image_url if image_url else DEFAULT_RECIPE_IMAGE_URL
```

**修正箇所2**: `_search_single_recipe_with_rag_fallback()`メソッド内（210行目、247行目付近）

```python
# 修正前
image_url=recipe.get("image_url")

# 修正後
from config.constants import DEFAULT_RECIPE_IMAGE_URL
image_url=recipe.get("image_url") or DEFAULT_RECIPE_IMAGE_URL
```

##### 3-2-3. `mcp_servers/recipe_web_google.py`

**修正箇所1**: `_filter_mock_recipes()`メソッド内（104-107行目付近）

```python
# 修正前
image_url = self._build_cookpad_ogp_image_url(recipe.get('url', ''))
if image_url:
    recipe['image_url'] = image_url

# 修正後
from config.constants import DEFAULT_RECIPE_IMAGE_URL
image_url = self._build_cookpad_ogp_image_url(recipe.get('url', ''))
recipe['image_url'] = image_url if image_url else DEFAULT_RECIPE_IMAGE_URL
```

**修正箇所2**: `_parse_search_results()`メソッド内（148-151行目付近）

```python
# 修正前
if site_name == 'cookpad.com':
    image_url = self._build_cookpad_ogp_image_url(recipe['url'])
    if image_url:
        recipe['image_url'] = image_url

# 修正後
from config.constants import DEFAULT_RECIPE_IMAGE_URL
if site_name == 'cookpad.com':
    image_url = self._build_cookpad_ogp_image_url(recipe['url'])
    recipe['image_url'] = image_url if image_url else DEFAULT_RECIPE_IMAGE_URL
```

##### 3-2-4. `mcp_servers/recipe_web_perplexity.py`

**修正箇所**: `_parse_perplexity_response()`メソッド内（146-155行目付近）

```python
# 修正前
for recipe_data, image_url in zip(recipe_data_list, image_urls):
    recipe = {
        'title': recipe_title,
        'url': recipe_data['url'],
        'description': f'{recipe_title}のレシピ（Perplexity検索）',
        'site': recipe_data['site_name'],
        'source': RECIPE_SITES.get(recipe_data['site_name'], 'Unknown'),
        'image_url': image_url  # 画像URLを追加
    }
    recipes.append(recipe)

# 修正後
from config.constants import DEFAULT_RECIPE_IMAGE_URL
for recipe_data, image_url in zip(recipe_data_list, image_urls):
    recipe = {
        'title': recipe_title,
        'url': recipe_data['url'],
        'description': f'{recipe_title}のレシピ（Perplexity検索）',
        'site': recipe_data['site_name'],
        'source': RECIPE_SITES.get(recipe_data['site_name'], 'Unknown'),
        'image_url': image_url if image_url else DEFAULT_RECIPE_IMAGE_URL
    }
    recipes.append(recipe)
```

## 実装ステップ

1. **静的ファイルディレクトリの作成**
   ```bash
   mkdir -p /app/Morizo-aiv2/static
   ```

2. **No Photo画像の配置**
   - `no-photo.png`を`/app/Morizo-aiv2/static/`に配置

3. **設定ファイルの作成**
   - `config/constants.py`を作成（存在しない場合）
   - `DEFAULT_RECIPE_IMAGE_URL`を定義

4. **`main.py`の修正**
   - 静的ファイル配信の設定を追加

5. **各ファイルの修正**
   - `mcp_servers/models/recipe_models.py`
   - `mcp_servers/services/recipe_service.py`
   - `mcp_servers/recipe_web_google.py`
   - `mcp_servers/recipe_web_perplexity.py`

6. **テスト**
   - `image_url`が`None`の場合にデフォルト画像が表示されることを確認
   - 有効な`image_url`がある場合は従来通り表示されることを確認

## 修正の影響

### メリット
- `image_url`が`None`の場合でも、エラー画像ではなく適切なプレースホルダーが表示される
- フロントエンド側の変更が不要
- ユーザー体験の向上

### 注意点
- 静的ファイル配信の設定が必要
- 本番環境では、環境変数でホスト/ポートを適切に設定する必要がある

## 環境変数（オプション）

本番環境でホスト/ポートを変更する場合：

```bash
# .env または環境変数
DEFAULT_RECIPE_IMAGE_URL=http://localhost:8000/static/no-photo.png
```

## 関連ドキュメント

- [Cookpad画像表示問題の修正プラン](./COOKPAD_IMAGE_DISPLAY_FIX_PLAN.md)（存在する場合）

## 更新履歴

- 2024-XX-XX: 初版作成

