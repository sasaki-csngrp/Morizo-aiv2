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

