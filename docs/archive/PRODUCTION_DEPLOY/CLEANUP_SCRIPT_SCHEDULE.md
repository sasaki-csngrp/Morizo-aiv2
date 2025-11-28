# 古いレシピ履歴削除スクリプトのスケジュール化

## 概要

`scripts/cleanup_old_recipe_history.py`を本番環境で定期実行するための設定手順です。

## 前提条件

- 本番環境のユーザー: `sasaki`
- 作業ディレクトリ: `/opt/morizo/Morizo-aiv2`
- 仮想環境: `/opt/morizo/Morizo-aiv2/venv`
- `.env`ファイルに`SUPABASE_SERVICE_ROLE_KEY`が設定されていること

## 方法1: systemd timer（推奨）

systemd timerを使用することで、既存のsystemdサービスと統合しやすく、ログ管理も統一できます。

### 1.1 systemdサービスファイルの作成

```bash
# systemdサービスファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-aiv2-cleanup.service
```

以下を記述：

```ini
[Unit]
Description=Morizo AI v2 - Cleanup Old Recipe History
After=network.target

[Service]
Type=oneshot
User=sasaki
WorkingDirectory=/opt/morizo/Morizo-aiv2
Environment="PATH=/opt/morizo/Morizo-aiv2/venv/bin"
ExecStart=/opt/morizo/Morizo-aiv2/venv/bin/python /opt/morizo/Morizo-aiv2/scripts/cleanup_old_recipe_history.py

# ログ設定
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morizo-aiv2-cleanup
```

### 1.2 systemdタイマーファイルの作成

```bash
# systemdタイマーファイルの作成（sudo権限が必要）
sudo vi /etc/systemd/system/morizo-aiv2-cleanup.timer
```

以下を記述：

```ini
[Unit]
Description=Run Morizo AI v2 Cleanup Script Daily
Requires=morizo-aiv2-cleanup.service

[Timer]
# 毎日午前3時に実行（JST）
OnCalendar=*-*-* 03:00:00
# タイムゾーンをJSTに設定（システムのタイムゾーンがJSTの場合）
# OnCalendar=*-*-* 03:00:00 Asia/Tokyo
Persistent=true

[Install]
WantedBy=timers.target
```

**実行スケジュールの例**:
- `OnCalendar=*-*-* 03:00:00` - 毎日午前3時
- `OnCalendar=Mon *-*-* 03:00:00` - 毎週月曜日の午前3時
- `OnCalendar=*-*-01 03:00:00` - 毎月1日の午前3時
- `OnCalendar=*-*-* 03:00:00` + `OnUnitActiveSec=1d` - 前回実行から24時間後（初回は指定時刻）

### 1.3 systemdタイマーの有効化と起動

```bash
# systemd設定のリロード（sudo権限が必要）
sudo systemctl daemon-reload

# タイマーの有効化（自動起動設定、sudo権限が必要）
sudo systemctl enable morizo-aiv2-cleanup.timer

# タイマーの起動（sudo権限が必要）
sudo systemctl start morizo-aiv2-cleanup.timer

# タイマーの状態確認（sudo権限が必要）
sudo systemctl status morizo-aiv2-cleanup.timer

# 次回実行時刻の確認（sudo権限が必要）
sudo systemctl list-timers morizo-aiv2-cleanup.timer
```

### 1.4 ログの確認

```bash
# サービスの実行ログを確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2-cleanup.service -n 50

# リアルタイムでログを確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2-cleanup.service -f

# タイマーのログを確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2-cleanup.timer -n 50
```

### 1.5 手動実行（テスト用）

```bash
# サービスを手動で実行（sudo権限が必要）
sudo systemctl start morizo-aiv2-cleanup.service

# 実行結果を確認（sudo権限が必要）
sudo journalctl -u morizo-aiv2-cleanup.service -n 50
```

### 1.6 タイマーの停止・無効化

```bash
# タイマーを停止（sudo権限が必要）
sudo systemctl stop morizo-aiv2-cleanup.timer

# タイマーを無効化（自動起動を解除、sudo権限が必要）
sudo systemctl disable morizo-aiv2-cleanup.timer
```

---

## 方法2: cron（代替案）

cronを使用する方法です。シンプルですが、systemdとログ管理が分離されます。

### 2.1 crontabの編集

```bash
# sasakiユーザーでcrontabを編集
crontab -e
```

以下を追加：

```cron
# 毎日午前3時に実行（JST）
0 3 * * * /opt/morizo/Morizo-aiv2/venv/bin/python /opt/morizo/Morizo-aiv2/scripts/cleanup_old_recipe_history.py >> /opt/morizo/Morizo-aiv2/logs/cleanup.log 2>&1
```

**cronスケジュールの例**:
- `0 3 * * *` - 毎日午前3時
- `0 3 * * 1` - 毎週月曜日の午前3時
- `0 3 1 * *` - 毎月1日の午前3時

### 2.2 ログディレクトリの作成（必要に応じて）

```bash
# ログディレクトリを作成（sasakiユーザーで実行）
mkdir -p /opt/morizo/Morizo-aiv2/logs

# ログファイルの権限を確認
ls -la /opt/morizo/Morizo-aiv2/logs/
```

### 2.3 cronの確認

```bash
# 現在のcrontabを確認
crontab -l

# cronサービスの状態確認（sudo権限が必要）
sudo systemctl status cron
```

---

## 推奨設定

### 実行頻度

- **推奨**: 毎日1回（午前3時など、アクセスが少ない時間帯）
- **理由**: 30日以上経過したデータを定期的に削除するため、毎日実行することでデータベースの負荷を分散

### タイムゾーン

本番環境のタイムゾーンがJST（Asia/Tokyo）に設定されていることを確認：

```bash
# タイムゾーンの確認
timedatectl

# タイムゾーンをJSTに設定（必要に応じて、sudo権限が必要）
sudo timedatectl set-timezone Asia/Tokyo
```

### ログ管理

systemd timerを使用する場合、ログは`journalctl`で確認できます。必要に応じて、ログローテーションの設定も検討してください。

---

## トラブルシューティング

### スクリプトが実行されない

1. **環境変数の確認**
   ```bash
   # sasakiユーザーで実行
   cd /opt/morizo/Morizo-aiv2
   source venv/bin/activate
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('SUPABASE_URL:', 'SET' if os.getenv('SUPABASE_URL') else 'NOT SET'); print('SUPABASE_SERVICE_ROLE_KEY:', 'SET' if os.getenv('SUPABASE_SERVICE_ROLE_KEY') else 'NOT SET')"
   ```

2. **スクリプトの実行権限確認**
   ```bash
   ls -la /opt/morizo/Morizo-aiv2/scripts/cleanup_old_recipe_history.py
   ```

3. **手動実行でテスト**
   ```bash
   # sasakiユーザーで実行
   cd /opt/morizo/Morizo-aiv2
   source venv/bin/activate
   python scripts/cleanup_old_recipe_history.py
   ```

### タイマーが実行されない

1. **タイマーの状態確認**
   ```bash
   sudo systemctl status morizo-aiv2-cleanup.timer
   ```

2. **次回実行時刻の確認**
   ```bash
   sudo systemctl list-timers morizo-aiv2-cleanup.timer
   ```

3. **タイマーのログ確認**
   ```bash
   sudo journalctl -u morizo-aiv2-cleanup.timer -n 50
   ```

### ログが出力されない

1. **journalctlで確認**
   ```bash
   sudo journalctl -u morizo-aiv2-cleanup.service -n 100
   ```

2. **システムログの確認**
   ```bash
   sudo journalctl -n 100 | grep morizo-aiv2-cleanup
   ```

---

## セキュリティチェックリスト

- [ ] `.env`ファイルに`SUPABASE_SERVICE_ROLE_KEY`が設定されている
- [ ] `.env`ファイルの権限が適切に設定されている（`chmod 600`）
- [ ] スクリプトが`sasaki`ユーザーで実行されることを確認
- [ ] タイマーが有効化されていることを確認
- [ ] ログが適切に出力されていることを確認

---

## 参考

- [systemd timer の使い方](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
- [cron の使い方](https://manpages.ubuntu.com/manpages/jammy/man5/crontab.5.html)

