# 本番環境移行計画書

## 概要

Morizo-web と Morizo-aiv2 を GCP VM (Ubuntu 24.04 LTS) 上にデプロイするための本番移行計画書です。

### 対象環境
- **本番環境**: GCP VM (Ubuntu 24.04 LTS, e2-micro)
- **ドメイン**: morizo.csngrp.co.jp
- **Supabase**: 開発環境と同じプロジェクトを使用
- **デプロイ方法**: 手動デプロイ（初期）

### 前提条件
- GCP VMインスタンスが起動済み
- ドメインがGCP VMインスタンスに紐付け済み
- SSH接続が可能
- 各リポジトリへのアクセス権限があること

### 作業ユーザー

**重要**: この手順書は、rootユーザーではなく、**通常のユーザー（`sasaki`）**で作業することを想定しています。

- **デフォルトユーザー**: `sasaki`（GCP VMの作業ユーザー）
- **必要な権限**: sudo権限（パッケージインストール、systemd設定など）
- **セキュリティ**: rootユーザーでの作業は避け、必要な場合のみ`sudo`を使用します

各コマンドの説明：
- `sudo`なしのコマンド → `sasaki`ユーザーで直接実行
- `sudo`付きのコマンド → 管理者権限が必要な操作

**現在のユーザー確認**:
```bash
# 現在のユーザーを確認
whoami

# sasakiユーザーであることを確認（他のユーザーの場合は適宜読み替えてください）
```

---

## 1. インフラ構成

### 1.1 GCP VMインスタンス仕様
- **マシンタイプ**: e2-micro
- **OS**: Ubuntu 24.04 LTS
- **ストレージ**: 20GB 標準永続ディスク（ベクトルDBデータ用）
- **メモリ**: 1GB（共有メモリ: 958MB利用可能）

**メモリ要件について**:
- **e2-microのメモリ制約**: 1GBのメモリは、Morizo-aiv2（FastAPI + ChromaDB + LangChain）とMorizo-web（Next.js）を同時に実行するには**非常に厳しい**状況です
- **推奨メモリ構成**:
  - **最低限**: 2GB（スワップ必須）
  - **推奨**: 4GB以上
  - **理想**: 8GB以上（本番環境での安定運用）
- **現在の構成での対策**:
  - スワップ領域（2-4GB）の設定が**必須**です（セクション2.5参照）
  - メモリ使用量の監視と最適化が必要です
  - 可能であれば、e2-small（2GB）またはe2-medium（4GB）へのアップグレードを検討してください

### 1.2 ネットワーク構成
```
インターネット
    ↓
GCP ファイアウォールルール (ポート443のみ開放)
    ↓
Ubuntu 24.04 LTS
    ├── nginx (リバースプロキシ) - ポート443で公開（SSL/TLS終端）
    │   ├── Morizo-web (Next.js) - ポート3000（HTTP、localhostのみ）
    │   └── Morizo-aiv2 (FastAPI) - ポート8000（localhostのみ）
    └── Morizo-aiv2 (FastAPI) - ポート8000（localhostのみ）
```

### 1.3 ポート設定
- **外部公開ポート**: 443 (HTTPS)
- **nginx**: 443ポートでリスニング（SSL/TLS終端、リバースプロキシ）
- **Morizo-web**: 3000ポート（HTTP、localhost:3000、nginxからのみアクセス）
- **Morizo-aiv2**: 8000ポート（localhost:8000、Morizo-webからのみアクセス）

### 1.4 ファイアウォールルール設定
GCPのファイアウォールルールで以下を設定：
- **インバウンドルール**:
  - タイプ: HTTPS
  - ポート: 443
  - ソース: 0.0.0.0/0（必要に応じて制限）
- **アウトバウンドルール**: すべて許可（デフォルト）

---

## 2. 初期セットアップ（GCP VM環境構築）

**作業ユーザー**: `sasaki`ユーザーで作業を開始してください。

### 2.0 実行ユーザー権限の分離（セキュリティ強化）

**重要**: セキュリティ強化のため、アプリケーション実行専用の低権限ユーザー（`appuser`）を作成し、アプリケーションをこのユーザーで実行します。これにより、万が一アプリケーションが侵害されても、システム全体への影響を最小限に抑えることができます。

#### 2.0.1 低権限ユーザーの作成

```bash
# アプリケーション実行用の低権限ユーザーを作成（ホームディレクトリなし、ログインシェルなし）
sudo useradd -r -s /bin/false appuser

# ユーザーが作成されたことを確認
id appuser
```

**注意**:
- `-r`オプション: システムユーザーとして作成（UID < 1000）
- `-s /bin/false`オプション: ログインシェルを無効化（セキュリティ向上）

---

### 2.1 システムパッケージのインストール

```bash
# システムの更新（sudo権限が必要）
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール（sudo権限が必要）
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    nodejs \
    npm \
    git \
    curl \
    build-essential \
    certbot \
    openssl \
    nginx \
    vim
```

### 2.2 Node.jsのバージョン確認・アップグレード

```bash
# Node.jsバージョン確認（通常ユーザーで実行）
node -v

# Node.js 22をインストール（sudo権限が必要）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# インストール後のバージョン確認（通常ユーザーで実行）
node -v
npm -v
```

**注意**: 
- 既にNode.jsがインストールされている場合、上記コマンドでアップグレードされます
- Node.js 22はLTS（Long Term Support）バージョンです

### 2.3 Python環境の確認

```bash
# Python 3.12がインストールされていることを確認（通常ユーザーで実行）
python3.12 --version
```

**注意**: Ubuntu 24.04 LTSでは、PEP 668によりシステム全体のPython環境での`pip`インストールが制限されています。pipのアップグレードは、後述の仮想環境内で行います（セクション3.2参照）。

### 2.4 SSL証明書の取得（Let's Encrypt）

**重要**: nginxが既にインストール・起動している場合、ポート80が使用されているため、`--standalone`モードは使用できません。以下のいずれかの方法を使用してください。

#### 方法1: nginxを一時停止して証明書を取得（初回取得時）

```bash
# nginxが起動しているか確認（sudo権限が必要）
sudo systemctl status nginx

# nginxを一時停止（sudo権限が必要）
sudo systemctl stop nginx

# Certbotを使用してSSL証明書を取得（sudo権限が必要）
sudo certbot certonly --standalone -d morizo.csngrp.co.jp

# nginxを再起動（sudo権限が必要）
sudo systemctl start nginx

# 証明書の場所を確認（通常は以下）
# /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem
# /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem

# 証明書の読み取り権限を確認（sasakiユーザーが読み取れることを確認）
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/
```

#### 方法2: webrootプラグインを使用（nginxを起動したまま証明書を取得・更新）

**推奨**: nginxを起動したまま証明書を取得・更新できるため、この方法を推奨します。

```bash
# webroot用のディレクトリを作成（sudo権限が必要）
sudo mkdir -p /var/www/html

# Certbotを使用してSSL証明書を取得（webrootプラグイン、sudo権限が必要）
sudo certbot certonly --webroot -w /var/www/html -d morizo.csngrp.co.jp

# 証明書の場所を確認（通常は以下）
# /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem
# /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem

# 証明書の読み取り権限を確認（sasakiユーザーが読み取れることを確認）
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/
```

**注意**: 
- SSL証明書の取得には、ドメインがGCP VMのパブリックIPに正しく向いている必要があります。
- 証明書ファイルはroot所有ですが、nginxが読み取れるように、適切な権限設定が必要です（nginxは通常、rootまたはwww-dataユーザーで実行されるため、通常は問題ありません）。
- **方法2（webroot）を使用する場合**: nginx設定ファイル（セクション4.5.2）で、`/.well-known/acme-challenge/`のlocationが既に設定されていることを確認してください。
- **下りポート（アウトバウンド）を閉じている場合**: 証明書の更新時にLet's Encryptのサーバーと通信する必要があるため、HTTPS（ポート443）のアウトバウンド通信が許可されている必要があります。

### 2.4.1 SSL証明書の読み取り権限設定（appuser用）

**作業ユーザー**: `sasaki`ユーザーで作業します。

**重要**: この手順は、セクション2.4でSSL証明書を取得した**後**に実行してください。

Morizo-webがSSL証明書を読み取れるように、`ssl-cert`グループを作成し、`appuser`を追加します。これが最も確実で安全な方法です。

```bash
# ssl-certグループが存在するか確認
getent group ssl-cert

# グループが存在しない場合は作成（sudo権限が必要）
if ! getent group ssl-cert > /dev/null 2>&1; then
  sudo groupadd ssl-cert
  echo "ssl-certグループを作成しました"
else
  echo "ssl-certグループは既に存在します"
fi

# appuserをssl-certグループに追加（sudo権限が必要）
sudo usermod -aG ssl-cert appuser

# グループの追加を確認
groups appuser
# 出力に "ssl-cert" が含まれていることを確認

# 証明書ディレクトリのグループ所有権をssl-certに変更（sudo権限が必要）
# 注意: Let's Encryptはシンボリックリンクを使用するため、親ディレクトリと実ファイルの両方に権限が必要

# /etc/letsencrypt/live/ディレクトリの権限とグループ所有権を設定（sudo権限が必要）
sudo chmod 755 /etc/letsencrypt/live/
sudo chgrp ssl-cert /etc/letsencrypt/live/

# /etc/letsencrypt/live/morizo.csngrp.co.jp/ディレクトリの権限とグループ所有権を設定（sudo権限が必要）
sudo chmod 755 /etc/letsencrypt/live/morizo.csngrp.co.jp/
sudo chgrp ssl-cert /etc/letsencrypt/live/morizo.csngrp.co.jp/

# 親ディレクトリ（archive）の権限を変更（sudo権限が必要）
# archiveディレクトリはデフォルトで700（drwx------）のため、755に変更が必要
sudo chmod 755 /etc/letsencrypt/archive/
sudo chgrp ssl-cert /etc/letsencrypt/archive/

# ドメイン配下のディレクトリのグループ所有権を変更（sudo権限が必要）
sudo chmod 755 /etc/letsencrypt/archive/morizo.csngrp.co.jp/
sudo chgrp ssl-cert /etc/letsencrypt/archive/morizo.csngrp.co.jp/

# 実ファイルのグループ所有権をssl-certに変更（sudo権限が必要）
sudo chgrp ssl-cert /etc/letsencrypt/archive/morizo.csngrp.co.jp/*.pem

# 実ファイルの権限を設定（グループ読み取り可能に）（sudo権限が必要）
sudo chmod 640 /etc/letsencrypt/archive/morizo.csngrp.co.jp/fullchain*.pem
sudo chmod 640 /etc/letsencrypt/archive/morizo.csngrp.co.jp/privkey*.pem
sudo chmod 640 /etc/letsencrypt/archive/morizo.csngrp.co.jp/cert*.pem
sudo chmod 640 /etc/letsencrypt/archive/morizo.csngrp.co.jp/chain*.pem

# appuserが証明書ファイルを読み取れることを確認
sudo -u appuser cat /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem > /dev/null && echo "証明書読み取りOK" || echo "証明書読み取りNG"
```

**注意**:
- `ssl-cert`グループを作成し、証明書ファイルのグループ所有権を`ssl-cert`に変更することで、`appuser`が証明書を読み取れるようになります
- この方法により、証明書ファイルの所有者（root）は変更せず、グループ権限のみでアクセスを許可します
- **重要**: Let's Encryptはシンボリックリンクを使用します：
  - `/etc/letsencrypt/live/` → シンボリックリンク（例: `fullchain.pem` → `../../archive/morizo.csngrp.co.jp/fullchain1.pem`）
  - `/etc/letsencrypt/archive/` → 実ファイルが保存される場所
  - シンボリックリンクをたどるには、親ディレクトリ（`archive`）に実行権限（`755`）が必要です
  - デフォルトでは`archive`ディレクトリが`700`（`drwx------`）のため、`755`に変更する必要があります
- グループの変更を反映するには、サービスを再起動する必要がある場合があります（セクション4.7参照）

**代替方法（ssl-certグループが利用できない場合）**:

もし`ssl-cert`グループが存在しない、または上記の方法で解決しない場合は、以下の方法を試してください：

```bash
# SSL証明書ディレクトリの読み取り権限を設定（sudo権限が必要）
# 注意: セキュリティ上の理由から、最小限の権限で設定してください
sudo chmod 755 /etc/letsencrypt/live/
sudo chmod 755 /etc/letsencrypt/live/morizo.csngrp.co.jp/
sudo chmod 644 /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem
sudo chmod 600 /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem

# appuserが証明書ファイルを読み取れることを確認
sudo -u appuser cat /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem > /dev/null && echo "証明書読み取りOK" || echo "証明書読み取りNG"
```

**トラブルシューティング**:
- 「証明書読み取りNG」と表示される場合：
  1. 証明書ファイルが存在することを確認: `sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/`
  2. `ssl-cert`グループが存在することを確認: `getent group ssl-cert`
  3. グループの変更を反映するため、サービスを再起動: `sudo systemctl restart morizo-web`（セクション4.7参照）
  4. それでも解決しない場合は、上記の代替方法（chmod）を試す

### 2.5 スワップ領域の設定（必須）

**重要**: e2-micro（1GBメモリ）では、Morizo-aiv2とMorizo-webを同時に実行するにはメモリが不足する可能性が高いため、スワップ領域の設定が**必須**です。

```bash
# スワップファイルの作成（2GB、sudo権限が必要）
sudo fallocate -l 2G /swapfile

# スワップファイルのパーミッション設定（sudo権限が必要）
sudo chmod 600 /swapfile

# スワップ領域としてフォーマット（sudo権限が必要）
sudo mkswap /swapfile

# スワップ領域を有効化（sudo権限が必要）
sudo swapon /swapfile

# スワップの確認（通常ユーザーで実行）
free -h

# 永続化のため、/etc/fstabに追加（sudo権限が必要）
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# スワップの優先度を設定（オプション、sudo権限が必要）
# メモリ不足時にスワップを優先的に使用する設定
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**注意**:
- スワップはディスクI/Oを使用するため、パフォーマンスに影響があります
- 2GBのスワップで足りない場合は、4GBに増やすことを検討してください
- 可能であれば、e2-small（2GB）またはe2-medium（4GB）へのアップグレードを推奨します

### 2.6 タイムゾーンの設定（日本時間JST）

**重要**: デフォルトではシステムのタイムゾーンがUTC（グリニッジ標準時）に設定されているため、ログの時刻がUTCで表示されます。日本時間（JST）で表示するために、システムのタイムゾーンをJSTに変更します。

```bash
# 現在のタイムゾーンを確認（通常ユーザーで実行）
timedatectl

# タイムゾーンを日本時間（JST）に変更（sudo権限が必要）
sudo timedatectl set-timezone Asia/Tokyo

# 変更後の確認（通常ユーザーで実行）
timedatectl
date
```

**注意**:
- タイムゾーンを変更すると、システム全体の時刻表示がJSTになります
- アプリケーションのログもJSTで表示されるようになります（後述のログ設定により）

---

## 3. Morizo-aiv2 デプロイ手順

**作業ユーザー**: `sasaki`ユーザーで作業します。

### 3.1 リポジトリのクローン

```bash
# デプロイ用ディレクトリの作成（sudo権限が必要）
sudo mkdir -p /opt/morizo

# リポジトリをクローンするために、一時的にsasakiユーザーに所有権を変更（sudo権限が必要）
# 注意: セットアップ完了後、セクション4.8で`/opt/morizo`の所有権を`appuser`に変更します
sudo chown sasaki:sasaki /opt/morizo

# ディレクトリに移動
cd /opt/morizo

# 現在のユーザーを確認（sasakiであることを確認）
whoami

# Morizo-aiv2リポジトリのクローン（通常ユーザーで実行）
git clone <Morizo-aiv2のリポジトリURL> Morizo-aiv2
cd Morizo-aiv2

# ディレクトリの所有権を確認
ls -la
```

**注意**: セットアップ作業（依存関係のインストール、環境変数の設定など）は`sasaki`ユーザーで行います。所有権を`appuser`に変更するのは、セクション4.8で行います。

### 3.2 Python仮想環境の作成と依存関係のインストール

```bash
# 仮想環境の作成（通常ユーザーで実行）
python3.12 -m venv venv

# 仮想環境のアクティベート
source venv/bin/activate

# 依存関係のインストール
pip install --upgrade pip

# メモリ使用量を抑えるため、requirements.txtを3つに分割してインストール
# 1. 基本パッケージ（FastAPI、uvicorn、基本的な依存関係）
pip install -r requirements_base.txt

# 2. AI/ML関連パッケージ（LangChain、OpenAI、ChromaDB）
pip install -r requirements_ai.txt

# 3. 重いパッケージ（pandas、numpy、spacy、nltk）
pip install -r requirements_heavy.txt

# または、一括インストール（メモリに余裕がある場合）
# pip install -r requirements.txt

# 仮想環境の所有権を確認（appuserユーザー所有であることを確認）
ls -la venv/
```

### 3.3 環境変数の設定

```bash
# .envファイルの作成（通常ユーザーで実行）
cp env.example .env

# .envファイルを編集
vi .env

# .envファイルの所有権と権限を確認（sasakiユーザー所有、読み取り専用）
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

# ディレクトリの所有権を確認（appuserユーザー所有であることを確認）
ls -ld recipe_vector_db_*

# 既存のベクトルDBデータがある場合、それらをコピー
# scp -r recipe_vector_db_* sasaki@gcp-vm-instance:/opt/morizo/Morizo-aiv2/
```

### 3.5 systemdサービスファイルの作成

```bash
# systemdサービスファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-aiv2.service
```

**重要**: systemdサービスは`appuser`ユーザーで実行されるため、`/opt/morizo/Morizo-aiv2`ディレクトリとその配下のファイルは`appuser`ユーザーが読み書きできる必要があります（セクション4.8参照）。

以下を記述：

```ini
[Unit]
Description=Morizo AI v2 FastAPI Application
After=network.target

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/morizo/Morizo-aiv2
Environment="PATH=/opt/morizo/Morizo-aiv2/venv/bin"
ExecStart=/opt/morizo/Morizo-aiv2/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

# セキュリティ設定
PrivateTmp=true

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-aiv2

[Install]
WantedBy=multi-user.target
```

**セキュリティ設定の説明**:
- `User=appuser`: アプリケーションを低権限ユーザーで実行
- `Group=appuser`: アプリケーションを低権限グループで実行
- `PrivateTmp=true`: サービス専用の`/tmp`ディレクトリを使用し、他のプロセスから隔離（セキュリティ向上）

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

# プロセスの所有者を確認（appuserユーザーで実行されていることを確認）
ps aux | grep uvicorn | grep -v grep
# または
ps -ef | grep uvicorn | grep -v grep
# 出力例: appuser 12345 ... uvicorn main:app ...
```

---

## 4. Morizo-web デプロイ手順

**作業ユーザー**: `sasaki`ユーザーで作業します。

### 4.1 リポジトリのクローン

```bash
# /opt/morizoディレクトリに移動
cd /opt/morizo

# 現在のユーザーを確認（sasakiであることを確認）
whoami

# Morizo-webリポジトリのクローン（通常ユーザーで実行）
git clone <Morizo-webのリポジトリURL> Morizo-web
cd Morizo-web

# ディレクトリの所有権を確認
ls -la
```

**注意**: 
**注意**: 
- セットアップ作業（リポジトリのクローン、依存関係のインストール、ビルドなど）は`sasaki`ユーザーで行います
- 所有権を`appuser`に変更するのは、セクション4.8で行います

### 4.2 依存関係のインストール

```bash
# npmパッケージのインストール（通常ユーザーで実行）
npm install

# node_modulesの所有権を確認（appuserユーザー所有であることを確認）
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

# ログ設定（サーバーサイド用）
LOG_INITIALIZE_BACKUP=true       # 起動時のログファイルバックアップ（true/false）。本番環境でlogrotate使用時はfalse推奨
```

**注意**: 
- Next.jsでは、`NEXT_PUBLIC_`プレフィックスの環境変数のみがクライアント側で利用可能です。
- `LOG_INITIALIZE_BACKUP`はサーバーサイドでのみ使用されます。
  - **開発環境**: `true`（デフォルト）- サーバー起動ごとにアプリでログをバックアップ＆リフレッシュ
  - **本番環境**: `false` - logrotateに任せるため、アプリでは何もしない

### 4.3.1 アプリケーションディレクトリの所有権設定（ビルド前）

**重要**: ビルド（セクション4.4）の**前**に、`/opt/morizo/Morizo-web`の所有権を`appuser`に変更します。これにより、ビルド生成物（`.next`ディレクトリなど）が正しい所有権で作成されます。

```bash
# /opt/morizo/Morizo-webディレクトリの所有権をappuserに変更（sudo権限が必要）
sudo chown -R appuser:appuser /opt/morizo/Morizo-web

# 所有権が正しく設定されたことを確認
ls -ld /opt/morizo/Morizo-web
ls -la /opt/morizo/Morizo-web | head -10
```

### 4.4 本番ビルド

**重要**: ビルドは`appuser`ユーザーで実行します。これにより、ビルド生成物（`.next`ディレクトリ）が正しい所有権で作成されます。セクション4.3.1で所有権を変更済みであることを確認してください。

```bash
# 本番用ビルド（appuserユーザーで実行）
sudo -u appuser bash -c "cd /opt/morizo/Morizo-web && npm run build"

# ビルドが正常に完了したことを確認
ls -la /opt/morizo/Morizo-web/.next/BUILD_ID

# 所有権がappuserであることを確認
ls -ld /opt/morizo/Morizo-web/.next
```

**注意**: 
- ビルド前に、`/opt/morizo/Morizo-web`ディレクトリの所有権が`appuser`であることを確認してください（セクション4.8で設定済みの場合、この手順は不要です）。
- ビルドが失敗する場合は、依存関係が正しくインストールされているか確認してください（セクション4.2参照）。

### 4.5 nginxリバースプロキシの設定

**重要**: セキュリティ強化のため、nginxをリバースプロキシとして導入し、SSL/TLS終端をnginxで行います。これにより、Next.jsアプリケーションはHTTP（localhost）で動作し、特権ポートのバインドが不要になります。

**作業ユーザー**: `sasaki`ユーザーで作業します。

#### 4.5.1 nginxのインストール

```bash
# nginxのインストール（sudo権限が必要）
sudo apt update
sudo apt install -y nginx

# nginxのバージョン確認
nginx -v

# nginxの起動確認（sudo権限が必要）
sudo systemctl status nginx
```

#### 4.5.2 nginx設定ファイルの作成

**重要**: `limit_req_zone`ディレクティブは`http`ブロック内でのみ使用可能です。`server`ブロック内では使用できません。そのため、レート制限の設定を`/etc/nginx/conf.d/`に分離します。

##### 4.5.2.1 レート制限設定ファイルの作成

**重要**: `limit_req_zone`ディレクティブは`http`ブロック内でのみ使用可能です。`/etc/nginx/conf.d/`ディレクトリのファイルは、`/etc/nginx/nginx.conf`の`http`ブロック内で自動的にインクルードされます。

```bash
# conf.dディレクトリが存在するか確認（存在しない場合は作成、sudo権限が必要）
if [ ! -d /etc/nginx/conf.d ]; then
    sudo mkdir -p /etc/nginx/conf.d
fi

# /etc/nginx/nginx.confでconf.dがインクルードされているか確認
sudo grep -q "include /etc/nginx/conf.d/\*.conf;" /etc/nginx/nginx.conf && echo "conf.dは既にインクルードされています" || echo "conf.dのインクルードが必要です"

# レート制限設定ファイルの作成（sudo権限が必要）
sudo vi /etc/nginx/conf.d/rate-limit.conf
```

以下を記述：

```nginx
# レート制限ゾーンの定義（httpブロック内で使用可能）
limit_req_zone $binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=api:10m rate=5r/s;
```

**注意**: 
- `/etc/nginx/nginx.conf`に`include /etc/nginx/conf.d/*.conf;`が含まれていない場合は、`http`ブロック内に追加する必要があります（通常は既に含まれています）。
- 確認方法: `sudo grep "include.*conf.d" /etc/nginx/nginx.conf`

##### 4.5.2.2 メイン設定ファイルの作成

```bash
# nginx設定ファイルの作成（sudo権限が必要）
sudo vi /etc/nginx/sites-available/morizo
```

以下を記述：

```nginx
# リバースプロキシ設定
upstream morizo_web {
    server 127.0.0.1:3000;
    keepalive 64;
}

# HTTPサーバー（HTTPSへのリダイレクト）
server {
    listen 80;
    listen [::]:80;
    server_name morizo.csngrp.co.jp;

    # Let's Encryptの証明書更新用（.well-known/acme-challenge）
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # その他すべてのHTTPリクエストをHTTPSにリダイレクト
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPSサーバー
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name morizo.csngrp.co.jp;

    # SSL証明書の設定
    ssl_certificate /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/morizo.csngrp.co.jp/privkey.pem;

    # SSL/TLS設定（セキュリティ強化）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_session_tickets off;

    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # ログ設定
    access_log /var/log/nginx/morizo-access.log;
    error_log /var/log/nginx/morizo-error.log;

    # クライアントボディサイズの制限（アップロードファイルサイズ制限）
    client_max_body_size 10M;

    # タイムアウト設定
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # 静的ファイルの直接配信（パフォーマンス向上）
    location /_next/static/ {
        alias /opt/morizo/Morizo-web/.next/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # カスタム静的ファイルの直接配信（public/staticディレクトリが存在する場合のみ有効）
    # 注意: このディレクトリが存在しない場合は、このlocationブロックを削除またはコメントアウトしてください
    # location /static/ {
    #     alias /opt/morizo/Morizo-web/public/static/;
    #     expires 1y;
    #     add_header Cache-Control "public, immutable";
    # }

    # APIエンドポイント（レート制限を適用）
    location /api/ {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://morizo_web;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # その他のリクエスト（レート制限を適用）
    location / {
        limit_req zone=general burst=20 nodelay;
        proxy_pass http://morizo_web;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

#### 4.5.3 nginx設定ファイルの有効化

```bash
# シンボリックリンクの作成（sudo権限が必要）
sudo ln -s /etc/nginx/sites-available/morizo /etc/nginx/sites-enabled/

# デフォルト設定の無効化（オプション、sudo権限が必要）
sudo rm /etc/nginx/sites-enabled/default

# nginx設定の構文チェック（sudo権限が必要）
sudo nginx -t

# nginxの再起動（sudo権限が必要）
sudo systemctl restart nginx

# nginxの状態確認（sudo権限が必要）
sudo systemctl status nginx
```

#### 4.5.4 静的ファイルディレクトリの権限設定

```bash
# 静的ファイルディレクトリの読み取り権限を設定（sudo権限が必要）
# nginxが静的ファイルを読み取れるようにする

# .next/staticディレクトリの権限設定（必須）
if [ -d /opt/morizo/Morizo-web/.next/static ]; then
    sudo chmod -R 755 /opt/morizo/Morizo-web/.next/static
    echo ".next/staticディレクトリの権限を設定しました"
else
    echo "警告: .next/staticディレクトリが見つかりません（ビルドが必要かもしれません）"
fi

# public/staticディレクトリの権限設定（オプション、存在する場合のみ）
if [ -d /opt/morizo/Morizo-web/public/static ]; then
    sudo chmod -R 755 /opt/morizo/Morizo-web/public/static
    echo "public/staticディレクトリの権限を設定しました"
else
    echo "情報: public/staticディレクトリは存在しません（オプション）"
fi

# 所有権の確認（appuserユーザー所有であることを確認）
if [ -d /opt/morizo/Morizo-web/.next/static ]; then
    ls -ld /opt/morizo/Morizo-web/.next/static
fi
if [ -d /opt/morizo/Morizo-web/public/static ]; then
    ls -ld /opt/morizo/Morizo-web/public/static
fi
```

**注意**:
- `.next/static`ディレクトリは、Next.jsのビルド後に自動的に作成されます。ビルドが完了していない場合は、セクション4.4でビルドを実行してください。
- `public/static`ディレクトリは、プロジェクトでカスタム静的ファイルを配置する場合に使用されます。存在しない場合は、nginx設定の`location /static/`ブロックを削除するか、コメントアウトしてください（セクション4.5.2.2参照）。
- nginxは`www-data`ユーザーで実行されますが、静的ファイルは`appuser`所有のままでも、読み取り権限（755）があればアクセス可能です
- 必要に応じて、`www-data`ユーザーを`appuser`グループに追加するか、静的ファイルディレクトリのグループ所有権を変更することもできます

#### 4.5.5 Next.jsの起動設定（HTTP、localhost）

**重要**: Next.jsはHTTP（localhost:3000）で起動します。`server.js`ファイルは不要です。

`package.json`の`start`スクリプトを確認：

```json
{
  "scripts": {
    "start": "next start -p 3000"
  }
}
```

**注意**: 
- `next start`コマンドはデフォルトでポート3000を使用しますが、明示的に`-p 3000`を指定します
- 環境変数`PORT=3000`を設定することもできます（セクション4.6参照）

### 4.6 systemdサービスファイルの作成

```bash
# systemdサービスファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-web.service
```

**重要**: systemdサービスは`appuser`ユーザーで実行されるため、`/opt/morizo/Morizo-web`ディレクトリとその配下のファイルは`appuser`ユーザーが読み書きできる必要があります（セクション4.8参照）。nginxがSSL/TLS終端を担当するため、Next.jsはHTTP（localhost:3000）で起動し、SSL証明書ファイルへのアクセスは不要です。

以下を記述：

```ini
[Unit]
Description=Morizo Web Next.js Application
After=network.target

[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/morizo/Morizo-web
Environment="NODE_ENV=production"
Environment="PORT=3000"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

# セキュリティ設定
PrivateTmp=true

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-web

[Install]
WantedBy=multi-user.target
```

**セキュリティ設定の説明**:
- `User=appuser`: アプリケーションを低権限ユーザーで実行
- `Group=appuser`: アプリケーションを低権限グループで実行
- `PrivateTmp=true`: サービス専用の`/tmp`ディレクトリを使用し、他のプロセスから隔離（セキュリティ向上）
- `Environment="PORT=3000"`: Next.jsをポート3000（HTTP）で起動（nginxがリバースプロキシとして接続）
- **注意**: `AmbientCapabilities=CAP_NET_BIND_SERVICE`は不要です。nginxがSSL/TLS終端を担当するため、Next.jsは特権ポートをバインドする必要がありません

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

# プロセスの所有者を確認（appuserユーザーで実行されていることを確認）
ps aux | grep morizo-web
# 出力例: appuser 12345 ... node ... next start ...
```

### 4.8 アプリケーションディレクトリの所有権設定（全体）

**重要**: すべてのセットアップ作業が完了した後、`/opt/morizo`全体の所有権を`appuser`に変更します。これにより、アプリケーションを`appuser`で実行できるようになります。

**注意**: 
- **Morizo-web**: セクション4.3.1で既に所有権を変更済みの場合は、この手順はスキップできます。
- **Morizo-aiv2**: セクション3.4（ベクトルDBの配置）の後に所有権を変更するか、このセクションで一括変更します。

**推奨**: 各アプリケーションの所有権は、ビルドやサービスの起動の**前**に変更することを推奨します（Morizo-web: セクション4.3.1、Morizo-aiv2: セクション3.4の後）。

```bash
# /opt/morizoディレクトリの所有権をappuserに変更（sudo権限が必要）
sudo chown -R appuser:appuser /opt/morizo

# 所有権が正しく設定されたことを確認
ls -ld /opt/morizo
ls -la /opt/morizo

# 各アプリケーションディレクトリの所有権を確認
ls -ld /opt/morizo/Morizo-aiv2
ls -ld /opt/morizo/Morizo-web
```

**注意**: 
- この手順は、セクション3.1〜3.6とセクション4.1〜4.7のすべてのセットアップ作業が完了した後に行います
- 所有権を変更した後は、`appuser`で実行されるsystemdサービスがファイルにアクセスできるようになります
- 所有権を変更した後、サービスを再起動することを推奨します：
  ```bash
  sudo systemctl restart morizo-aiv2
  sudo systemctl restart morizo-web
  ```

---

## 5. 動作確認手順

### 5.1 Morizo-aiv2の動作確認

```bash
# サービスが起動しているか確認（sudo権限が必要）
sudo systemctl status morizo-aiv2

# ローカルでヘルスチェック（通常ユーザーで実行）
curl http://localhost:8000/health

# プロセスの所有者を確認（appuserユーザーで実行されていることを確認）
ps aux | grep uvicorn
# 出力例: appuser 12345 ... uvicorn main:app ...

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

# プロセスの所有者を確認（appuserユーザーで実行されていることを確認）
ps aux | grep node
# 出力例: appuser 12345 ... node ... next start ...

# nginxの状態確認（sudo権限が必要）
sudo systemctl status nginx

# nginxのアクセスログ確認（sudo権限が必要）
sudo tail -f /var/log/nginx/morizo-access.log

# nginxのエラーログ確認（sudo権限が必要）
sudo tail -f /var/log/nginx/morizo-error.log

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

# ファイルの所有権を確認（appuserユーザー所有であることを確認）
cd /opt/morizo/Morizo-aiv2
ls -la

# 手動で起動してエラーを確認（appuserユーザーで実行）
sudo -u appuser bash -c "cd /opt/morizo/Morizo-aiv2 && source venv/bin/activate && python main.py"

# 環境変数が正しく設定されているか確認（appuserユーザーで実行）
sudo -u appuser bash -c "cd /opt/morizo/Morizo-aiv2 && source venv/bin/activate && python -c \"import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('SUPABASE_URL'))\""

# ファイルの所有権が間違っている場合の修正
# sudo chown -R appuser:appuser /opt/morizo/Morizo-aiv2
```

### 6.2 Morizo-webが起動しない

```bash
# エラーログを確認（sudo権限が必要）
sudo journalctl -u morizo-web -n 100

# ファイルの所有権を確認（appuserユーザー所有であることを確認）
cd /opt/morizo/Morizo-web
ls -la

# 手動で起動してエラーを確認（appuserユーザーで実行）
sudo -u appuser bash -c "cd /opt/morizo/Morizo-web && npm start"

# ビルドエラーの確認（appuserユーザーで実行）
sudo -u appuser bash -c "cd /opt/morizo/Morizo-web && npm run build"

# ファイルの所有権が間違っている場合の修正
# sudo chown -R appuser:appuser /opt/morizo/Morizo-web

# Next.jsがポート3000でリスニングしているか確認
sudo netstat -tlnp | grep :3000
# または
sudo ss -tlnp | grep :3000
```

### 6.2.1 nginxが起動しない、またはリバースプロキシが動作しない

```bash
# nginxの状態確認（sudo権限が必要）
sudo systemctl status nginx

# nginxのエラーログを確認（sudo権限が必要）
sudo tail -n 100 /var/log/nginx/morizo-error.log

# nginx設定の構文チェック（sudo権限が必要）
sudo nginx -t

# nginx設定ファイルの確認
sudo cat /etc/nginx/sites-available/morizo

# シンボリックリンクの確認
ls -la /etc/nginx/sites-enabled/morizo

# SSL証明書ファイルの確認（nginxが読み取れることを確認）
sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/
sudo cat /etc/letsencrypt/live/morizo.csngrp.co.jp/fullchain.pem > /dev/null && echo "証明書読み取りOK" || echo "証明書読み取りNG"

# nginxの再起動（sudo権限が必要）
sudo systemctl restart nginx

# Next.jsがポート3000でリスニングしているか確認
sudo netstat -tlnp | grep :3000
# または
sudo ss -tlnp | grep :3000

# nginxからNext.jsへの接続テスト（localhost:3000）
curl -I http://localhost:3000
```

**よくある問題と解決方法**:

1. **nginx設定の構文エラー**:
   - `sudo nginx -t`で構文チェックを実行
   - エラーメッセージに従って修正

2. **SSL証明書が見つからない**:
   - 証明書ファイルのパスを確認: `sudo ls -la /etc/letsencrypt/live/morizo.csngrp.co.jp/`
   - nginx設定ファイルの証明書パスを確認

3. **Next.jsに接続できない（502 Bad Gateway）**:
   - Next.jsが起動しているか確認: `sudo systemctl status morizo-web`
   - Next.jsがポート3000でリスニングしているか確認: `sudo netstat -tlnp | grep :3000`
   - Next.jsのログを確認: `sudo journalctl -u morizo-web -n 50`

4. **静的ファイルが配信されない**:
   - 静的ファイルディレクトリの権限を確認: `ls -ld /opt/morizo/Morizo-web/.next/static`
   - 権限を設定: `sudo chmod -R 755 /opt/morizo/Morizo-web/.next/static`

### 6.3 SSL証明書の更新

Let's Encryptの証明書は90日で期限切れになるため、自動更新を設定：

```bash
# Certbotの自動更新テスト（sudo権限が必要）
sudo certbot renew --dry-run

# systemdタイマーの設定（通常は自動設定済み）
sudo systemctl status certbot.timer

# 手動で証明書を更新（sudo権限が必要）
sudo certbot renew
```

**重要**: 
- **webrootプラグインを使用している場合**: nginxを起動したまま証明書を更新できます（`certbot renew`を実行するだけ）。
- **standaloneモードを使用している場合**: 証明書更新時はnginxを一時停止する必要があります。自動更新の場合は、certbotのフックスクリプトでnginxを停止・起動する設定が必要です。
- **推奨**: webrootプラグインを使用することで、nginxを停止せずに証明書を更新できます（セクション2.4参照）。

**証明書更新後のnginx再読み込み**:

証明書が更新された後、nginxに新しい証明書を読み込ませる必要があります：

```bash
# nginx設定の再読み込み（証明書ファイルの再読み込み、sudo権限が必要）
sudo systemctl reload nginx

# または、nginxの再起動（sudo権限が必要）
sudo systemctl restart nginx
```

**自動更新時のnginx再読み込み設定**:

certbotの更新後に自動的にnginxを再読み込みするように設定：

```bash
# certbotの更新後フックスクリプトの作成（sudo権限が必要）
sudo vi /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

以下を記述：

```bash
#!/bin/bash
systemctl reload nginx
```

```bash
# 実行権限を付与（sudo権限が必要）
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

これにより、証明書が更新された際に自動的にnginxが再読み込みされます。

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

### 7.0 ログ時刻の設定（日本時間JST）

**重要**: システムのタイムゾーンをJSTに設定した後、アプリケーションのログもJSTで表示されるように設定されています。

#### 7.0.1 Morizo-aiv2のログ時刻設定

Morizo-aiv2のログ設定（`config/logging.py`）では、`AlignedFormatter`クラスにJSTタイムゾーンが設定されています。

```python
# config/logging.py内の設定
def jst_time(*args):
    """JST（日本時間）を返すconverter関数（システムのタイムゾーンを使用）"""
    return time.localtime()

class AlignedFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        super().__init__(fmt, datefmt)
        # JSTタイムゾーンを使用するようにconverterを設定
        self.converter = jst_time
        # ...
```

**確認方法**:
```bash
# ログファイルの時刻を確認（JSTで表示される）
tail -n 5 /opt/morizo/Morizo-aiv2/morizo_ai.log
# 出力例: 2025-11-21 16:33:12 - morizo_ai.api.main - INFO - ...
```

#### 7.0.2 Morizo-webのログ時刻設定

Morizo-webのログ設定（`lib/logging.ts`、`lib/client-logging.ts`、`middleware.ts`）では、`getJSTTimestamp()`関数を使用してJST時刻を取得しています。

```typescript
// lib/logging.ts内の設定
private getJSTTimestamp(): string {
  // JST（日本時間）を取得してISO形式で返す
  const now = new Date();
  // Intl.DateTimeFormatを使用してJST時間を取得
  const formatter = new Intl.DateTimeFormat('ja-JP', {
    timeZone: 'Asia/Tokyo',
    // ...
  });
  // ...
}
```

**確認方法**:
```bash
# ログファイルの時刻を確認（JSTで表示される）
tail -n 5 /opt/morizo/Morizo-web/logs/morizo_web.log
# 出力例: 2025-11-21T16:40:51.035+09:00 - MAIN - INFO - ...
```

**注意**:
- システムのタイムゾーンがJSTに設定されている必要があります（セクション2.6参照）
- アプリケーションのコードは既にJST対応済みです
- 新しい環境に構築する場合は、システムのタイムゾーン設定（セクション2.6）を必ず実行してください

### 7.1 Morizo-aiv2のログ

- **ログファイル**: `/opt/morizo/Morizo-aiv2/morizo_ai.log`
- **エラーログファイル**: `/opt/morizo/Morizo-aiv2/morizo_ai_error.log`
- **systemdログ**: `sudo journalctl -u morizo-aiv2`
- **ログ時刻**: JST（日本時間）で表示されます

```bash
# ログファイルの確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai.log

# エラーログファイルの確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai_error.log

# systemdログの確認
sudo journalctl -u morizo-aiv2 -f

# ログローテーション設定（セクション7.3.1参照）
# /etc/logrotate.d/morizo-aiv2 が設定済み
```

### 7.2 Morizo-webのログ

- **ログファイル**: `/opt/morizo/Morizo-web/logs/morizo_web.log`
- **systemdログ**: `sudo journalctl -u morizo-web`
- **ログ時刻**: JST（日本時間）で表示されます（ISO形式: `YYYY-MM-DDTHH:mm:ss.sss+09:00`）

```bash
# ログファイルの確認
tail -f /opt/morizo/Morizo-web/logs/morizo_web.log

# systemdログの確認
sudo journalctl -u morizo-web -f

# 最新の100行を表示
sudo journalctl -u morizo-web -n 100
```

### 7.3 ログローテーション設定

#### 7.3.1 Morizo-aiv2のログローテーション設定

**OSレベルのlogrotate設定**:

```bash
# logrotate設定ファイルの作成（sudo権限が必要）
sudo vi /etc/logrotate.d/morizo-aiv2
```

以下を記述：

```
# Morizo AI v2 ログローテーション設定
/opt/morizo/Morizo-aiv2/morizo_ai*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 appuser appuser
    postrotate
        systemctl reload morizo-aiv2 > /dev/null 2>&1 || true
    endscript
}
```

設定内容：
- **ローテーション頻度**: 日次（daily）
- **保持期間**: 30日間
- **圧縮**: 有効（delaycompress）
- **対象ファイル**: `/opt/morizo/Morizo-aiv2/morizo_ai*.log`
- **所有者**: `appuser`ユーザー

**設定の確認**:

```bash
# logrotate設定ファイルの確認（sudo権限が必要）
cat /etc/logrotate.d/morizo-aiv2

# logrotate設定のテスト（sudo権限が必要）
sudo logrotate -d /etc/logrotate.d/morizo-aiv2

# logrotate設定の強制実行（テスト用、sudo権限が必要）
sudo logrotate -f /etc/logrotate.d/morizo-aiv2
```

**アプリケーションレベルの設定**:

環境変数で制御可能：
- `LOG_USE_PYTHON_ROTATION`: Pythonのローテーション使用（true/false）
  - **開発環境**: `true`（デフォルト）- PythonのRotatingFileHandlerを使用
  - **本番環境**: `false` - logrotateを使用するため、Pythonローテーションを無効化
- `LOG_INITIALIZE_BACKUP`: 起動時のログファイルバックアップ（true/false）
  - **開発環境**: `true`（デフォルト）- サーバー起動ごとにアプリでログをバックアップ＆リフレッシュ
  - **本番環境**: `false` - logrotateに任せるため、アプリでは何もしない

**本番環境での推奨設定**（`.env`ファイル）:
```bash
LOG_USE_PYTHON_ROTATION=false
LOG_INITIALIZE_BACKUP=false
```

#### 7.3.2 Morizo-webのログローテーション設定

**OSレベルのlogrotate設定**:

```bash
# logrotate設定ファイルの作成（sudo権限が必要）
sudo vi /etc/logrotate.d/morizo-web
```

以下を記述：

```
# Morizo Web ログローテーション設定
/opt/morizo/Morizo-web/logs/morizo_web*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 appuser appuser
    postrotate
        systemctl reload morizo-web > /dev/null 2>&1 || true
    endscript
}
```

設定内容：
- **ローテーション頻度**: 日次（daily）
- **保持期間**: 30日間
- **圧縮**: 有効（delaycompress）
- **対象ファイル**: `/opt/morizo/Morizo-web/logs/morizo_web*.log`
- **所有者**: `appuser`ユーザー

**アプリケーションレベルの設定**:

環境変数で制御可能：
- `LOG_INITIALIZE_BACKUP`: 起動時のログファイルバックアップ（true/false）
  - **開発環境**: `true`（デフォルト）- サーバー起動ごとにアプリでログをバックアップ＆リフレッシュ
  - **本番環境**: `false` - logrotateに任せるため、アプリでは何もしない

**本番環境での推奨設定**（`.env.local`ファイル）:
```bash
LOG_INITIALIZE_BACKUP=false
```

**設定の確認**:

```bash
# logrotate設定のテスト（sudo権限が必要）
sudo logrotate -d /etc/logrotate.d/morizo-web

# logrotate設定の強制実行（テスト用、sudo権限が必要）
sudo logrotate -f /etc/logrotate.d/morizo-web
```

**注意**:
- 本番環境では、OSレベルのlogrotateを使用することを推奨します
- アプリケーション側のログローテーション（起動時バックアップ）は、`LOG_INITIALIZE_BACKUP=false`で無効化してください
- 開発環境では、`LOG_INITIALIZE_BACKUP=true`（デフォルト）で、サーバー起動ごとにログをリフレッシュできます

---

## 8. バックアップ手順

### 8.1 ベクトルDBのバックアップ

```bash
# バックアップディレクトリの作成（sasakiユーザーで実行）
mkdir -p ~/backups/morizo-aiv2

# ベクトルDBのバックアップ（sasakiユーザーで実行）
tar -czf ~/backups/morizo-aiv2/vector_db_$(date +%Y%m%d_%H%M%S).tar.gz \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_main \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_sub \
    /opt/morizo/Morizo-aiv2/recipe_vector_db_soup

# バックアップファイルの所有権を確認
ls -lh ~/backups/morizo-aiv2/

# ローカルにダウンロード（scpを使用）
# scp sasaki@gcp-vm-instance:~/backups/morizo-aiv2/vector_db_*.tar.gz ./
```

### 8.2 環境変数ファイルのバックアップ

```bash
# 環境変数ファイルのバックアップ（sasakiユーザーで実行、暗号化して保存）
tar -czf ~/backups/morizo-aiv2/env_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    /opt/morizo/Morizo-aiv2/.env \
    /opt/morizo/Morizo-web/.env.local

# バックアップファイルの所有権を確認（sasakiユーザー所有であることを確認）
ls -lh ~/backups/morizo-aiv2/env_backup_*.tar.gz

# バックアップファイルの権限を制限（他のユーザーが読み取れないように）
chmod 600 ~/backups/morizo-aiv2/env_backup_*.tar.gz
```

**重要**: 
- 環境変数ファイルには機密情報が含まれるため、安全に保管してください。
- バックアップファイルも適切な権限で保護してください。

---

## 9. 更新・デプロイ手順

**重要**: 更新作業は`sasaki`ユーザーで行います。更新作業前に所有権を一時的に`sasaki`に変更し、作業完了後に`appuser`に戻します。これはセキュリティの観点から必要な作業です。

### 9.1 Morizo-aiv2の更新

```bash
# サービスを停止（sudo権限が必要）
sudo systemctl stop morizo-aiv2

# 所有権を一時的にsasakiに変更（更新作業のため、sudo権限が必要）
sudo chown -R sasaki:sasaki /opt/morizo/Morizo-aiv2

# リポジトリの更新（sasakiユーザーで実行）
cd /opt/morizo/Morizo-aiv2
git pull

# 依存関係の更新（必要に応じて、sasakiユーザーで実行）
source venv/bin/activate
# メモリ使用量を抑えるため、分割されたrequirementsファイルを使用
pip install -r requirements_base.txt
pip install -r requirements_ai.txt
pip install -r requirements_heavy.txt
# または、一括インストール（メモリに余裕がある場合）
# pip install -r requirements.txt

# 所有権をappuserに戻す（セキュリティのため、sudo権限が必要）
sudo chown -R appuser:appuser /opt/morizo/Morizo-aiv2

# サービスを再起動（sudo権限が必要）
sudo systemctl start morizo-aiv2

# 状態確認（sudo権限が必要）
sudo systemctl status morizo-aiv2

# ファイルの所有権を確認（appuserユーザー所有であることを確認）
ls -la
```

### 9.2 Morizo-webの更新

```bash
# サービスを停止（sudo権限が必要）
sudo systemctl stop morizo-web

# 所有権を一時的にsasakiに変更（更新作業のため、sudo権限が必要）
sudo chown -R sasaki:sasaki /opt/morizo/Morizo-web

# リポジトリの更新（sasakiユーザーで実行）
cd /opt/morizo/Morizo-web
git pull

# 依存関係の更新（必要に応じて、sasakiユーザーで実行）
npm install

# 本番ビルド（sasakiユーザーで実行）
npm run build

# 所有権をappuserに戻す（セキュリティのため、sudo権限が必要）
sudo chown -R appuser:appuser /opt/morizo/Morizo-web

# サービスを再起動（sudo権限が必要）
sudo systemctl start morizo-web

# 状態確認（sudo権限が必要）
sudo systemctl status morizo-web

# ファイルの所有権を確認（appuserユーザー所有であることを確認）
ls -la
```

---

## 10. セキュリティチェックリスト

- [ ] SSL証明書が正しく設定されている
- [ ] nginxがSSL証明書ファイルを読み取れることを確認（nginxはrootまたはwww-dataユーザーで実行されるため、通常は問題なし）
- [ ] nginx設定ファイル（`/etc/nginx/sites-available/morizo`）が正しく設定されている
- [ ] nginx設定の構文チェックが成功している（`sudo nginx -t`）
- [ ] nginxが起動し、ポート443でリスニングしていることを確認
- [ ] 環境変数ファイルに機密情報が含まれている（`.gitignore`で除外されていることを確認）
- [ ] 環境変数ファイルの権限が適切に設定されている（`chmod 600`）
- [ ] ファイアウォールルールで必要最小限のポートのみ開放（443のみ）
- [ ] システムパッケージが最新の状態である
- [ ] ログファイルに機密情報が出力されていない
- [ ] ベクトルDBディレクトリのアクセス権限が適切に設定されている
- [ ] アプリケーションが`appuser`ユーザーで実行されていることを確認
- [ ] systemdサービスファイルに`User=appuser`、`Group=appuser`が設定されていることを確認
- [ ] systemdサービスファイルに`PrivateTmp=true`が設定されていることを確認
- [ ] systemdサービスファイルに`AmbientCapabilities=CAP_NET_BIND_SERVICE`が**設定されていない**ことを確認（nginxがSSL/TLS終端を担当するため不要）
- [ ] `/opt/morizo`配下のファイル・ディレクトリが`appuser`ユーザー所有であることを確認
- [ ] Next.jsがHTTP（localhost:3000）で起動していることを確認
- [ ] 静的ファイルディレクトリの読み取り権限が適切に設定されている（nginxが読み取れること）
- [ ] rootユーザーでの作業を行っていないことを確認
- [ ] システムのタイムゾーンがJST（Asia/Tokyo）に設定されている（セクション2.6参照）
- [ ] ログの時刻がJSTで表示されていることを確認（セクション7.0参照）

---

## 11. 今後の改善項目

以下の項目は後日実装予定：

1. **ログローテーション設定** ✅ **完了**
   - logrotateを使用したログファイルの自動ローテーション（セクション7.3参照）
   - ログの自動削除設定
   - アプリケーションレベルとOSレベルのローテーション競合回避機能

2. **モニタリング設定**
   - Cloud Monitoringやその他のモニタリングツールの導入
   - メトリクスの収集

3. **アラート設定**
   - 異常検知時の通知方法
   - メール/Slack通知の設定

4. **CI/CDパイプライン**
   - GitHub Actions等を使用した自動デプロイ
   - テストの自動実行

5. **バックアップ自動化**
   - 定期的なバックアップスクリプトの作成
   - Cloud Storage等への自動バックアップ

6. **nginxリバースプロキシの導入** ✅ **完了**
   - Next.jsの前にnginxを配置してパフォーマンス向上（セクション4.5参照）
   - 静的ファイル配信の最適化（セクション4.5参照）
   - SSL/TLS処理の効率化（セクション4.5参照）
   - 複数アプリケーションの統合管理（Next.js + FastAPI）
   - セキュリティ強化（DDoS対策、レート制限など）（セクション4.5参照）
   - 詳細なアクセスログ・エラーログの取得（セクション4.5参照）

7. **水平スケーリング対応**
   - 複数のNext.jsインスタンスへの負荷分散
   - 複数のFastAPIインスタンスへの負荷分散
   - ロードバランサー（nginx/ALB）の設定
   - セッション管理の対応（Sticky Sessionなど）

8. **垂直スケーリング対応**
   - GCP VMマシンタイプのアップグレード計画
   - リソース監視に基づくスケールアップ判断基準
   - メモリ・CPU使用率の閾値設定

9. **マルチインスタンス構成**
   - 複数GCP VMインスタンスへの分散デプロイ
   - 共有ストレージ（Cloud Storage等）の検討
   - ベクトルDBの共有化または分散配置
   - データベース接続プールの最適化

10. **オートスケーリング設定**
    - Cloud Monitoringベースの自動スケーリング
    - トラフィックに応じたインスタンス数の自動調整
    - コスト最適化のためのスケールダウンポリシー

---

## 12. 関連ドキュメント

- [環境変数設定ガイド](../ENVIRONMENT_SETUP.md)
- [README](../README.md)

---

## 更新履歴

- 2025-01-XX: nginxリバースプロキシの導入
  - セクション4.5: 「Next.jsをHTTPSで起動するための設定」を削除し、「nginxリバースプロキシの設定」に置き換え
    - nginxのインストール手順を追加
    - nginx設定ファイルの作成手順を追加（SSL/TLS終端、リバースプロキシ、セキュリティヘッダー、レート制限）
    - Next.jsをHTTP（localhost:3000）で起動する設定に変更
    - 静的ファイルの直接配信設定を追加
  - セクション4.6: systemdサービスファイルから`AmbientCapabilities=CAP_NET_BIND_SERVICE`を削除
  - セクション1.2: ネットワーク構成図にnginxを追加
  - セクション1.3: ポート設定を更新（nginx: 443、Next.js: 3000）
  - セクション2.1: システムパッケージのインストールにnginxを追加
  - セクション6.2.1: nginx関連のトラブルシューティングを追加
  - セクション10: セキュリティチェックリストにnginx関連の確認項目を追加
  - セクション11: 「nginxリバースプロキシの導入」を完了マーク
- 2025-11-21: ログローテーション設定を追加
  - セクション7.3: ログローテーション設定を追加
    - Morizo-aiv2のlogrotate設定（OSレベル）
    - Morizo-webのlogrotate設定（OSレベル）
    - `LOG_INITIALIZE_BACKUP`環境変数の説明を追加
    - 開発環境と本番環境での使い分けを明記
  - セクション4.3: Morizo-webの環境変数設定に`LOG_INITIALIZE_BACKUP`を追加
- 2025-11-21: ログ時刻を日本時間（JST）に変更する設定を追加
  - セクション2.6: タイムゾーンの設定（日本時間JST）を追加
  - セクション7.0: ログ時刻の設定（日本時間JST）を追加
  - Morizo-aiv2とMorizo-webのログがJSTで表示されるように設定
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
   - 対象ドメイン（morizo.csngrp.co.jp）がGCP VMのIPに正しく向いている必要がある
3. ポート80の一時開放が必要な場合がある
   - 初回取得時にHTTP-01チャレンジで使用

本番移行計画書の「2.4 SSL証明書の取得（Let's Encrypt）」セクションで、Certbotを使用した取得手順を記載しています。
