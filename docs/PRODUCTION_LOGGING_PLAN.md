# 本番環境ロギング改善計画書

## 概要

Morizo-aiv2の本番環境デプロイに向けたロギング改善計画書です。
現在のロギング実装を分析し、本番環境で必要となる機能を段階的に実装します。

---

## 1. 現状の問題点

### 1.1 環境変数対応の不足
- **問題**: 環境変数`LOG_FILE`が定義されているが、コード内で使用されていない
- **影響**: 本番環境でログファイルのパスを環境変数で制御できない
- **現在の実装**: `config/logging.py`で固定パス`morizo_ai.log`を使用

### 1.2 ログローテーション設定の不足
- **問題**: アプリケーションレベルのローテーション（RotatingFileHandler）はあるが、OSレベルのlogrotate設定がない
- **影響**: 長期間運用するとディスク容量を圧迫する可能性
- **現在の実装**: Pythonの`RotatingFileHandler`（10MB、5バックアップ）のみ

### 1.3 エラーログの分離不足
- **問題**: すべてのログが1つのファイルに出力される
- **影響**: エラーの特定と分析が困難
- **現在の実装**: 単一のログファイル（`morizo_ai.log`）

### 1.4 構造化ログの未対応
- **問題**: テキスト形式のログのみで、JSON形式のログが出力できない
- **影響**: ログ分析ツール（CloudWatch、ELK等）との連携が困難
- **現在の実装**: カスタムフォーマッター（`AlignedFormatter`）によるテキスト形式のみ

### 1.5 セキュリティログの不足
- **問題**: 認証失敗、不正アクセス試行などのセキュリティイベントが専用ログに記録されない
- **影響**: セキュリティインシデントの検知と対応が遅れる
- **現在の実装**: 通常のログに混在して記録

### 1.6 パフォーマンスログの不足
- **問題**: レスポンス時間の閾値超過やスロークエリが専用ログに記録されない
- **影響**: パフォーマンスボトルネックの特定が困難
- **現在の実装**: `LoggingMiddleware`で処理時間は記録されるが、閾値チェックなし

### 1.7 ログレベルの環境別設定不足
- **問題**: 環境変数`ENVIRONMENT`に基づいた自動的なログレベル調整がない
- **影響**: 本番環境でもDEBUGログが出力される可能性
- **現在の実装**: 環境変数`LOG_LEVEL`のみで制御

### 1.8 systemdログとの統合不足
- **問題**: systemdジャーナルへの出力が設定されていない
- **影響**: systemdログの利点（自動ローテーション、検索容易）を活用できない
- **現在の実装**: ファイルログとコンソールログのみ

### 1.9 DEBUGログが出力されない問題（緊急）

- **問題**: 開発環境で`LOG_LEVEL=DEBUG`を設定してもDEBUGログが出力されない
- **原因**: 
  1. `main.py`でログレベルが`"INFO"`にハードコードされている
  2. ファイルハンドラーのレベルが`logging.INFO`に固定されている（98行目）
  3. コンソールハンドラーのレベルが`logging.INFO`に固定されている（117行目）
- **影響**: 
  - 開発環境でデバッグが困難
  - デバッグログがINFOレベルで出力されているため、ログの意味が不明確
  - 環境変数`LOG_LEVEL`が機能していない
- **現在の実装**: 
  - `main.py`の25行目: `setup_logging(log_level="INFO", initialize=True)`
  - `config/logging.py`の98行目: `file_handler.setLevel(logging.INFO)`
  - `config/logging.py`の117行目: `console_handler.setLevel(logging.INFO)`

---

## 2. 改善案

### 2.1 環境変数対応の強化

**修正箇所**: `config/logging.py`の`LoggingConfig`クラス

**修正内容**:
- 環境変数`LOG_FILE`を読み取り、デフォルトは`morizo_ai.log`
- 環境変数`LOG_DIR`でログディレクトリを指定可能に
- 本番環境では`/opt/morizo/Morizo-aiv2/morizo_ai.log`を使用

**修正理由**: 本番環境でログファイルのパスを環境変数で制御可能にする

**修正の影響**: 既存のログファイルパスに依存するコードは影響なし（デフォルト値で互換性維持）

**実装詳細**:
```python
# 環境変数からログファイルパスを取得
log_file = os.getenv('LOG_FILE', 'morizo_ai.log')
log_dir = os.getenv('LOG_DIR', '.')

# ディレクトリが指定されている場合は結合
if log_dir != '.':
    log_file = os.path.join(log_dir, os.path.basename(log_file))
```

---

### 2.2 エラーログの分離

**修正箇所**: `config/logging.py`の`LoggingConfig`クラス

**修正内容**:
- ERROR/CRITICALレベルのログを別ファイル（`morizo_ai_error.log`）に出力
- 通常ログとエラーログを分離して管理

**修正理由**: エラーの特定と分析を容易にする

**修正の影響**: 新規ファイルが追加されるのみで既存機能への影響なし

**実装詳細**:
```python
# エラーログ用のハンドラーを追加
error_file_handler = logging.handlers.RotatingFileHandler(
    filename='morizo_ai_error.log',
    maxBytes=self.max_file_size,
    backupCount=self.backup_count,
    encoding='utf-8'
)
error_file_handler.setLevel(logging.ERROR)
logger.addHandler(error_file_handler)
```

---

### 2.3 構造化ログ（JSON形式）のオプション追加

**修正箇所**: `config/logging.py`にJSONフォーマッターを追加

**修正内容**:
- 環境変数`LOG_FORMAT=json`でJSON形式に切り替え可能
- デフォルトは従来のテキスト形式（後方互換性維持）

**修正理由**: ログ分析ツール（CloudWatch、ELK等）との連携を容易にする

**修正の影響**: デフォルトは従来形式のため既存機能への影響なし

**実装詳細**:
```python
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)
```

---

### 2.4 セキュリティログの強化

**修正箇所**: `api/middleware/authentication.py`（存在確認が必要）

**修正内容**:
- 認証失敗、不正アクセス試行、レート制限超過を専用ログに記録
- セキュリティイベントを`morizo_ai_security.log`に出力

**修正理由**: セキュリティインシデントの検知と対応を迅速化

**修正の影響**: 新規ログファイルが追加されるのみ

**実装詳細**:
```python
# セキュリティログ用の専用ロガー
security_logger = logging.getLogger('morizo_ai.security')
security_handler = logging.handlers.RotatingFileHandler(
    filename='morizo_ai_security.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
    encoding='utf-8'
)
security_logger.addHandler(security_handler)

# 認証失敗時のログ記録
security_logger.warning(
    f"Authentication failed: user_id={user_id}, "
    f"ip={request.client.host}, reason={reason}"
)
```

---

### 2.5 パフォーマンスログの追加

**修正箇所**: `api/middleware/logging.py`の`LoggingMiddleware`

**修正内容**:
- レスポンス時間の閾値（例: 1秒以上）を超えたリクエストを`morizo_ai_performance.log`に記録
- スロークエリの検出と記録

**修正理由**: パフォーマンスボトルネックの特定を容易にする

**修正の影響**: 新規ログファイルが追加されるのみ

**実装詳細**:
```python
# パフォーマンスログ用の専用ロガー
performance_logger = logging.getLogger('morizo_ai.performance')
performance_handler = logging.handlers.RotatingFileHandler(
    filename='morizo_ai_performance.log',
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
    encoding='utf-8'
)
performance_logger.addHandler(performance_handler)

# 閾値超過時のログ記録
SLOW_REQUEST_THRESHOLD = float(os.getenv('SLOW_REQUEST_THRESHOLD', '1.0'))
if process_time > SLOW_REQUEST_THRESHOLD:
    performance_logger.warning(
        f"Slow request: {request.method} {request.url.path} "
        f"Time: {process_time:.3f}s, User: {user_id}"
    )
```

---

### 2.6 logrotate設定ファイルの作成

**修正箇所**: 新規ファイル `/etc/logrotate.d/morizo-aiv2`（本番環境用）

**修正内容**:
- ログファイルの自動ローテーション設定
- 30日間保持、圧縮、古いログの自動削除

**修正理由**: ディスク容量の管理とログの長期保存

**修正の影響**: 本番環境の設定のみ

**実装詳細**:
```
/opt/morizo/Morizo-aiv2/morizo_ai*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    missingok
    create 0644 ubuntu ubuntu
    postrotate
        systemctl reload morizo-aiv2 > /dev/null 2>&1 || true
    endscript
}
```

---

### 2.7 ログレベルの環境別設定

**修正箇所**: `config/logging.py`の`get_log_level()`関数

**修正内容**:
- 環境変数`ENVIRONMENT`に基づいてログレベルを自動調整
  - `production`: INFO以上（DEBUGログを抑制）
  - `development`: DEBUG以上（すべてのログを出力）
  - `staging`: WARNING以上（INFOログを抑制）

**修正理由**: 環境に応じた適切なログ出力

**修正の影響**: デフォルト動作は維持（環境変数未設定時）

**実装詳細**:
```python
def get_log_level() -> str:
    """Get log level from environment variable with environment-based defaults"""
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    log_level = os.getenv('LOG_LEVEL', '').upper()
    
    # 環境変数LOG_LEVELが明示的に設定されている場合はそれを使用
    if log_level:
        return log_level
    
    # 環境に基づくデフォルト値
    environment_defaults = {
        'production': 'INFO',
        'development': 'DEBUG',
        'staging': 'WARNING'
    }
    
    return environment_defaults.get(environment, 'INFO')
```

---

### 2.8 systemdログとの統合強化

**修正箇所**: `config/logging.py`にsystemdジャーナルハンドラーを追加（オプション）

**修正内容**:
- 環境変数`LOG_TO_JOURNAL=true`でsystemdジャーナルにも出力
- 本番環境ではsystemdログとファイルログの両方を利用

**修正理由**: systemdログの利点（ローテーション自動、検索容易）を活用

**修正の影響**: オプション機能のため既存機能への影響なし

**実装詳細**:
```python
# systemdジャーナルハンドラーの追加（オプション）
if os.getenv('LOG_TO_JOURNAL', 'false').lower() == 'true':
    try:
        from systemd import journal
        journal_handler = journal.JournalHandler()
        journal_handler.setLevel(logging.INFO)
        logger.addHandler(journal_handler)
        logger.info("📋 [LOGGING] systemdジャーナルハンドラー設定完了")
    except ImportError:
        logger.warning("⚠️ [LOGGING] systemdモジュールが利用できません")
```

---

### 2.9 DEBUGログ出力の修正（緊急対応）

**修正箇所**: 
1. `main.py`の25行目
2. `config/logging.py`の`_setup_file_handler`メソッド（98行目）
3. `config/logging.py`の`_setup_console_handler`メソッド（117行目）
4. `config/logging.py`の`setup_logging`メソッド（73-76行目）

**修正内容**:
1. **`main.py`の修正**:
   - `setup_logging(log_level="INFO", initialize=True)`を削除
   - `get_log_level()`を使用して環境変数からログレベルを取得
   - `setup_logging(log_level=get_log_level(), initialize=True)`に変更

2. **`_setup_file_handler`の修正**:
   - `file_handler.setLevel(logging.INFO)`を削除
   - `file_handler.setLevel(getattr(logging, log_level.upper()))`に変更
   - `log_level`パラメータを`_setup_file_handler`に渡す

3. **`_setup_console_handler`の修正**:
   - `console_handler.setLevel(logging.INFO)`を削除
   - `console_handler.setLevel(getattr(logging, log_level.upper()))`に変更
   - `log_level`パラメータを`_setup_console_handler`に渡す

4. **`setup_logging`メソッドの修正**:
   - `_setup_file_handler(root_logger, initialize)`を`_setup_file_handler(root_logger, log_level, initialize)`に変更
   - `_setup_console_handler(root_logger)`を`_setup_console_handler(root_logger, log_level)`に変更

**修正理由**: 
- 環境変数`LOG_LEVEL`でログレベルを制御可能にする
- 開発環境でDEBUGログを出力できるようにする
- ハンドラーのレベルをロガーレベルに合わせる

**修正の影響**: 
- 環境変数未設定時はデフォルト`INFO`のため、既存動作は維持
- 既存のログ出力への影響なし
- 開発環境で`.env`に`LOG_LEVEL=DEBUG`を設定するとDEBUGログが出力される

**実装詳細**:

```python
# main.py の修正
from config.logging import setup_logging, get_log_level

# ログ設定の初期化とローテーション
setup_logging(log_level=get_log_level(), initialize=True)
```

```python
# config/logging.py の修正
def setup_logging(self, log_level: str = "INFO", initialize: bool = True) -> logging.Logger:
    # ... 既存のコード ...
    
    # Setup file handler with rotation
    self._setup_file_handler(root_logger, log_level, initialize)
    
    # Setup console handler for development
    self._setup_console_handler(root_logger, log_level)
    
    # ... 既存のコード ...

def _setup_file_handler(self, logger: logging.Logger, log_level: str, initialize: bool = True) -> None:
    """Setup file handler with rotation"""
    try:
        # ... 既存のコード ...
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_file,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        # ... 既存のコード ...

def _setup_console_handler(self, logger: logging.Logger, log_level: str) -> None:
    """Setup console handler for development"""
    try:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # ... 既存のコード ...
```

**修正後の動作**:
- 開発環境で`.env`に`LOG_LEVEL=DEBUG`を設定すると、DEBUGログが出力される
- 本番環境では`LOG_LEVEL=INFO`でINFO以上のみ出力される
- 環境変数未設定時はデフォルト`INFO`で動作（後方互換性維持）

**作業規模**:
- 修正ファイル数: 1ファイル（`config/logging.py`）
- 修正行数: 約10行
- 影響範囲: ロギング設定のみ（既存ログ出力への影響なし）
- コンテキストウインドウへの影響: 小

---

## 3. 実装優先順位

### Phase 0（緊急対応・最優先）

開発環境でのデバッグを可能にするための緊急修正：

0. **DEBUGログ出力の修正（2.9）** ⚠️ **最優先** ✅ **完了**
   - 開発環境でDEBUGログを出力できるようにする
   - 環境変数`LOG_LEVEL`が機能するようにする
   - 実装工数: 小（30分-1時間）
   - **影響**: 開発効率に直結するため、最優先で実装すべき
   - **実装状況**: ✅ 完了（`main.py`、`config/logging.py`で環境変数`LOG_LEVEL`に対応）

**Phase 0の合計工数**: 約30分-1時間

---

### Phase 1（MVP必須）

本番環境デプロイに最低限必要な機能：

1. **環境変数対応の強化（2.1）** ⏳ **未実装**
   - 本番環境でログパスを環境変数で制御可能にする
   - 実装工数: 小（1-2時間）

2. **logrotate設定ファイルの作成（2.6）** ⏳ **未実装**
   - ディスク容量管理のため必須
   - 実装工数: 小（30分）

**Phase 1の合計工数**: 約2-3時間

**補足: ログレベル分類作業** ✅ **完了**
- 全ソースコードのログレベルをINFO/DEBUGに分類
- 約10ファイル、約25箇所を修正
- 認証成功ログをINFOに統一、user_idをDEBUGに分離
- 詳細パラメータをDEBUGに分離

---

### Phase 2（運用改善）

本番環境運用開始後の改善機能：

3. **エラーログの分離（2.2）** ⏳ **未実装**
   - エラー分析の効率化
   - 実装工数: 中（2-3時間）

4. **ログレベルの環境別設定（2.7）** ⏳ **未実装**
   - 環境に応じた適切なログ出力
   - 実装工数: 小（1時間）

**Phase 2の合計工数**: 約3-4時間

---

### Phase 3（高度な機能）

将来的な拡張機能：

5. **構造化ログ（JSON形式）のオプション追加（2.3）** ⏳ **未実装**
   - ログ分析ツールとの連携
   - 実装工数: 中（3-4時間）

6. **セキュリティログの強化（2.4）** ⏳ **未実装**
   - セキュリティインシデントの検知
   - 実装工数: 中（2-3時間）

7. **パフォーマンスログの追加（2.5）** ⏳ **未実装**
   - パフォーマンスボトルネックの特定
   - 実装工数: 中（2-3時間）

8. **systemdログとの統合強化（2.8）** ⏳ **未実装**
   - systemdログの利点を活用
   - 実装工数: 小（1-2時間）

**Phase 3の合計工数**: 約8-12時間

---

## 4. 実装時の注意事項

### 4.1 後方互換性の維持
- 既存のログ出力は維持する（既存のログファイルは継続使用）
- 新機能は環境変数で有効化（デフォルトは無効）
- 既存のログフォーマットは維持（JSON形式はオプション）

### 4.2 本番環境での段階的導入
- Phase 1を最初に実装し、動作確認後にPhase 2へ
- Phase 3は必要に応じて段階的に導入
- 各フェーズで十分なテストを実施

### 4.3 ログファイルの権限設定
- ログファイルは`ubuntu`ユーザー所有で作成
- 読み取り権限は適切に設定（`chmod 644`）
- 機密情報がログに出力されないよう注意

### 4.4 ディスク容量の監視
- ログファイルのサイズを定期的に監視
- logrotate設定が正しく動作しているか確認
- ディスク使用率が80%を超えた場合は警告

### 4.5 ログの機密情報対策
- APIキー、パスワード、トークンなどの機密情報をログに出力しない
- 必要に応じてマスキング処理を実装
- ログファイルのアクセス権限を適切に設定

---

## 5. 環境変数の追加

以下の環境変数を`env.example`に追加：

```bash
# ログ設定
LOG_LEVEL=INFO                    # ログレベル（DEBUG, INFO, WARNING, ERROR）
LOG_FILE=morizo_ai.log           # ログファイル名
LOG_DIR=.                        # ログディレクトリ（本番環境では /opt/morizo/Morizo-aiv2）
LOG_FORMAT=text                  # ログ形式（text または json）
LOG_TO_JOURNAL=false             # systemdジャーナルへの出力（true/false）
ENVIRONMENT=production           # 環境（production, development, staging）
SLOW_REQUEST_THRESHOLD=1.0       # スロークエリの閾値（秒）
```

---

## 6. 本番環境でのログファイル構成

本番環境（`/opt/morizo/Morizo-aiv2/`）でのログファイル構成：

```
/opt/morizo/Morizo-aiv2/
├── morizo_ai.log                    # 通常ログ（INFO以上）
├── morizo_ai.log.1                  # ローテーション済み（圧縮）
├── morizo_ai.log.2.gz
├── ...
├── morizo_ai_error.log              # エラーログ（ERROR/CRITICAL）
├── morizo_ai_error.log.1.gz
├── ...
├── morizo_ai_security.log           # セキュリティログ（Phase 3）
├── morizo_ai_security.log.1.gz
├── ...
├── morizo_ai_performance.log        # パフォーマンスログ（Phase 3）
└── morizo_ai_performance.log.1.gz
```

---

## 7. ログ確認コマンド

### 7.1 通常ログの確認
```bash
# リアルタイムでログを確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai.log

# 最新100行を表示
tail -n 100 /opt/morizo/Morizo-aiv2/morizo_ai.log

# エラーログのみを確認
tail -f /opt/morizo/Morizo-aiv2/morizo_ai_error.log
```

### 7.2 systemdログの確認
```bash
# リアルタイムでログを確認
sudo journalctl -u morizo-aiv2 -f

# 最新100行を表示
sudo journalctl -u morizo-aiv2 -n 100

# エラーログのみを確認
sudo journalctl -u morizo-aiv2 -p err
```

### 7.3 ログの検索
```bash
# 特定の文字列を含むログを検索
grep "ERROR" /opt/morizo/Morizo-aiv2/morizo_ai.log

# 特定のユーザーのログを検索
grep "user_id=xxx" /opt/morizo/Morizo-aiv2/morizo_ai.log

# 特定の日時のログを検索
grep "2024-01-01" /opt/morizo/Morizo-aiv2/morizo_ai.log
```

---

## 8. 関連ドキュメント

- [本番環境移行計画書](./PRODUCTION_DEPLOYMENT_PLAN.md)
- [ロギング戦略（アーカイブ）](./archive/rebuild/03_LOGGING_STRATEGY.md)
- [README](../README.md)

---

## 9. 更新履歴

- 2024-XX-XX: 初版作成
- 2025-11-15: Phase 0（DEBUGログ出力修正）完了
- 2025-11-15: ログレベル分類作業完了
  - 優先度1（API層）: 完了（`api/routes/recipe.py`、`api/routes/health.py`等）
  - 優先度2（MCP層）: 完了（`mcp_servers/inventory_mcp.py`、`recipe_mcp.py`、`recipe_history_mcp.py`等）
  - 優先度3（Service層）: 完了（`services/session/help_state_manager.py`等）
  - 優先度4（Core層）: 完了（`core/executor.py`、`core/agent.py`、`core/planner.py`等）
  - 修正ファイル数: 10ファイル、修正箇所数: 約25箇所

---

## 10. 補足説明

### 10.1 ログローテーションについて

**アプリケーションレベルのローテーション**:
- Pythonの`RotatingFileHandler`を使用
- ファイルサイズが10MBを超えると自動ローテーション
- 最大5つのバックアップファイルを保持

**OSレベルのローテーション**:
- `logrotate`を使用（Phase 1で実装）
- 日次でローテーション
- 30日間保持、圧縮、古いログの自動削除

両方のローテーションが動作する場合、`logrotate`が優先されます。

### 10.2 ログ形式について

**テキスト形式（デフォルト）**:
- 人間が読みやすい形式
- 既存のツール（`grep`、`tail`等）で検索可能
- ログ分析ツールとの連携は困難

**JSON形式（オプション）**:
- 機械が読みやすい形式
- ログ分析ツール（CloudWatch、ELK等）との連携が容易
- 構造化されたデータとして扱える

本番環境では、必要に応じてJSON形式に切り替えることを推奨します。

### 10.3 ログレベルの使い分け

- **DEBUG**: 開発時の詳細な情報（本番環境では出力しない）
- **INFO**: 通常の動作情報（リクエスト、レスポンス等）
- **WARNING**: 警告情報（非致命的な問題）
- **ERROR**: エラー情報（処理が失敗した場合）
- **CRITICAL**: 致命的なエラー（アプリケーションが停止する可能性）

本番環境では、INFO以上のみを出力することを推奨します。

---

## 11. ログレベル分類基準

### 11.1 概要

本番環境での適切なログ出力を実現するため、既存のログをINFOとDEBUGに分類し直します。
この分類基準に基づいて、コードベース全体のログ出力を段階的に修正します。

### 11.2 分類基準

#### INFOレベル（本番環境でも出力）

**リクエスト受信・処理開始**
- エンドポイントへのリクエスト受信（詳細パラメータを含めても可）
- 例: `logger.info(f"🔍 [API] Inventory list request received: sort_by={sort_by}")`
- **注意**: 詳細パラメータを分離して2行にする必要はない（ログ行数が増えるだけ）

**認証成功**
- 認証成功メッセージ（user_idは含める）
- 例: `logger.info(f"✅ [API] Authenticated client created for user: {user_id}")`

**処理完了・成功**
- 処理の成功メッセージ（IDや件数を含めても可）
- 例: `logger.info(f"✅ [API] Inventory item added: {item_id}")`
- 例: `logger.info(f"✅ [API] Retrieved {count} items")`
- **注意**: IDや件数を分離して2行にする必要はない（ログ行数が増えるだけ）

**重要な状態変化**
- システムの重要な状態変化
- エラー発生時のエラーメッセージ

#### DEBUGレベル（開発環境のみ出力）

**詳細な変数の値**
- user_id、item_id、mapping_idなどの識別子（認証成功ログのuser_idを除く）
- ファイル名、パラメータの詳細値
- 例: `logger.debug(f"🔍 [API] User ID: {user_id}")`
- 例: `logger.debug(f"🔍 [API] Item ID: {item_id}")`
- 例: `logger.debug(f"🔍 [API] Filename: {file.filename}")`

**中間処理の詳細**
- データ変換、マッピング適用などの中間処理
- 例: `logger.debug(f"✅ [API] Applied item mappings to {len(items)} items")`

**データ構造の内容**
- JSON、リスト、辞書などのデータ構造の詳細
- 例: `logger.debug(f"📊 [INVENTORY] List result: {result}")`

**条件分岐の詳細**
- 条件分岐の判定結果、ループ処理の詳細

**件数・統計情報**
- 取得件数、処理件数などの統計情報
- 例: `logger.debug(f"🔍 [API] Retrieved {len(result.get('data', []))} items")`

### 11.3 分類の具体例

#### 例1: リクエスト受信ログ（修正しない）

**現在:**
```python
logger.info(f"🔍 [API] Inventory list request received: sort_by={sort_by}, sort_order={sort_order}")
```

**修正後:**
```python
# 変更なし（詳細パラメータを分離するとログ行数が増えるだけ）
logger.info(f"🔍 [API] Inventory list request received: sort_by={sort_by}, sort_order={sort_order}")
```

#### 例2: 認証成功ログ（修正しない）

**現在:**
```python
logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
```

**修正後:**
```python
# 変更なし（user_idは認証成功ログに重要なのでINFOに残す）
logger.info(f"✅ [API] Authenticated client created for user: {user_id}")
```

#### 例3: 処理完了ログ（修正しない）

**現在:**
```python
logger.info(f"✅ [API] Inventory item added: {item_id}")
```

**修正後:**
```python
# 変更なし（IDを分離するとログ行数が増えるだけ）
logger.info(f"✅ [API] Inventory item added: {item_id}")
```

#### 例4: 件数ログ（修正しない）

**現在:**
```python
logger.info(f"✅ [API] Retrieved {len(result.get('data', []))} inventory items")
```

**修正後:**
```python
# 変更なし（件数を分離するとログ行数が増えるだけ）
logger.info(f"✅ [API] Retrieved {len(result.get('data', []))} inventory items")
```

#### 例5: user_idログ（修正する）

**修正前:**
```python
logger.info(f"🔍 [API] User ID: {user_id}")
```

**修正後:**
```python
logger.debug(f"🔍 [API] User ID: {user_id}")
```

#### 例6: データ構造の詳細（修正する）

**修正前:**
```python
logger.info(f"📊 [INVENTORY] List result: {result}")
```

**修正後:**
```python
logger.debug(f"📊 [INVENTORY] List result: {result}")
```

#### 例7: 中間処理の詳細（修正する）

**修正前:**
```python
logger.info(f"✅ [API] Applied item mappings to {len(items)} items")
```

**修正後:**
```python
logger.debug(f"✅ [API] Applied item mappings to {len(items)} items")
```

### 11.4 分類作業の進め方

1. **優先順位の高い層から開始**
   - API層（`api/routes/`, `api/middleware/`）
   - MCP層（`mcp_servers/`）
   - Service層（`services/`）
   - Core層（`core/`）

2. **ファイル単位で分類**
   - 1ファイルずつ確認・分類・修正
   - 修正後、動作確認

3. **作業プランの提示**
   - 各ファイルについて以下を提示:
     - 修正箇所（ファイル名、行番号、関数名）
     - 修正内容（INFO/DEBUGの変更）
     - 修正理由
     - 修正の影響

### 11.5 注意事項

- **認証成功ログのuser_id**: 認証成功ログにはuser_idを含める（INFOレベル）
- **エラーログ**: ERRORレベルは変更しない
- **警告ログ**: WARNINGレベルは変更しない
- **後方互換性**: 既存の動作に影響を与えないよう注意
- **ログ行数の増加を避ける**: 詳細パラメータ、ID、件数を分離して2行にする必要はない（ログ行数が増えるだけ）

### 11.6 サンプルファイル

分類基準の確認のため、`api/routes/inventory.py`をサンプルとして分類済み。
この基準に基づいて、他のファイルも同様に分類する。

