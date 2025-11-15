# 本番環境移行計画書

## 概要

Morizo-web と Morizo-aiv2 を AWS EC2 (Ubuntu 24.04 LTS) 上にデプロイするための本番移行計画書です。

### 対象環境
- **本番環境**: AWS EC2 (Ubuntu 24.04 LTS, t2.micro)
- **ドメイン**: morizo.csngrp.co.jp
- **Supabase**: 開発環境と同じプロジェクトを使用
- **デプロイ方法**: 手動デプロイ（初期）

### 前提条件
- EC2インスタンスが起動済み
- ドメインがEC2インスタンスに紐付け済み
- SSH接続が可能
- 各リポジトリへのアクセス権限があること

### 作業ユーザー

**重要**: この手順書は、rootユーザーではなく、**通常のユーザー（`ubuntu`）**で作業することを想定しています。

- **デフォルトユーザー**: `ubuntu`（EC2のデフォルトユーザー）
- **必要な権限**: sudo権限（パッケージインストール、systemd設定など）
- **セキュリティ**: rootユーザーでの作業は避け、必要な場合のみ`sudo`を使用します

各コマンドの説明：
- `sudo`なしのコマンド → `ubuntu`ユーザーで直接実行
- `sudo`付きのコマンド → 管理者権限が必要な操作

**現在のユーザー確認**:
```bash
# 現在のユーザーを確認
whoami

# ubuntuユーザーであることを確認（他のユーザーの場合は適宜読み替えてください）
```

---

## 1. インフラ構成

### 1.1 EC2インスタンス仕様
- **インスタンスタイプ**: t2.micro
- **OS**: Ubuntu 24.04 LTS
- **ストレージ**: 必要に応じて拡張（ベクトルDBデータ用）

### 1.2 ネットワーク構成
```
インターネット
    ↓
EC2 Security Group (ポート443のみ開放)
    ↓
Ubuntu 24.04 LTS
    ├── Morizo-web (Next.js) - ポート443で公開
    └── Morizo-aiv2 (FastAPI) - ポート8000（localhostのみ）
```

### 1.3 ポート設定
- **外部公開ポート**: 443 (HTTPS)
- **Morizo-web**: 443ポートでリスニング
- **Morizo-aiv2**: 8000ポート（localhost:8000、Morizo-webからのみアクセス）

### 1.4 セキュリティグループ設定
EC2のセキュリティグループで以下を設定：
- **インバウンドルール**:
  - タイプ: HTTPS
  - ポート: 443
  - ソース: 0.0.0.0/0（必要に応じて制限）
- **アウトバウンドルール**: すべて許可（デフォルト）

---

## 2. 初期セットアップ（EC2環境構築）

**作業ユーザー**: `ubuntu`ユーザーで作業を開始してください。

### 2.1 システムパッケージのインストール

```bash
# システムの更新（sudo権限が必要）
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール（sudo権限が必要）
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    nodejs \
    npm \
    git \
    curl \
    build-essential \
    certbot \
    openssl
```

### 2.2 Node.jsのバージョン確認・アップグレード

```bash
# Node.jsバージョン確認（通常ユーザーで実行）
node -v

# 必要に応じて最新のLTSバージョンをインストール（sudo権限が必要）
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2.3 Python環境の確認

```bash
# Python 3.11がインストールされていることを確認（通常ユーザーで実行）
python3.11 --version

# pipのアップグレード（通常ユーザーで実行）
python3.11 -m pip install --upgrade pip --user
```

### 2.4 SSL証明書の取得（Let's Encrypt）

```bash
# Certbotを使用してSSL証明書を取得（sudo権限が必要）
sudo certbot certonly --standalone -d morizo.csngrp.co.jp

# 証明書の場所を確認（通常は以下）
# /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem
# /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem

# 証明書の読み取り権限を確認（ubuntuユーザーが読み取れることを確認）
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/
```

**注意**: 
- SSL証明書の取得には、ドメインがEC2のパブリックIPに正しく向いている必要があります。
- 証明書ファイルはroot所有ですが、Next.jsアプリケーションから読み取れるように、適切な権限設定が必要です（後述）。

---

## 3. Morizo-aiv2 デプロイ手順

**作業ユーザー**: `ubuntu`ユーザーで作業します。

### 3.1 リポジトリのクローン

```bash
# デプロイ用ディレクトリの作成（sudo権限が必要）
sudo mkdir -p /opt/morizo

# ディレクトリの所有権をubuntuユーザーに変更
sudo chown ubuntu:ubuntu /opt/morizo

# ディレクトリに移動
cd /opt/morizo

# 現在のユーザーを確認（ubuntuであることを確認）
whoami

# Morizo-aiv2リポジトリのクローン（通常ユーザーで実行）
git clone <Morizo-aiv2のリポジトリURL> Morizo-aiv2
cd Morizo-aiv2

# ディレクトリの所有権を確認
ls -la
```

### 3.2 Python仮想環境の作成と依存関係のインストール

```bash
# 仮想環境の作成（通常ユーザーで実行）
python3.11 -m venv venv

# 仮想環境のアクティベート
source venv/bin/activate

# 依存関係のインストール
pip install --upgrade pip
pip install -r requirements.txt

# 仮想環境の所有権を確認（ubuntuユーザー所有であることを確認）
ls -la venv/
```

### 3.3 環境変数の設定

```bash
# .envファイルの作成（通常ユーザーで実行）
cp env.example .env

# .envファイルを編集
vi .env

# .envファイルの所有権と権限を確認（ubuntuユーザー所有、読み取り専用）
ls -la .env
# 必要に応じて権限を制限（他のユーザーが読み取れないように）
chmod 600 .env
```

`.env`ファイルに以下を設定：

```bash
# Supabase設定
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# OpenAI設定
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Google Search API設定
GOOGLE_SEARCH_API_KEY=your_google_search_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_google_search_engine_id_here

# RAG検索設定
CHROMA_PERSIST_DIRECTORY_MAIN=/opt/morizo/Morizo-aiv2/recipe_vector_db_main
CHROMA_PERSIST_DIRECTORY_SUB=/opt/morizo/Morizo-aiv2/recipe_vector_db_sub
CHROMA_PERSIST_DIRECTORY_SOUP=/opt/morizo/Morizo-aiv2/recipe_vector_db_soup

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=/opt/morizo/Morizo-aiv2/morizo_ai.log
ENVIRONMENT=production

# サーバー設定
HOST=127.0.0.1
PORT=8000
RELOAD=false
```

### 3.4 ベクトルDBの配置

ベクトルDBデータを配置する場合：

```bash
# ベクトルDBディレクトリの作成（通常ユーザーで実行）
mkdir -p recipe_vector_db_main
mkdir -p recipe_vector_db_sub
mkdir -p recipe_vector_db_soup

# ディレクトリの所有権を確認（ubuntuユーザー所有であることを確認）
ls -ld recipe_vector_db_*

# 既存のベクトルDBデータがある場合、それらをコピー
# scp -r recipe_vector_db_* ubuntu@ec2-instance:/opt/morizo/Morizo-aiv2/
```

### 3.5 systemdサービスファイルの作成

```bash
# systemdサービスファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-aiv2.service
```

**重要**: systemdサービスは`ubuntu`ユーザーで実行されるため、`/opt/morizo/Morizo-aiv2`ディレクトリとその配下のファイルは`ubuntu`ユーザーが読み書きできる必要があります。

以下を記述：

```ini
[Unit]
Description=Morizo AI v2 FastAPI Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/morizo/Morizo-aiv2
Environment="PATH=/opt/morizo/Morizo-aiv2/venv/bin"
ExecStart=/opt/morizo/Morizo-aiv2/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --no-reload
Restart=always
RestartSec=10

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-aiv2

[Install]
WantedBy=multi-user.target
```

### 3.6 systemdサービスの有効化と起動

```bash
# systemd設定のリロード（sudo権限が必要）
sudo systemctl daemon-reload

# サービスの有効化（自動起動設定、sudo権限が必要）
sudo systemctl enable morizo-aiv2

# サービスの起動（sudo権限が必要）
sudo systemctl start morizo-aiv2

# サービスの状態確認（sudo権限が必要）
sudo systemctl status morizo-aiv2

# ログの確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2 -f

# プロセスの所有者を確認（ubuntuユーザーで実行されていることを確認）
ps aux | grep morizo-aiv2
```

---

## 4. Morizo-web デプロイ手順

**作業ユーザー**: `ubuntu`ユーザーで作業します。

### 4.1 リポジトリのクローン

```bash
# /opt/morizoディレクトリに移動
cd /opt/morizo

# 現在のユーザーを確認（ubuntuであることを確認）
whoami

# Morizo-webリポジトリのクローン（通常ユーザーで実行）
git clone <Morizo-webのリポジトリURL> Morizo-web
cd Morizo-web

# ディレクトリの所有権を確認（ubuntuユーザー所有であることを確認）
ls -la
```

### 4.2 依存関係のインストール

```bash
# npmパッケージのインストール（通常ユーザーで実行）
npm install

# node_modulesの所有権を確認（ubuntuユーザー所有であることを確認）
ls -ld node_modules
```

### 4.3 環境変数の設定

```bash
# .env.localファイルの作成（通常ユーザーで実行）
vi .env.local

# .env.localファイルの所有権と権限を確認
ls -la .env.local
# 必要に応じて権限を制限（他のユーザーが読み取れないように）
chmod 600 .env.local
```

`.env.local`ファイルに以下を設定：

```bash
# Supabase設定
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url_here
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Morizo AI URL（localhost経由）
MORIZO_AI_URL=http://localhost:8000
```

**注意**: Next.jsでは、`NEXT_PUBLIC_`プレフィックスの環境変数のみがクライアント側で利用可能です。

### 4.4 本番ビルド

```bash
# 本番用ビルド
npm run build

# ビルドが正常に完了したことを確認
```

### 4.5 Next.jsをHTTPSで起動するための設定

Next.jsを直接HTTPSで起動する場合、カスタムサーバーが必要です。

**作業ユーザー**: `ubuntu`ユーザーで作業します。

`server.js`を作成（プロジェクトルートに）：

```javascript
const { createServer } = require('https');
const { parse } = require('url');
const next = require('next');
const fs = require('fs');

const dev = process.env.NODE_ENV !== 'production';
const hostname = 'morizo.csngrp.co.jp';
const port = 443;

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

const httpsOptions = {
  key: fs.readFileSync('/etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem'),
  cert: fs.readFileSync('/etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem'),
};

app.prepare().then(() => {
  createServer(httpsOptions, async (req, res) => {
    try {
      const parsedUrl = parse(req.url, true);
      await handle(req, res, parsedUrl);
    } catch (err) {
      console.error('Error occurred handling', req.url, err);
      res.statusCode = 500;
      res.end('internal server error');
    }
  }).listen(port, (err) => {
    if (err) throw err;
    console.log(`> Ready on https://${hostname}:${port}`);
  });
});
```

**重要**: 
- `server.js`ファイルを作成後、`ubuntu`ユーザーの所有権であることを確認してください。
- SSL証明書ファイル（`/etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem`と`fullchain.pem`）は、`ubuntu`ユーザーが読み取れる必要があります。必要に応じて証明書ディレクトリの読み取り権限を設定してください：

```bash
# SSL証明書の読み取り権限を確認
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/

# 証明書ディレクトリに読み取り権限がない場合、以下のコマンドで設定（sudo権限が必要）
# 注意: セキュリティ上の理由から、最小限の権限で設定してください
sudo chmod 755 /etc/letsencrypt/live/
sudo chmod 755 /etc/letsencrypt/live/morizo.csngrp.co.jp/
sudo chmod 644 /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem
sudo chmod 600 /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem
```

`package.json`にstartスクリプトを追加：

```json
{
  "scripts": {
    "start": "node server.js"
  }
}
```

### 4.6 systemdサービスファイルの作成

```bash
# systemdサービスファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-web.service
```

**重要**: systemdサービスは`ubuntu`ユーザーで実行されるため、`/opt/morizo/Morizo-web`ディレクトリとその配下のファイル、SSL証明書ファイルは`ubuntu`ユーザーが読み書きできる必要があります。

以下を記述：

```ini
[Unit]
Description=Morizo Web Next.js Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/morizo/Morizo-web
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-web

[Install]
WantedBy=multi-user.target
```

### 4.7 systemdサービスの有効化と起動

```bash
# systemd設定のリロード（sudo権限が必要）
sudo systemctl daemon-reload

# サービスの有効化（自動起動設定、sudo権限が必要）
sudo systemctl enable morizo-web

# サービスの起動（sudo権限が必要）
sudo systemctl start morizo-web

# サービスの状態確認（sudo権限が必要）
sudo systemctl status morizo-web

# ログの確認（sudo権限が必要）
sudo journalctl -u morizo-web -f

# プロセスの所有者を確認（ubuntuユーザーで実行されていることを確認）
ps aux | grep morizo-web
```

---

## 5. 動作確認手順

### 5.1 Morizo-aiv2の動作確認

```bash
# サービスが起動しているか確認（sudo権限が必要）
sudo systemctl status morizo-aiv2

# ローカルでヘルスチェック（通常ユーザーで実行）
curl http://localhost:8000/health

# プロセスの所有者を確認（ubuntuユーザーで実行）
ps aux | grep uvicorn

# ログの確認
# systemdログ（sudo権限が必要）
sudo journalctl -u morizo-aiv2 -n 50
# またはログファイル（通常ユーザーで実行）
tail -f /opt/morizo/Morizo-aiv2/morizo_ai.log
```

### 5.2 Morizo-webの動作確認

```bash
# サービスが起動しているか確認（sudo権限が必要）
sudo systemctl status morizo-web

# プロセスの所有者を確認（ubuntuユーザーで実行）
ps aux | grep node

# ブラウザでアクセス
# https://morizo.csngrp.co.jp

# ログの確認（sudo権限が必要）
sudo journalctl -u morizo-web -n 50
```

### 5.3 統合動作確認

1. ブラウザで `https://morizo.csngrp.co.jp` にアクセス
2. ログイン機能が動作することを確認
3. チャット機能でMorizo-aiv2との通信が正常に行われることを確認

---

## 6. トラブルシューティング

### 6.1 Morizo-aiv2が起動しない

```bash
# エラーログを確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2 -n 100

# ファイルの所有権を確認（ubuntuユーザー所有であることを確認）
cd /opt/morizo/Morizo-aiv2
ls -la

# 手動で起動してエラーを確認（ubuntuユーザーで実行）
cd /opt/morizo/Morizo-aiv2
source venv/bin/activate
python main.py

# 環境変数が正しく設定されているか確認（ubuntuユーザーで実行）
source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('SUPABASE_URL'))"

# ファイルの所有権が間違っている場合の修正
# sudo chown -R ubuntu:ubuntu /opt/morizo/Morizo-aiv2
```

### 6.2 Morizo-webが起動しない

```bash
# エラーログを確認（sudo権限が必要）
sudo journalctl -u morizo-web -n 100

# ファイルの所有権を確認（ubuntuユーザー所有であることを確認）
cd /opt/morizo/Morizo-web
ls -la

# SSL証明書ファイルの読み取り権限を確認
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/

# 手動で起動してエラーを確認（ubuntuユーザーで実行）
cd /opt/morizo/Morizo-web
npm start

# ビルドエラーの確認（ubuntuユーザーで実行）
npm run build

# ファイルの所有権が間違っている場合の修正
# sudo chown -R ubuntu:ubuntu /opt/morizo/Morizo-web
```

### 6.3 SSL証明書の更新

Let's Encryptの証明書は90日で期限切れになるため、自動更新を設定：

```bash
# Certbotの自動更新テスト
sudo certbot renew --dry-run

# systemdタイマーの設定（通常は自動設定済み）
sudo systemctl status certbot.timer
```

### 6.4 ポートが既に使用されている

```bash
# ポートの使用状況を確認
sudo lsof -i :443
sudo lsof -i :8000

# プロセスを停止
sudo systemctl stop <サービス名>
```

### 6.5 ベクトルDBが見つからない

```bash
# ベクトルDBディレクトリの存在確認
ls -la /opt/morizo/Morizo-aiv2/recipe_vector_db_*

# 環境変数のパスを確認
cd /opt/morizo/Morizo-aiv2
source venv/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('MAIN:', os.getenv('CHROMA_PERSIST_DIRECTORY_MAIN')); print('SUB:', os.getenv('CHROMA_PERSIST_DIRECTORY_SUB')); print('SOUP:', os.getenv('CHROMA_PERSIST_DIRECTORY_SOUP'))"
```

---

## 7. ログ管理

### 7.1 Morizo-aiv2のログ

- **ログファイル**: `/opt/morizo/Morizo-aiv2/morizo_ai.log`
- **systemdログ**: `sudo journalctl -u morizo-aiv2`

```bash
# ログファイルの確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai.log

# systemdログの確認
sudo journalctl -u morizo-aiv2 -f

# ログローテーション設定（後で実装）
# /etc/logrotate.d/morizo-aiv2 を作成予定
```

### 7.2 Morizo-webのログ

- **systemdログ**: `sudo journalctl -u morizo-web`

```bash
# ログの確認
sudo journalctl -u morizo-web -f

# 最新の100行を表示
sudo journalctl -u morizo-web -n 100
```

---

## 8. バックアップ手順

### 8.1 ベクトルDBのバックアップ

```bash
# バックアップディレクトリの作成（ubuntuユーザーで実行）
mkdir -p ~/backups/morizo-aiv2

# ベクトルDBのバックアップ（ubuntuユーザーで実行）
tar -czf ~/backups/morizo-aiv2/vector_db_$(date +%Y%m%d_%H%M%S).tar.gz \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_main \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_sub \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_soup

# バックアップファイルの所有権を確認
ls -lh ~/backups/morizo-aiv2/

# ローカルにダウンロード（scpを使用）
# scp ubuntu@ec2-instance:~/backups/morizo-aiv2/vector_db_*.tar.gz ./
```

### 8.2 環境変数ファイルのバックアップ

```bash
# 環境変数ファイルのバックアップ（ubuntuユーザーで実行、暗号化して保存）
tar -czf ~/backups/morizo-aiv2/env_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    /opt/morizo/Morizo-aiv2/.env \
    /opt/morizo/Morizo-web/.env.local

# バックアップファイルの所有権を確認（ubuntuユーザー所有であることを確認）
ls -lh ~/backups/morizo-aiv2/env_backup_*.tar.gz

# バックアップファイルの権限を制限（他のユーザーが読み取れないように）
chmod 600 ~/backups/morizo-aiv2/env_backup_*.tar.gz
```

**重要**: 
- 環境変数ファイルには機密情報が含まれるため、安全に保管してください。
- バックアップファイルも適切な権限で保護してください。

---

## 9. 更新・デプロイ手順

### 9.1 Morizo-aiv2の更新

```bash
# サービスを停止（sudo権限が必要）
sudo systemctl stop morizo-aiv2

# リポジトリの更新（ubuntuユーザーで実行）
cd /opt/morizo/Morizo-aiv2
git pull

# 依存関係の更新（必要に応じて、ubuntuユーザーで実行）
source venv/bin/activate
pip install -r requirements.txt

# サービスを再起動（sudo権限が必要）
sudo systemctl start morizo-aiv2

# 状態確認（sudo権限が必要）
sudo systemctl status morizo-aiv2

# ファイルの所有権を確認（ubuntuユーザー所有であることを確認）
ls -la
```

### 9.2 Morizo-webの更新

```bash
# サービスを停止（sudo権限が必要）
sudo systemctl stop morizo-web

# リポジトリの更新（ubuntuユーザーで実行）
cd /opt/morizo/Morizo-web
git pull

# 依存関係の更新（必要に応じて、ubuntuユーザーで実行）
npm install

# 本番ビルド（ubuntuユーザーで実行）
npm run build

# サービスを再起動（sudo権限が必要）
sudo systemctl start morizo-web

# 状態確認（sudo権限が必要）
sudo systemctl status morizo-web

# ファイルの所有権を確認（ubuntuユーザー所有であることを確認）
ls -la
```

---

## 10. セキュリティチェックリスト

- [ ] SSL証明書が正しく設定されている
- [ ] 環境変数ファイルに機密情報が含まれている（`.gitignore`で除外されていることを確認）
- [ ] 環境変数ファイルの権限が適切に設定されている（`chmod 600`）
- [ ] セキュリティグループで必要最小限のポートのみ開放（443のみ）
- [ ] システムパッケージが最新の状態である
- [ ] ログファイルに機密情報が出力されていない
- [ ] ベクトルDBディレクトリのアクセス権限が適切に設定されている
- [ ] `/opt/morizo`配下のファイル・ディレクトリが`ubuntu`ユーザー所有であることを確認
- [ ] systemdサービスが`ubuntu`ユーザーで実行されていることを確認
- [ ] rootユーザーでの作業を行っていないことを確認
- [ ] SSL証明書ファイルの読み取り権限が適切に設定されている

---

## 11. 今後の改善項目

以下の項目は後日実装予定：

1. **ログローテーション設定**
   - logrotateを使用したログファイルの自動ローテーション
   - ログの自動削除設定

2. **モニタリング設定**
   - CloudWatchやその他のモニタリングツールの導入
   - メトリクスの収集

3. **アラート設定**
   - 異常検知時の通知方法
   - メール/Slack通知の設定

4. **CI/CDパイプライン**
   - GitHub Actions等を使用した自動デプロイ
   - テストの自動実行

5. **バックアップ自動化**
   - 定期的なバックアップスクリプトの作成
   - S3等への自動バックアップ

6. **nginxリバースプロキシの導入**
   - Next.jsの前にnginxを配置してパフォーマンス向上
   - 静的ファイル配信の最適化
   - SSL/TLS処理の効率化
   - 複数アプリケーションの統合管理（Next.js + FastAPI）
   - セキュリティ強化（DDoS対策、レート制限など）
   - 詳細なアクセスログ・エラーログの取得

7. **水平スケーリング対応**
   - 複数のNext.jsインスタンスへの負荷分散
   - 複数のFastAPIインスタンスへの負荷分散
   - ロードバランサー（nginx/ALB）の設定
   - セッション管理の対応（Sticky Sessionなど）

8. **垂直スケーリング対応**
   - EC2インスタンスタイプのアップグレード計画
   - リソース監視に基づくスケールアップ判断基準
   - メモリ・CPU使用率の閾値設定

9. **マルチインスタンス構成**
   - 複数EC2インスタンスへの分散デプロイ
   - 共有ストレージ（EFS等）の検討
   - ベクトルDBの共有化または分散配置
   - データベース接続プールの最適化

10. **オートスケーリング設定**
    - CloudWatchベースの自動スケーリング
    - トラフィックに応じたインスタンス数の自動調整
    - コスト最適化のためのスケールダウンポリシー

---

## 12. 関連ドキュメント

- [環境変数設定ガイド](../ENVIRONMENT_SETUP.md)
- [README](../README.md)

---

## 更新履歴

- 2024-XX-XX: 初版作成

---
補足説明

## Let's Encryptとは

Let's Encryptは、**無料のSSL/TLS証明書を発行する認証局（CA）**です。2015年にInternet Security Research Group (ISRG)が設立した非営利組織が運営しています。

### 主な特徴

1. **無料**
   - 有効期間は90日（自動更新可能）

2. **自動化**
   - Certbotなどのツールで自動取得・更新が可能

3. **広く利用されている**
   - ブラウザで認識され、多くのWebサイトで使用

### SSL/TLS証明書とは

HTTPS通信に必要な証明書で、以下を実現します：
- 通信の暗号化（第三者による盗聴を防止）
- サイトの身元証明（なりすましを防止）
- ブラウザでの警告を抑制

### Let's Encryptを使うメリット

1. 費用がかからない
2. 自動更新できる（Certbotで設定）
3. ブラウザ互換性が高い
4. セットアップが容易

### 本番環境での使用

本番移行計画書では、以下の理由でLet's Encryptを使用しています：
- 無料で運用できる
- Certbotで自動発行・更新が可能
- HTTPS通信を実現できる
- 本番環境でも問題なく使用できる

### 注意点

1. 証明書の有効期間は90日
   - 自動更新を設定することが推奨
2. ドメイン所有権の確認が必要
   - 対象ドメイン（morizo.csngrp.co.jp）がEC2のIPに正しく向いている必要がある
3. ポート80の一時開放が必要な場合がある
   - 初回取得時にHTTP-01チャレンジで使用

本番移行計画書の「2.4 SSL証明書の取得（Let's Encrypt）」セクションで、Certbotを使用した取得手順を記載しています。
