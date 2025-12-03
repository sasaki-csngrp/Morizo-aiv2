# iOSレビュー却下対応 修正プラン

## 概要

2025年11月28日のiOSアプリレビューで5つの問題が指摘されました。本ドキュメントは、各問題に対する修正プランを記載しています。

**提出ID**: 11cd5ea8-ed87-47eb-a3d0-02c60f2aff69  
**レビュー日**: 2025年11月28日  
**レビュー対象バージョン**: 1.0

---

## 問題1: ガイドライン 4.8 - Sign in with Apple の実装

### 問題の詳細
アプリはサードパーティのログインサービス（Google）を使用していますが、以下のすべての機能を備えた同等のログインオプションとして別のログインサービスを提供していません：
- ログインオプションは、ユーザーの名前とメールアドレスにデータ収集を制限します
- ログインオプションは、アカウント設定の一環として、ユーザーがすべての当事者からメールアドレスを非公開にできるようにします
- ログインオプションは、同意なしに広告目的でアプリとの相互作用を収集しません

**Sign in with Appleは、ガイドライン4.8で指定されたすべての要件を満たすログインサービスです。**

### 修正する場所

#### モバイル側（コード修正）
1. `/app/Morizo-mobile/lib/auth/apple-auth.ts` (新規作成)
2. `/app/Morizo-mobile/lib/auth/index.ts` (Sign in with Appleのエクスポート追加)
3. `/app/Morizo-mobile/lib/auth/auth-methods.ts` (Sign in with Apple関数の追加)
4. `/app/Morizo-mobile/contexts/AuthContext.tsx` (Sign in with Appleメソッドの追加)
5. `/app/Morizo-mobile/screens/LoginScreen.tsx` (Sign in with Appleボタンの追加)
6. `/app/Morizo-mobile/package.json` (expo-apple-authentication依存関係の追加)

#### Supabase側（設定のみ、コード修正不要）
- Supabase Dashboard > Authentication > Providers > Apple
  - Apple認証プロバイダーを有効化
  - Service ID、Key ID、Team IDを設定

#### Apple Developer Console側（設定のみ、コード修正不要）
- Apple Developer Consoleで以下を設定：
  - Service IDの作成
  - Key IDの作成
  - リダイレクトURLの設定

### 修正する内容
- `expo-apple-authentication`パッケージを追加
- Sign in with Appleの認証関数を実装
  - Apple ID認証の開始
  - 認証トークンの取得
  - Supabase Authとの統合
- LoginScreenにSign in with Appleボタンを追加
  - Google認証ボタンの下に配置
  - Appleのデザインガイドラインに準拠したボタンデザイン
- AuthContextにSign in with Appleメソッドを追加
  - `signInWithApple`メソッドの実装
  - 認証状態の管理

### 修正の理由
ガイドライン4.8により、サードパーティログイン（Google）に加えて、Sign in with Appleなどの同等オプションを提供する必要があります。

### 修正の影響
- **新規機能追加のため、既存の認証フローへの影響は最小限**
- **モバイル側のコード修正のみでは完了しない**
  - Supabase Dashboardでの設定が必要（コード修正不要）
  - Apple Developer Consoleでの設定が必要（コード修正不要）
- iOS実機でのテストが必要（シミュレーターでは動作しない可能性）

### 注意事項
**重要**: 問題1は、モバイル側のコード修正だけでは対応できません。以下の設定も必要です：

1. **Apple Developer Consoleでの設定**（必須）
   - App IDでSign In with Appleを有効化
   - Service IDの作成と設定
   - Key IDの作成とKeyファイル（.p8）のダウンロード
   - リダイレクトURLの設定

2. **Supabase Dashboardでの設定**（必須）
   - Apple認証プロバイダーを有効化
   - Service ID、Key ID、Team ID、Secret Key（.p8ファイルの内容）を設定

**詳細な設定手順は、別ドキュメント「[Sign in with Apple 設定手順書](./IOS_SIGN_IN_WITH_APPLE_SETUP.md)」を参照してください。**

### 実装の詳細

**詳細な実装手順は、別ドキュメント「[Sign in with Apple 設定手順書](./IOS_SIGN_IN_WITH_APPLE_SETUP.md)」を参照してください。**

#### 概要
1. **Apple Developer Consoleでの設定**（約30分）
   - App IDの確認・設定
   - Service IDの作成
   - Key IDの作成とKeyファイル（.p8）のダウンロード
   - リダイレクトURLの設定

2. **Supabase Dashboardでの設定**（約10分）
   - Apple認証プロバイダーの有効化
   - Apple Developer Consoleで取得した情報の設定

3. **モバイルアプリ側の実装**（約2-4時間）
   - `expo-apple-authentication`パッケージのインストール
   - 認証関数の実装（`apple-auth.ts`）
   - UIの追加（LoginScreenにボタン追加）

---

## 問題2: ガイドライン 5.1.1 - マイクの目的文字列が不十分

### 問題の詳細
アプリ内のマイクの目的文字列が、保護されたリソースの使用を十分に説明していません。目的文字列は、アプリのデータの使用を明確かつ完全に説明し、ほとんどの場合、データの使用方法の例を提供する必要があります。

### 修正する場所
- `/app/Morizo-mobile/app.json` (infoPlistにNSMicrophoneUsageDescriptionを追加)

### 修正する内容
```json
"ios": {
  "infoPlist": {
    "ITSAppUsesNonExemptEncryption": false,
    "NSMicrophoneUsageDescription": "音声入力でレシピの相談や在庫管理を行うためにマイクへのアクセスが必要です。例えば、「冷蔵庫に何がある？」と話しかけることで、音声で在庫を確認できます。"
  }
}
```

### 修正の理由
マイクの目的文字列が不足しており、使用方法の説明と具体例が必要です。

### 修正の影響
- iOSビルド時にInfo.plistに反映されます
- 既存のマイク使用コード（`useVoiceRecording.ts`）への影響はありません
- ユーザーが初めてマイクアクセスを許可する際に、この説明が表示されます

---

## 問題3: ガイドライン 4.0 - 権限リクエストのローカライゼーション

### 問題の詳細
アプリの権限リクエストは、アプリの日本語ローカライゼーションと同じ言語で記述されていません。ユーザーがアプリが特定の機能へのアクセスを要求している理由を理解できるように、アプリの権限リクエストは、アプリの現在のローカライゼーションと同じ言語である必要があります。

### 修正する場所
- `/app/Morizo-mobile/app.json` (infoPlistに日本語の目的文字列を追加)

### 修正する内容
- 問題2で追加する`NSMicrophoneUsageDescription`を日本語で記述することで、この問題も同時に解決されます

### 修正の理由
権限リクエストが日本語ローカライゼーションと一致していません。

### 修正の影響
- 問題2と同じ修正で対応可能です
- 他の権限（カメラ、写真ライブラリなど）も使用している場合は、同様に日本語の目的文字列を追加する必要があります

---

## 問題4: ガイドライン 5.1.1(v) - アカウント削除機能の実装

### 問題の詳細
アプリはアカウント作成をサポートしていますが、アカウント削除を開始するオプションが含まれていません。アカウント作成をサポートするアプリは、ユーザーがアプリを使用している間に共有したデータをより制御できるように、アカウント削除も提供する必要があります。

**要件:**
- アカウントを一時的に非アクティブ化または無効化するだけでは不十分
- ユーザーがアカウントの削除を完了するためにウェブサイトにアクセスする必要がある場合は、プロセスを完了できるウェブサイトページへの直接リンクを含める
- アプリには、ユーザーが誤ってアカウントを削除するのを防ぐための確認ステップを含めることができる
- 厳しく規制されている業界のアプリのみが、アカウント削除を完了するために、電話をかけるまたはメールを送信するなどのカスタマーサービスリソースの使用をユーザーに要求できる

### 修正する場所
1. `/app/Morizo-aiv2/api/routes/user.py` (新規作成)
2. `/app/Morizo-aiv2/api/main.py` (userルーターの登録)
3. `/app/Morizo-web/app/api/user/account/route.ts` (新規作成) - **ウェブアプリのAPIルート**
4. `/app/Morizo-mobile/api/user-api.ts` (新規作成)
5. `/app/Morizo-mobile/components/UserProfileModal.tsx` (アカウント削除ボタンと確認モーダルの追加)
6. `/app/Morizo-mobile/contexts/AuthContext.tsx` (アカウント削除メソッドの追加)

### 修正する内容

#### アーキテクチャ
本アプリのアーキテクチャは以下の通りです：
- **mobile（モバイル）** → **web（フロント）** → **ai（バックエンド）**

したがって、アカウント削除機能もこの3層構造に従って実装します。

#### バックエンド実装（AI層）
- **新規APIエンドポイント**: `DELETE /api/user/account`
  - 認証済みユーザーのアカウントを削除
  - Supabase Authのユーザー削除機能を使用
  - 関連データの削除処理
    - 在庫データ（`inventory`テーブル）
    - レシピ履歴（`recipe_historys`テーブル）
    - ユーザー設定（`user_settings`テーブル）
    - OCRマッピング（`ocr_item_mappings`テーブル）
  - データベースのCASCADE削除設定により、関連データは自動削除される想定

#### ウェブアプリ実装（Web層）
- **新規APIルート**: `/app/api/user/account/route.ts`
  - Next.js APIルートとして実装
  - モバイルアプリからのリクエストを受信
  - 認証チェック（`authenticateRequest`を使用）
  - バックエンドAI（`MORIZO_AI_URL`）にリクエストを転送
  - レスポンスをモバイルアプリに返却
  - CORSヘッダーの設定
  - ログ記録

#### モバイルアプリ実装（Mobile層）
- **UserProfileModalの拡張**
  - アカウント削除ボタンを追加（ログアウトボタンの下に配置）
  - 確認ダイアログを実装（誤削除防止）
    - 警告メッセージの表示
    - 「削除する」と入力する必要がある確認ステップ（オプション）
  - 削除処理の実装
    - API呼び出し
    - 削除成功後のログアウト処理
    - エラーハンドリング

- **AuthContextの拡張**
  - `deleteAccount`メソッドの実装
  - 削除後の状態管理

### 修正の理由
アカウント作成をサポートするアプリは、アカウント削除も提供する必要があります。

### 修正の影響
- **新規機能追加のため、既存機能への影響は最小限**
- データベースのCASCADE削除設定により、関連データは自動削除される想定
- 削除は不可逆のため、確認ステップを必須とする
- 削除処理は慎重に実装し、誤削除を防ぐ仕組みを設ける

### 実装の詳細

#### バックエンドAPI仕様（AI層）
```python
@router.delete("/user/account")
async def delete_user_account(http_request: Request):
    """
    ユーザーアカウントを削除
    
    - 認証済みユーザーのみ実行可能
    - Supabase Authのユーザー削除を実行
    - 関連データはCASCADE削除で自動削除
    """
```

#### ウェブアプリAPI仕様（Web層）
```typescript
// /app/api/user/account/route.ts
export async function DELETE(request: NextRequest) {
  // 1. 認証チェック（authenticateRequest）
  // 2. バックエンドAIにリクエスト転送（authenticatedMorizoAIRequest）
  // 3. レスポンスを返却
}
```

#### モバイルアプリAPI仕様（Mobile層）
```typescript
// user-api.ts
export const deleteUserAccount = async (): Promise<{ success: boolean; error?: string }> => {
  // DELETE /api/user/account を呼び出し（ウェブアプリのAPIルート）
  // authenticatedFetchを使用して認証付きリクエストを送信
}
```

#### UIフロー
1. UserProfileModalで「アカウントを削除」ボタンをタップ
2. 確認ダイアログを表示
   - 警告メッセージ：「この操作は取り消せません。すべてのデータが削除されます。」
   - 「削除する」ボタンと「キャンセル」ボタン
3. 「削除する」をタップ
4. API呼び出し
5. 削除成功後、ログアウト処理を実行
6. LoginScreenに遷移

---

## 問題5: ガイドライン 1.5 - サポートURLが機能していない

### 問題の詳細
App Store Connectで提供されたサポートURL、https://www.csngrp.co.jp/は、ユーザーが質問をしたりサポートを依頼したりするために使用できる情報を含むウェブサイトにリンクしていません。

### 修正する場所
- **App Store Connectの設定**（コード修正不要）

### 修正する内容
App Store Connectで、サポートURL（https://www.csngrp.co.jp/）を、実際にサポート情報が掲載されているページに更新します。

例:
- https://www.csngrp.co.jp/support
- https://www.csngrp.co.jp/contact
- または、サポート情報を含む適切なページ

### 修正の理由
サポートURLが機能していません。

### 修正の影響
- **コード修正不要**（App Store Connectの設定変更のみ）
- サポートページが存在しない場合は、新規作成が必要

---

## 実装優先順位

1. **問題2・3（マイク目的文字列）**: 最も簡単で即座に対応可能
   - 修正時間: 約10分
   - リスク: 低

2. **問題1（Sign in with Apple）**: 実装に時間がかかる可能性
   - 修正時間: 2-4時間
   - リスク: 中
   - 依存関係: Supabase設定、Apple Developer設定

3. **問題4（アカウント削除）**: バックエンドとフロントエンドの両方の実装が必要
   - 修正時間: 3-5時間
   - リスク: 中
   - 注意: 削除処理は慎重に実装

4. **問題5（サポートURL）**: コード修正不要
   - 修正時間: 5-10分（ページ作成が必要な場合は追加時間）
   - リスク: 低

---

## 実装チェックリスト

### 問題1: Sign in with Apple
#### モバイル側（コード修正）
- [ ] `expo-apple-authentication`パッケージをインストール
- [ ] `apple-auth.ts`を作成
- [ ] `auth-methods.ts`にSign in with Apple関数を追加
- [ ] `AuthContext.tsx`にSign in with Appleメソッドを追加
- [ ] `LoginScreen.tsx`にSign in with Appleボタンを追加

#### Supabase側（設定のみ）
- [ ] Apple Developer ConsoleでService ID、Key ID、Team IDを取得
- [ ] Supabase DashboardでApple認証を有効化
- [ ] Supabase DashboardにService ID、Key ID、Team IDを設定

#### Apple Developer Console側（設定のみ）
- [ ] Service IDの作成
- [ ] Key IDの作成
- [ ] リダイレクトURLの設定

#### テスト
- [ ] iOS実機でテスト（シミュレーターでは動作しない可能性）

### 問題2・3: マイク目的文字列
- [ ] `app.json`の`infoPlist`に`NSMicrophoneUsageDescription`を追加
- [ ] 日本語で使用方法と具体例を記述
- [ ] iOSビルドで確認

### 問題4: アカウント削除
- [ ] バックエンド（AI層）: `api/routes/user.py`を作成
- [ ] バックエンド（AI層）: `api/main.py`にuserルーターを登録
- [ ] ウェブアプリ（Web層）: `app/api/user/account/route.ts`を作成
- [ ] モバイルアプリ（Mobile層）: `api/user-api.ts`を作成
- [ ] モバイルアプリ（Mobile層）: `UserProfileModal.tsx`にアカウント削除UIを追加
- [ ] モバイルアプリ（Mobile層）: `AuthContext.tsx`にアカウント削除メソッドを追加
- [ ] 確認ダイアログの実装
- [ ] エラーハンドリングの実装
- [ ] テスト: アカウント削除フローの動作確認（mobile → web → ai）

### 問題5: サポートURL
- [ ] サポートページの作成（必要に応じて）
- [ ] App Store ConnectでサポートURLを更新

---

## 注意事項

1. **承認が必要**: すべての修正は、承認を得てから実装してください
2. **段階的実装**: 優先順位に従って、段階的に実装を進めてください
3. **テスト**: 各修正後、必ずテストを実施してください
4. **バックアップ**: 重要な変更前には、バックアップを取得してください
5. **ドキュメント更新**: 実装後、関連ドキュメントを更新してください

---

## 参考資料

- [iOS App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [Sign in with Apple](https://developer.apple.com/sign-in-with-apple/)
- [Expo Apple Authentication](https://docs.expo.dev/versions/latest/sdk/apple-authentication/)
- [Supabase Auth - Apple Provider](https://supabase.com/docs/guides/auth/social-login/auth-apple)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)

---

**作成日**: 2025年11月28日  
**最終更新**: 2025年11月28日

