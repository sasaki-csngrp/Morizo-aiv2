Google Search APIのキーとSearch Engine IDの作成手順です。

## Google Search API の設定手順

### 1. Google Cloud Console での設定

#### 1-1. プロジェクトの作成（または既存プロジェクトの選択）
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成、または既存プロジェクトを選択

#### 1-2. Custom Search API の有効化
1. 左メニューから「APIとサービス」→「ライブラリ」を選択
2. 検索バーで「Custom Search API」を検索
3. 「Custom Search API」を選択して「有効にする」をクリック

#### 1-3. API キーの作成
1. 「APIとサービス」→「認証情報」を選択
2. 「認証情報を作成」→「APIキー」を選択
3. 作成されたAPIキーをコピー（後で使用）
4. （推奨）APIキーをクリックして「アプリケーションの制限」を設定
   - 「HTTPリファラー」を選択
   - 許可するドメインを追加（例: `localhost:8000`、本番ドメインなど）

### 2. Custom Search Engine の作成

#### 2-1. Custom Search Engine の作成
1. [Google Custom Search](https://programmablesearchengine.google.com/) にアクセス
2. 「新しい検索エンジンを作成」をクリック
3. 設定を入力：
   - 検索するサイト: レシピサイトを指定
     - `cookpad.com`
     - `kurashiru.com`
     - `recipe.rakuten.co.jp`
     - `delishkitchen.tv`
   - 検索エンジン名: 任意（例: "Morizo Recipe Search"）
4. 「作成」をクリック

#### 2-2. Search Engine ID の取得
1. 作成した検索エンジンの「設定」を開く
2. 「基本」タブの「検索エンジンID」をコピー（後で使用）

#### 2-3. 検索対象サイトの追加（オプション）
1. 「設定」→「基本」で「サイトを追加」から対象サイトを追加
2. または「高度な設定」で検索対象を調整

### 3. 環境変数の設定

取得した情報を `.env` に設定：

```bash
# Google Search API設定
GOOGLE_SEARCH_API_KEY=取得したAPIキー
GOOGLE_SEARCH_ENGINE_ID=取得した検索エンジンID
```

### 4. 動作確認

設定後、アプリケーションを再起動してレシピ検索機能をテストしてください。

## 注意事項

1. APIキーの制限: 本番環境では「HTTPリファラー」で制限を設定してください
2. 無料枠: Custom Search APIは1日100リクエストまで無料（超過は有料）
3. 検索対象: 検索エンジンIDは対象サイトの設定と一致している必要があります

## 現在のコードでの使用箇所

```21:34:mcp_servers/recipe_web.py
class _GoogleSearchClient:
    """Google Search APIを使用したレシピ検索クライアント"""
    
    # モック機能の切り替えフラグ（課金回避用）
    USE_MOCK_SEARCH = True
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
        self.engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        
        if not self.api_key or not self.engine_id:
            raise ValueError("GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID are required")
        
        self.service = build("customsearch", "v1", developerKey=self.api_key)
```

現在は `USE_MOCK_SEARCH = True` のためモックデータを使用しています。実際のAPIを使用する場合は、このフラグを `False` に変更してください。

不明点があれば知らせてください。