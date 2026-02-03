# セキュリティ強化作業プラン

## 背景

GCP VMインスタンスが暗号通貨マイニングのポリシー違反により停止されました。セキュリティを強化し、インスタンスを再構築するための作業プランです。

## 現状の問題点

### 1. 実行ユーザー権限の分離不足

- **現状**: アプリケーションが`sasaki`ユーザー（通常の作業ユーザー）で実行されている
- **問題**: アプリケーションが侵害された場合、`sasaki`ユーザーの権限でシステム全体に影響を与える可能性がある
- **リスク**: 攻撃者がアプリケーション経由でシステム全体にアクセス可能

### 2. Morizo-webのセキュリティリスク

#### 問題2-1: CORS設定が全開放
- **ファイル**: `app/api/whisper/route.ts`
- **現状**: `Access-Control-Allow-Origin: *`で全オリジンからのアクセスを許可
- **リスク**: 不正なオリジンからのAPIアクセスが可能

#### 問題2-2: セキュリティヘッダー未設定
- **ファイル**: `middleware.ts`
- **現状**: セキュリティヘッダー（X-Content-Type-Options、X-Frame-Options等）が設定されていない
- **リスク**: XSS、クリックジャッキング等の攻撃に対して脆弱

#### 問題2-3: 入力検証の確認が必要
- **確認が必要なファイル**: 
  - `app/api/whisper/route.ts`（音声ファイルのサイズ・形式チェック）
  - その他のAPIルート（入力検証の実装状況）
- **リスク**: 不正な入力による攻撃の可能性

---

## 作業プラン

### 1. `docs/PRODUCTION_DEPLOYMENT_PLAN.md`の見直し

#### 修正箇所1: セクション2「初期セットアップ」の冒頭に低権限ユーザー作成手順を追加

- **ファイル**: `docs/PRODUCTION_DEPLOYMENT_PLAN.md`
- **位置**: セクション2.1の前（新規セクション「2.0 実行ユーザー権限の分離」として追加）
- **修正内容**:
  - 低権限ユーザー`appuser`の作成手順を追加
  - ホームディレクトリなし、ログインシェルなしの設定
  - `/opt/morizo`配下の所有権変更手順
- **修正の理由**: 最小権限の原則に基づき、アプリケーション実行を専用の低権限ユーザーに分離するため
- **修正の影響**: 
  - 既存の`sasaki`ユーザーでの作業フローに影響
  - 手順書の順序を調整する必要がある

**追加する内容（想定）**:

```bash
# アプリケーション実行用の低権限ユーザーを作成（ホームディレクトリなし、ログインシェルなし）
sudo useradd -r -s /bin/false appuser

# /opt/morizoディレクトリの所有権をappuserに変更
sudo chown -R appuser:appuser /opt/morizo
```

#### 修正箇所2: セクション3.5「systemdサービスファイルの作成」の修正

- **ファイル**: `docs/PRODUCTION_DEPLOYMENT_PLAN.md`
- **位置**: 行344-365の`morizo-aiv2.service`設定
- **修正内容**:
  - `User=sasaki` → `User=appuser`に変更
  - `Group=appuser`を追加
  - `PrivateTmp=true`を追加
- **修正の理由**: アプリケーションを低権限ユーザーで実行し、一時ファイルを他のプロセスから隔離するため
- **修正の影響**: 
  - サービス再起動が必要
  - `/opt/morizo/Morizo-aiv2`ディレクトリの所有権を`appuser`に変更する必要がある

**修正後の内容（想定）**:

```ini
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
```

#### 修正箇所3: セクション4.6「systemdサービスファイルの作成」の修正

- **ファイル**: `docs/PRODUCTION_DEPLOYMENT_PLAN.md`
- **位置**: 行545-566の`morizo-web.service`設定
- **修正内容**:
  - `User=sasaki` → `User=appuser`に変更
  - `Group=appuser`を追加
  - `PrivateTmp=true`を追加
- **修正の理由**: アプリケーションを低権限ユーザーで実行し、一時ファイルを他のプロセスから隔離するため
- **修正の影響**: 
  - サービス再起動が必要
  - `/opt/morizo/Morizo-web`ディレクトリの所有権を`appuser`に変更する必要がある
  - SSL証明書の読み取り権限を`appuser`に付与する必要がある

**修正後の内容（想定）**:

```ini
[Service]
Type=simple
User=appuser
Group=appuser
WorkingDirectory=/opt/morizo/Morizo-web
Environment="NODE_ENV=production"
ExecStart=/usr/bin/npm start
Restart=always
RestartSec=10

# セキュリティ設定
PrivateTmp=true

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-web
```

#### 修正箇所4: セクション10「セキュリティチェックリスト」の更新

- **ファイル**: `docs/PRODUCTION_DEPLOYMENT_PLAN.md`
- **位置**: 行1014-1029
- **修正内容**:
  - `appuser`ユーザーで実行されていることの確認項目を追加
  - `PrivateTmp=true`の設定確認項目を追加
- **修正の理由**: 新しいセキュリティ設定の確認項目を追加するため
- **修正の影響**: チェックリストの拡充のみ

**追加する確認項目（想定）**:

```markdown
- [ ] アプリケーションが`appuser`ユーザーで実行されていることを確認
- [ ] systemdサービスファイルに`PrivateTmp=true`が設定されていることを確認
- [ ] `/opt/morizo`配下のファイル・ディレクトリが`appuser`ユーザー所有であることを確認
- [ ] SSL証明書ファイルが`appuser`ユーザーから読み取れることを確認
```

---

### 2. Morizo-webのセキュリティレビュー結果と修正

#### 問題1: CORS設定が全開放

- **ファイル**: `app/api/whisper/route.ts`
- **位置**: 行11-15の`setCorsHeaders`関数
- **現状**: `Access-Control-Allow-Origin: *`で全オリジンからのアクセスを許可
- **修正内容**: 特定のオリジンのみ許可（例: `https://morizo.csngrp.co.jp`）
- **修正の理由**: 不正なオリジンからのアクセスを防止するため
- **修正の影響**: 
  - 同一オリジンからのアクセスには影響なし
  - 他オリジンからのアクセスは拒否される（セキュリティ向上）

**修正後の内容（想定）**:

```typescript
// CORSヘッダーを設定するヘルパー関数
function setCorsHeaders(response: NextResponse) {
  // 本番環境では特定のオリジンのみ許可
  const allowedOrigin = process.env.NODE_ENV === 'production' 
    ? 'https://morizo.csngrp.co.jp'
    : '*'; // 開発環境では全許可
  
  response.headers.set('Access-Control-Allow-Origin', allowedOrigin);
  response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  response.headers.set('Access-Control-Max-Age', '86400');
  return response;
}
```

#### 問題2: セキュリティヘッダー未設定

- **ファイル**: `middleware.ts`
- **位置**: 行50-54のレスポンス処理
- **現状**: セキュリティヘッダーが設定されていない
- **修正内容**: 以下のセキュリティヘッダーを追加
  - `X-Content-Type-Options: nosniff` - MIMEタイプスニッフィング攻撃を防止
  - `X-Frame-Options: DENY` - クリックジャッキング攻撃を防止
  - `X-XSS-Protection: 1; mode=block` - XSS攻撃の緩和（レガシーブラウザ対応）
  - `Referrer-Policy: strict-origin-when-cross-origin` - リファラー情報の漏洩を制限
  - `Content-Security-Policy`（必要に応じて） - XSS攻撃を防止
- **修正の理由**: XSS、クリックジャッキング等の攻撃を防止するため
- **修正の影響**: 既存機能への影響は最小限（セキュリティ向上）

**修正後の内容（想定）**:

```typescript
export function middleware(request: NextRequest) {
  const requestId = Math.random().toString(36).substr(2, 9);
  
  // Edge Runtime対応のシンプルなログ
  console.log(`[MIDDLEWARE] HTTPリクエスト受信: ${request.method} ${request.nextUrl.pathname}`, {
    requestId,
    method: request.method,
    url: request.url,
    pathname: request.nextUrl.pathname,
    userAgent: request.headers.get('user-agent'),
    origin: request.headers.get('origin'),
    contentType: request.headers.get('content-type'),
    contentLength: request.headers.get('content-length'),
    timestamp: getJSTTimestamp()
  });

  // レスポンスを返す前にログを記録
  const response = NextResponse.next();
  
  // セキュリティヘッダーの設定
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-XSS-Protection', '1; mode=block');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  
  response.headers.set('X-Request-ID', requestId);
  
  return response;
}
```

#### 問題3: 入力検証の確認

- **確認が必要なファイル**:
  - `app/api/whisper/route.ts`（音声ファイルのサイズ・形式チェック）
  - その他のAPIルート（入力検証の実装状況）
- **現状**: 一部のAPIで入力検証が実装済みか確認が必要
- **修正内容**: 必要に応じて入力検証を強化
  - ファイルサイズの制限
  - ファイル形式の検証
  - リクエストボディのバリデーション
- **修正の理由**: 不正な入力による攻撃を防止するため
- **修正の影響**: 不正な入力が拒否される（正常な動作）

**修正例（whisper/route.ts）**:

```typescript
// ファイルサイズの制限（例: 10MB）
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

if (audioFile.size > MAX_FILE_SIZE) {
  ServerLogger.warn(LogCategory.VOICE, 'ファイルサイズが上限を超えています', { 
    requestId,
    fileSize: audioFile.size,
    maxSize: MAX_FILE_SIZE
  });
  const response = NextResponse.json(
    { error: 'ファイルサイズが上限（10MB）を超えています' },
    { status: 400 }
  );
  return setCorsHeaders(response);
}

// ファイル形式の検証
const allowedMimeTypes = ['audio/mpeg', 'audio/wav', 'audio/webm', 'audio/ogg'];
if (!allowedMimeTypes.includes(audioFile.type)) {
  ServerLogger.warn(LogCategory.VOICE, '許可されていないファイル形式です', { 
    requestId,
    fileType: audioFile.type
  });
  const response = NextResponse.json(
    { error: '許可されていないファイル形式です' },
    { status: 400 }
  );
  return setCorsHeaders(response);
}
```

---

## その他の設定（ユーザーが作業）

### 3. GCP側でのネットワーク出口（Egress）の制限

- **作業者**: ユーザー
- **内容**: GCPのファイアウォールルールで、アウトバウンド通信を制限
- **目的**: 不正な外部通信（マイニング等）を防止

#### 3.1. 許可ルールの作成（必要な通信を許可）

まず、アプリケーションに必要な通信を許可するルールを作成します。

1. **GCPコンソールにアクセス**
   - https://console.cloud.google.com/ にログイン

2. **ファイアウォールルールの作成画面を開く**
   - ナビゲーションメニューから「VPCネットワーク」→「ファイアウォール」を選択
   - 「ファイアウォールルールを作成」をクリック

3. **DNS許可ルールの作成（必須）**
   - **基本設定**:
     - 名前: `allow-egress-dns`
     - 説明: 「DNS通信を許可」
     - ネットワーク: 対象のVPCネットワークを選択
     - 優先度: `500`（**重要**: 拒否ルールより小さい数値に設定）
     - トラフィックの方向: **アウトバウンド（Egress）**を選択
     - アクション: **許可**を選択
   - **ターゲット**:
     - 「指定されたターゲットタグ」を選択
     - ターゲットタグ: `morizo-server`（または適切なタグ名）
   - **フィルタ**:
     - 送信元IP範囲: `0.0.0.0/0`
     - 送信先IP範囲: `0.0.0.0/0`
     - プロトコルとポート: 「指定したプロトコルとポート」を選択
       - UDP: `53`（DNS）
   - 「作成」をクリック

4. **HTTP/HTTPS許可ルールの作成**
   - 「ファイアウォールルールを作成」をクリック
   - **基本設定**:
     - 名前: `allow-egress-http-https`
     - 説明: 「HTTP/HTTPS通信を許可」
     - ネットワーク: 対象のVPCネットワークを選択
     - 優先度: `500`（**重要**: 拒否ルールより小さい数値に設定）
     - トラフィックの方向: **アウトバウンド（Egress）**を選択
     - アクション: **許可**を選択
   - **ターゲット**:
     - 「指定されたターゲットタグ」を選択
     - ターゲットタグ: `morizo-server`（または適切なタグ名）
   - **フィルタ**:
     - 送信元IP範囲: `0.0.0.0/0`
     - 送信先IP範囲: `0.0.0.0/0`
     - プロトコルとポート: 「指定したプロトコルとポート」を選択
       - TCP: `80,443`（HTTP/HTTPS）
   - 「作成」をクリック

5. **その他の必要な通信の許可ルール作成**
   - アプリケーションが使用する外部APIやサービスへの通信が必要な場合、同様の手順で許可ルールを作成
   - 例: NTP（UDP 123）、特定のAPIエンドポイントへの通信など

#### 3.2. 拒否ルールの作成（その他すべてを拒否）

許可ルールを作成した後、それ以外のすべてのアウトバウンド通信を拒否するルールを作成します。

1. **ファイアウォールルールの作成画面を開く**
   - 「ファイアウォールルールを作成」をクリック

2. **拒否ルールの設定**
   - **基本設定**:
     - 名前: `deny-egress-all`
     - 説明: 「許可された通信以外のアウトバウンドを拒否」
     - ネットワーク: 対象のVPCネットワークを選択
     - 優先度: `65534`（**重要**: 許可ルールより大きい数値に設定）
     - トラフィックの方向: **アウトバウンド（Egress）**を選択
     - アクション: **拒否**を選択
   - **ターゲット**:
     - 「指定されたターゲットタグ」を選択
     - ターゲットタグ: `morizo-server`（または適切なタグ名）
   - **フィルタ**:
     - 送信元IP範囲: `0.0.0.0/0`
     - 送信先IP範囲: `0.0.0.0/0`
     - プロトコルとポート: 「すべて」を選択
   - 「作成」をクリック

#### 3.3. ファイアウォールルールとタグの仕組み

GCPのファイアウォールルールでは、タグを使用してルールが適用されるVMインスタンスを指定します。

**動作の仕組み**:

1. **ファイアウォールルール側**: 「ターゲットタグ」を指定
   - ルール作成時に「指定されたターゲットタグ」を選択し、タグ名を指定（例: `morizo-server`）
   - このタグを持つVMインスタンスにのみ、このルールが適用されます

2. **VMインスタンス側**: 「ネットワークタグ」を設定
   - VMインスタンスの編集画面で「ネットワークタグ」にタグ名を設定（例: `morizo-server`）

3. **タグの一致でルールが適用される**
   - VMのネットワークタグが、ルールのターゲットタグと一致する場合、そのルールが適用されます
   - タグが一致しないVMインスタンスには、そのルールは適用されません

**既存のタグの例**:

GCPにはデフォルトで以下のようなファイアウォールルールが存在します：
- `default-allow-http`: ターゲットタグ `http-server` → VMに `http-server` タグを付けるとHTTP通信が許可される
- `default-allow-https`: ターゲットタグ `https-server` → VMに `https-server` タグを付けるとHTTPS通信が許可される

現在のVMに `http-server`、`https-server` タグが付いている場合、これらは上記のデフォルトルールを適用するためのタグです。

**Egress制限ルールでのタグの使い方**:

1. Egress制限用の新しいタグ（例: `morizo-server`）をファイアウォールルールのターゲットタグとして指定
2. 同じタグ（`morizo-server`）をVMインスタンスのネットワークタグに追加
3. これにより、作成したEgress制限ルールがそのVMインスタンスに適用されます

既存の `http-server`、`https-server` タグは維持したまま、新しいタグを追加することで、既存のルールと新しいEgress制限ルールの両方が適用されます。

#### 3.4. VMインスタンスのタグの確認と設定

ファイアウォールルールでターゲットタグを使用している場合、対象のVMインスタンスにタグを適用する必要があります。まず、現在のタグを確認してから、必要に応じて設定します。

##### 3.3.1. 現在のタグの確認方法

**方法1: インスタンス詳細画面から確認**

1. ナビゲーションメニューから「Compute Engine」→「VMインスタンス」を選択
2. 対象のインスタンス名をクリック
3. 「ネットワーク」セクションを展開
4. 「ネットワークタグ」欄に現在のタグが表示されます（タグがない場合は空欄）

**方法2: インスタンス一覧から確認**

1. 「Compute Engine」→「VMインスタンス」を開く
2. インスタンス一覧の「ネットワークタグ」列で確認できます
   - 列が表示されていない場合は、列の表示設定（列のヘッダーを右クリック）で「ネットワークタグ」を追加

##### 3.3.2. タグの設定方法

**既存インスタンスにタグを追加/変更**

1. **VMインスタンスの編集画面を開く**
   - ナビゲーションメニューから「Compute Engine」→「VMインスタンス」を選択
   - 対象のインスタンス名をクリック
   - 「編集」をクリック

2. **ネットワークタグの追加**
   - 「ネットワーク」セクションを展開
   - 「ネットワークタグ」に `morizo-server`（または設定したタグ名）を入力
     - 複数のタグを設定する場合は、カンマ区切りで入力
   - 「保存」をクリック
   - インスタンスが再起動される場合があります（通常は再起動不要）

**新規インスタンス作成時にタグを設定**

1. VMインスタンス作成時に「ネットワーク」セクションを展開
2. 「ネットワークタグ」欄にタグ名を入力

#### 3.4. 注意事項

- **優先順位**: ファイアウォールルールは優先度の数値が**小さいほど先に評価**されます。許可ルール（優先度: 500）を拒否ルール（優先度: 65534）より**小さい数値**に設定することで、許可ルールが先に評価され、マッチした場合は拒否ルールまで到達しません。許可ルールでマッチしなかった通信のみ、拒否ルールが評価されます。

- **必要な通信の確認**: アプリケーションが使用する外部APIやサービスへの通信を事前に確認し、必要な許可ルールを作成してください。
  - 例: OpenAI API、その他の外部サービスへの通信

- **テスト手順**: 
  1. まず許可ルールのみを作成して動作確認
  2. 問題なければ拒否ルールを追加
  3. 段階的に制限を強化

- **ログの確認**: ファイアウォールルールのログを有効化することで、ブロックされた通信を確認できます。
  - 「VPCネットワーク」→「ファイアウォールルール」→ ルールの編集 → 「ログを有効にする」にチェック

#### 3.5. Egress制限の動作確認方法

ファイアウォールルールの設定後、以下のコマンドでVMインスタンス上から動作確認を行います。

##### 3.5.1. DNS通信の確認

DNS（UDP 53）が正常に動作していることを確認します。

```bash
# nslookupコマンドで確認
nslookup google.com

# または digコマンドで確認
dig google.com

# 成功例:
# Server:		8.8.8.8
# Address:	8.8.8.8#53
# 
# Non-authoritative answer:
# Name:	google.com
# Address: 142.250.191.14
```

**確認ポイント**: DNSクエリが正常に解決され、IPアドレスが返ってくれば成功です。

##### 3.5.2. HTTP/HTTPS通信の確認

HTTP（TCP 80）とHTTPS（TCP 443）が正常に動作していることを確認します。

```bash
# HTTP通信の確認
curl -I http://www.google.com

# HTTPS通信の確認
curl -I https://www.google.com

# 成功例（HTTP）:
# HTTP/1.1 200 OK
# Content-Type: text/html; charset=ISO-8859-1
# ...

# 成功例（HTTPS）:
# HTTP/2 200
# content-type: text/html; charset=UTF-8
# ...
```

**確認ポイント**: HTTPステータスコード（200等）が返ってくれば成功です。

##### 3.5.3. その他の通信がブロックされることの確認

DNS、HTTP/HTTPS以外の通信がブロックされていることを確認します。

```bash
# SSH（TCP 22）がブロックされることを確認
timeout 5 telnet ssh.example.com 22
# または
timeout 5 nc -zv ssh.example.com 22

# FTP（TCP 21）がブロックされることを確認
timeout 5 telnet ftp.example.com 21
# または
timeout 5 nc -zv ftp.example.com 21

# 成功例（ブロックされている場合）:
# telnet: Unable to connect to remote host: Connection timed out
# または
# nc: connect to xxx.xxx.xxx.xxx port 22 (tcp) failed: Connection timed out
```

**確認ポイント**: 接続がタイムアウト（Connection timed out）すれば、ブロックされていることを確認できます。

##### 3.5.4. 一括確認スクリプト

以下のスクリプトで一括確認できます。

```bash
#!/bin/bash

echo "=== DNS通信の確認 ==="
if nslookup google.com > /dev/null 2>&1; then
    echo "✓ DNS通信: 成功"
else
    echo "✗ DNS通信: 失敗"
fi

echo ""
echo "=== HTTP通信の確認 ==="
if curl -I -s --max-time 5 http://www.google.com | head -1 | grep -q "200\|301\|302"; then
    echo "✓ HTTP通信: 成功"
else
    echo "✗ HTTP通信: 失敗"
fi

echo ""
echo "=== HTTPS通信の確認 ==="
if curl -I -s --max-time 5 https://www.google.com | head -1 | grep -q "200\|301\|302"; then
    echo "✓ HTTPS通信: 成功"
else
    echo "✗ HTTPS通信: 失敗"
fi

echo ""
echo "=== その他の通信（SSH）がブロックされることの確認 ==="
if timeout 3 nc -zv 8.8.8.8 22 > /dev/null 2>&1; then
    echo "✗ SSH通信: 許可されている（想定外）"
else
    echo "✓ SSH通信: ブロックされている（正常）"
fi

echo ""
echo "=== 確認完了 ==="
```

**使用方法**:
1. 上記のスクリプトを `check_egress.sh` として保存
2. 実行権限を付与: `chmod +x check_egress.sh`
3. 実行: `./check_egress.sh`

##### 3.5.5. 注意事項

- **タイムアウト時間**: ブロックされた通信の確認では、タイムアウトまで時間がかかる場合があります。`timeout` コマンドで時間を制限することを推奨します。
- **必要なパッケージ**: 一部のコマンド（`nc`、`dig`等）がインストールされていない場合があります。必要に応じてインストールしてください。
  ```bash
  # Ubuntu/Debianの場合
  sudo apt-get update
  sudo apt-get install -y netcat-openbsd dnsutils
  ```
- **アプリケーション固有の通信**: アプリケーションが使用する外部API（例: OpenAI API）への通信も、必要に応じて確認してください。

---

## 作業の優先順位

1. **最優先**: 実行ユーザー権限の分離（`appuser`ユーザーの作成とsystemd設定の変更）
2. **高**: CORS設定の修正（`whisper/route.ts`）
3. **高**: セキュリティヘッダーの追加（`middleware.ts`）
4. **中**: 入力検証の強化（各APIルート）

---

## 注意事項

- すべての修正は、**承認を得てから**実施すること
- 修正後は、必ず動作確認を行うこと
- 本番環境への適用前に、テスト環境で検証すること
- セキュリティ設定の変更は、既存機能に影響を与える可能性があるため、慎重に実施すること

---

## 更新履歴

- 2025-01-XX: 初版作成

