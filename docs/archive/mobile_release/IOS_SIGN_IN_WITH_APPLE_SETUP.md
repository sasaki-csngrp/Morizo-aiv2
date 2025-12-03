# Sign in with Apple 設定手順書

## 概要

本ドキュメントは、iOSアプリにSign in with Apple機能を実装するための詳細な設定手順を記載しています。

**対象**: 問題1（ガイドライン 4.8 - Sign in with Apple の実装）の対応

---

## 前提条件

- Apple Developerアカウント（有料メンバーシップ）
- Supabaseプロジェクトへのアクセス権限
- iOSアプリのBundle IDが確定していること

---

## 設定手順の全体フロー

1. **Apple Developer Consoleでの設定**（約30分）
   - App IDの設定
   - Service IDの作成
   - Key IDの作成
   - リダイレクトURLの設定

2. **Supabase Dashboardでの設定**（約10分）
   - Apple認証プロバイダーの有効化
   - Apple Developer Consoleで取得した情報の設定

3. **モバイルアプリ側の実装**（約2-4時間）
   - パッケージのインストール
   - 認証関数の実装
   - UIの追加

---

## ステップ1: Apple Developer Consoleでの設定

### 1.1 App IDの確認・設定

1. [Apple Developer Console](https://developer.apple.com/account/)にログイン
2. **Certificates, Identifiers & Profiles** を選択
3. **Identifiers** を選択
4. 既存のApp IDを検索、または新規作成
   - 既存のApp IDを使用する場合：
     - Bundle ID: `jp.co.csngrp.morizo`（`app.json`で確認）
     - 該当するApp IDを選択
   - 新規作成する場合：
     - **+** ボタンをクリック
     - **App IDs** を選択して **Continue**
     - **App** を選択して **Continue**
     - Description: `Morizo Mobile`
     - Bundle ID: `jp.co.csngrp.morizo`
     - **Capabilities** で **Sign In with Apple** にチェック
     - **Continue** → **Register**

5. App IDの詳細画面で、**Sign In with Apple** が有効になっていることを確認

### 1.2 Service IDの作成

1. **Identifiers** 画面で **+** ボタンをクリック
2. **Services IDs** を選択して **Continue**
3. 以下の情報を入力：
   - **Description**: `Morizo Sign In with Apple`
   - **Identifier**: 
     - 推奨: `jp.co.csngrp.morizo.signin`（逆ドメイン形式）
     - **重要**: このIdentifierは一意である必要があります
     - 既に使用されている場合は、別のIdentifierを使用してください
     - 例: `jp.co.csngrp.morizo.apple.signin` や `jp.co.csngrp.morizo.signin.apple`
     - Identifierの形式: 逆ドメイン形式（例: `com.example.service`）で、英数字、ピリオド（.）、ハイフン（-）が使用可能
     - 長さの制限: 最大100文字
4. **Continue** → **Register**

**注意**: Identifierでエラーが出る場合：
- **既に使用されているIdentifier**: 別のIdentifierを試してください
  - 例: `jp.co.csngrp.morizo.signin.apple`
  - 例: `jp.co.csngrp.morizo.apple.signin`
  - 例: `jp.co.csngrp.morizo.signin2`
- **形式エラー**: 逆ドメイン形式（例: `com.example.service`）を使用しているか確認
- **文字エラー**: 英数字、ピリオド（.）、ハイフン（-）のみ使用可能
- **長さエラー**: 100文字以内に収めているか確認

5. 作成したService IDを選択
6. **Sign In with Apple** にチェックを入れて **Configure** をクリック

**重要**: ここで「No App ID is available.」という警告が表示される場合があります。この場合は、以下の手順を先に実行してください：

1. **App IDの確認**: 1.1で作成したApp IDで、Sign In with Appleが有効になっているか確認
2. **App IDの再確認**: Apple Developer Consoleで、該当するApp IDを開き、**Sign In with Apple**が有効になっていることを確認
3. まだ有効になっていない場合は、App IDの編集画面で**Sign In with Apple**を有効化して保存

7. **Primary App ID** で、1.1で確認したApp IDを選択
   - **重要**: このドロップダウンにApp IDが表示されない場合、上記の手順を確認してください
   - App IDが表示されないと、「Next」ボタンが活性化しません

8. **Website URLs** セクションで：
   - **Domains and Subdomains**: `supabase.co`
     - **重要**: このフィールドは必須です。空欄のままでは「Next」ボタンが活性化しません
     - Supabaseのドメイン（`supabase.co`）を入力します
     - カンマ区切りで複数のドメインを入力することもできますが、通常は`supabase.co`のみでOKです
   - **Return URLs**: 
     ```
     https://[YOUR_SUPABASE_PROJECT_REF].supabase.co/auth/v1/callback
     ```
     - **重要**: このフィールドも必須です。空欄のままでは「Next」ボタンが活性化しません
     - `[YOUR_SUPABASE_PROJECT_REF]` は、Supabase Dashboardの **Settings** > **API** で確認できるProject URLから取得します
     - 確認方法：
       1. Supabase Dashboardにログイン
       2. 対象プロジェクトを選択
       3. **Settings** > **API** を選択
       4. **Project URL** を確認（例: `https://abcdefghijklmnop.supabase.co`）
     - Project URLが `https://abcdefghijklmnop.supabase.co` の場合、Return URLは: `https://abcdefghijklmnop.supabase.co/auth/v1/callback`
     - **重要**: このReturn URLは、Supabaseが提供する認証コールバックURLです
     - URLは完全な形式（`https://`から始まる）で入力してください
9. **Next** ボタンをクリック
   - **注意**: 「Next」ボタンが活性化しない場合の確認事項：
     1. **Primary App ID** が選択されているか確認
     2. **Domains and Subdomains** に `supabase.co` が入力されているか確認
     3. **Return URLs** に完全なURL（`https://`から始まる）が入力されているか確認
     4. すべての必須フィールドが正しく入力されていれば、「Next」ボタンが活性化します

10. 確認画面で内容を確認し、**Continue** → **Register** をクリック

### 1.3 Key IDの作成

1. **Certificates, Identifiers & Profiles** 画面で **Keys** を選択
2. **+** ボタンをクリック
3. 以下の情報を入力：
   - **Key Name**: `Morizo Sign In with Apple Key`
   - **Sign In with Apple** にチェックを入れる
4. **Configure** をクリック
5. **Primary App ID** で、1.1で確認したApp IDを選択
6. **Save** → **Continue** → **Register**

7. **重要**: ダウンロードボタンが表示されるので、**必ずKeyファイル（.p8）をダウンロードして安全な場所に保存**
   - このファイルは一度しかダウンロードできません
   - 失くした場合は、新しいKeyを作成する必要があります

8. **Key ID** をメモ（後でSupabaseに設定）

### 1.4 必要な情報のまとめ

以下の情報をメモしておきます（Supabase設定時に使用）：

- **Team ID**: Apple Developer Consoleの右上に表示される10文字の英数字
- **Service ID**: 1.2で作成したService ID（例: `jp.co.csngrp.morizo.signin`）
- **Key ID**: 1.3で作成したKey ID（10文字の英数字）
- **Keyファイル（.p8）**: 1.3でダウンロードしたファイル

---

## ステップ2: Supabase Dashboardでの設定

### 2.1 Supabaseプロジェクトにアクセス

1. [Supabase Dashboard](https://app.supabase.com/)にログイン
2. 対象のプロジェクトを選択

### 2.2 Apple認証プロバイダーを有効化

1. 左メニューから **Authentication** を選択
2. **Providers** タブを選択
3. **Apple** を検索またはスクロールして選択
4. **Enable Apple provider** トグルを **ON** にする

### 2.3 Apple認証の設定

以下の情報を入力します（1.4でメモした情報を使用）：

#### 必須項目

1. **Service ID**
   - 1.2で作成したService IDを入力
   - 例: `jp.co.csngrp.morizo.signin`

2. **Secret Key**
   - **重要**: Supabaseでは、.p8ファイルの内容をそのまま貼り付けるのではなく、**JWT形式で生成したトークン**を入力する必要があります
   - JWTを生成する方法（下記参照）

3. **Key ID**
   - 1.3で作成したKey IDを入力
   - 例: `ABC123DEF4`

4. **Team ID**
   - Apple Developer Consoleの右上に表示されるTeam IDを入力
   - 例: `XYZ987WUV6`

#### オプション項目

- **Authorized Client IDs**: 通常は空欄でOK
- **Authorized Domains**: 通常は空欄でOK

### 2.4 リダイレクトURLの確認

1. **Settings** > **API** を選択
2. **Project URL** を確認
   - 例: `https://abcdefghijklmnop.supabase.co`
3. このURLが、1.2で設定したReturn URLと一致していることを確認
   - Return URL: `https://abcdefghijklmnop.supabase.co/auth/v1/callback`

### 2.4 JWTの生成方法（Secret Key用）

SupabaseのSecret Keyには、.p8ファイルの内容ではなく、JWT形式で生成したトークンを入力する必要があります。

#### 必要な情報の確認

JWTを生成する前に、以下の情報を準備してください：

1. **YOUR_KEY_ID**（Key ID）:
   - **取得場所**: Apple Developer Console > **Certificates, Identifiers & Profiles** > **Keys**
   - **確認方法**: 1.3で作成したKeyの詳細画面で確認
   - **形式**: 10文字の英数字（例: `ABC123DEF4`）
   - **例**: `ABC123DEF4`

2. **YOUR_TEAM_ID**（Team ID）:
   - **取得場所**: Apple Developer Consoleの右上
   - **確認方法**: ログイン後の画面右上に表示される10文字の英数字
   - **形式**: 10文字の英数字（例: `XYZ987WUV6`）
   - **例**: `XYZ987WUV6`

3. **YOUR_SERVICE_ID**（Service ID）:
   - **取得場所**: Apple Developer Console > **Certificates, Identifiers & Profiles** > **Identifiers** > **Services IDs**
   - **確認方法**: 1.2で作成したService IDのIdentifier
   - **形式**: 逆ドメイン形式（例: `jp.co.csngrp.morizo.signin`）
   - **例**: `jp.co.csngrp.morizo.signin`

4. **.p8ファイル**:
   - **取得場所**: 1.3でダウンロードしたKeyファイル
   - **ファイル名**: `AuthKey_YOUR_KEY_ID.p8`（例: `AuthKey_ABC123DEF4.p8`）
   - **内容**: `-----BEGIN PRIVATE KEY-----` で始まるテキスト

#### 方法1: オンラインツールを使用（推奨）

1. [JWT.io](https://jwt.io/) などのオンラインツールを使用
2. 上記で確認した情報を準備：
   - **Key ID**: YOUR_KEY_ID（例: `ABC123DEF4`）
   - **Team ID**: YOUR_TEAM_ID（例: `XYZ987WUV6`）
   - **Service ID**: YOUR_SERVICE_ID（例: `jp.co.csngrp.morizo.signin`）
   - **.p8ファイル**: 1.3でダウンロードしたKeyファイル

3. JWTを生成：
   - **Header**:
     ```json
     {
       "alg": "ES256",
       "kid": "ABC123DEF4"
     }
     ```
     - `"kid"`には、上記で確認した**YOUR_KEY_ID**を入力（例: `ABC123DEF4`）
   
   - **Payload**:
     ```json
     {
       "iss": "XYZ987WUV6",
       "iat": 1701234567,
       "exp": 1717008567,
       "aud": "https://appleid.apple.com",
       "sub": "jp.co.csngrp.morizo.signin"
     }
     ```
     - `"iss"`: 上記で確認した**YOUR_TEAM_ID**を入力（例: `XYZ987WUV6`）
     - `"iat"`: 現在のUNIXタイムスタンプ（例: `1701234567`）
       - 現在時刻をUNIXタイムスタンプに変換: [Epoch Converter](https://www.epochconverter.com/)
     - `"exp"`: 有効期限のUNIXタイムスタンプ（`iat`から最大6ヶ月後、例: `1717008567`）
       - 6ヶ月 = 約15552000秒（60秒 × 60分 × 24時間 × 180日）
     - `"aud"`: 固定で `"https://appleid.apple.com"` を指定
     - `"sub"`: 上記で確認した**YOUR_SERVICE_ID**を入力（例: `jp.co.csngrp.morizo.signin`）
   
   - **Signature**: .p8ファイルを使用してES256アルゴリズムで署名
     - JWT.ioなどのツールで、.p8ファイルの内容を貼り付けて署名

#### 方法2: Node.jsスクリプトを使用（推奨 - 最も確実）

`jwt-cli`はES256アルゴリズムと.p8ファイルの扱いで問題が発生する可能性があるため、Node.jsスクリプトを使用することを推奨します。

以下のNode.jsスクリプトでJWTを生成できます：

```javascript
const jwt = require('jsonwebtoken');
const fs = require('fs');

// 実際の値に置き換えてください
const keyId = 'ABC123DEF4';        // YOUR_KEY_ID（1.3で確認したKey ID）
const teamId = 'XYZ987WUV6';       // YOUR_TEAM_ID（Apple Developer Console右上のTeam ID）
const serviceId = 'jp.co.csngrp.morizo.signin';  // YOUR_SERVICE_ID（1.2で作成したService ID）
const privateKeyPath = './AuthKey_ABC123DEF4.p8';  // .p8ファイルのパス（相対パスまたは絶対パス）

const privateKey = fs.readFileSync(privateKeyPath);

const now = Math.floor(Date.now() / 1000);
const token = jwt.sign(
  {
    iss: teamId,                    // YOUR_TEAM_ID
    iat: now,                        // 現在のUNIXタイムスタンプ
    exp: now + (86400 * 180),        // 6ヶ月後（180日 = 15552000秒）
    aud: 'https://appleid.apple.com',  // 固定値
    sub: serviceId,                  // YOUR_SERVICE_ID
  },
  privateKey,
  {
    algorithm: 'ES256',
    header: {
      alg: 'ES256',
      kid: keyId,                    // YOUR_KEY_ID
    },
  }
);

console.log('Generated JWT:');
console.log(token);
```

**必要なパッケージ**:
```bash
npm install jsonwebtoken
```

**使用方法**:
1. 上記のスクリプトを `generate-jwt.js` として保存
2. `keyId`、`teamId`、`serviceId`、`privateKeyPath`を実際の値に置き換える
3. .p8ファイルを同じディレクトリに配置（または絶対パスで指定）
4. 実行: `node generate-jwt.js`
5. 出力されたJWTをコピーしてSupabaseのSecret Keyに貼り付け

**注意**: 
- JWTの有効期限（exp）は最大6ヶ月です
- 有効期限が切れたら、新しいJWTを生成する必要があります

#### 方法3: オンラインツール（JWT.io）を使用

JWT.ioなどのオンラインツールを使用する場合、ES256アルゴリズムと.p8ファイルの扱いが複雑なため、Node.jsスクリプト（方法2）の使用を推奨します。

ただし、JWT.ioを使用する場合は：
1. [JWT.io](https://jwt.io/) にアクセス
2. **Algorithm** で `ES256` を選択
3. **Header** と **Payload** を入力
4. **VERIFY SIGNATURE** セクションで、.p8ファイルの内容を貼り付け
5. 生成されたJWTをコピー

**注意**: JWT.ioでは、.p8ファイルの内容をそのまま貼り付ける必要がありますが、ES256の署名検証が正しく動作しない場合があります。

#### 生成したJWTの使用方法

1. 上記のいずれかの方法でJWTを生成
2. 生成されたJWT（長い文字列）をコピー
3. Supabase Dashboardの **Secret Key** フィールドに貼り付け
4. **Save** をクリック

**重要**: 
- JWTは有効期限があります（最大6ヶ月）
- 有効期限が切れたら、新しいJWTを生成してSupabaseに再設定する必要があります
- JWTは.p8ファイルの内容とは異なります

### 2.5 設定の保存

1. すべての情報を入力したら、**Save** をクリック
2. エラーが表示されないことを確認

---

## ステップ3: モバイルアプリ側の実装

### 3.1 パッケージのインストール

```bash
cd /app/Morizo-mobile
npx expo install expo-apple-authentication
```

### 3.2 app.jsonの確認

`app.json`で、Bundle IDが正しく設定されていることを確認：

```json
{
  "expo": {
    "ios": {
      "bundleIdentifier": "jp.co.csngrp.morizo"
    }
  }
}
```

### 3.3 認証関数の実装

#### 3.3.1 apple-auth.tsの作成

`/app/Morizo-mobile/lib/auth/apple-auth.ts` を新規作成：

```typescript
import * as AppleAuthentication from 'expo-apple-authentication';
import { Platform } from 'react-native';
import { supabase } from '../supabase';
import { logAuth, safeLog, LogCategory } from '../logging';

/**
 * Sign in with Appleを行う関数
 * @returns エラー情報を含むオブジェクト
 */
export const signInWithApple = async (): Promise<{ error: any }> => {
  const timer = safeLog.timer('apple-signin');
  
  try {
    // iOSのみサポート
    if (Platform.OS !== 'ios') {
      const error = new Error('Sign in with Apple is only available on iOS');
      await logAuth('apple_signin', undefined, false, { error: error.message });
      safeLog.error(LogCategory.AUTH, 'Sign in with Apple: iOS only', { platform: Platform.OS });
      timer();
      return { error };
    }

    // Apple認証が利用可能かチェック
    const isAvailable = await AppleAuthentication.isAvailableAsync();
    if (!isAvailable) {
      const error = new Error('Sign in with Apple is not available on this device');
      await logAuth('apple_signin', undefined, false, { error: error.message });
      safeLog.error(LogCategory.AUTH, 'Sign in with Apple: Not available', { isAvailable });
      timer();
      return { error };
    }

    safeLog.info(LogCategory.AUTH, 'Sign in with Apple: 認証開始');

    // Apple ID認証を開始
    const credential = await AppleAuthentication.signInAsync({
      requestedScopes: [
        AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
        AppleAuthentication.AppleAuthenticationScope.EMAIL,
      ],
    });

    if (!credential.identityToken) {
      const error = new Error('Apple認証でIDトークンが取得できませんでした');
      await logAuth('apple_signin', undefined, false, { error: error.message });
      safeLog.error(LogCategory.AUTH, 'Sign in with Apple: IDトークン取得失敗');
      timer();
      return { error };
    }

    safeLog.info(LogCategory.AUTH, 'Sign in with Apple: IDトークン取得成功', {
      user: credential.user,
      hasEmail: !!credential.email,
      hasFullName: !!credential.fullName
    });

    // Supabase Authでサインイン
    const { data, error: supabaseError } = await supabase.auth.signInWithIdToken({
      provider: 'apple',
      token: credential.identityToken,
    });

    if (supabaseError) {
      await logAuth('apple_signin', credential.email || undefined, false, { error: supabaseError.message });
      safeLog.error(LogCategory.AUTH, 'Sign in with Apple: Supabase認証失敗', { error: supabaseError.message });
      timer();
      return { error: supabaseError };
    }

    if (data.user) {
      await logAuth('apple_signin', data.user.email || credential.email || undefined, true);
      safeLog.info(LogCategory.AUTH, 'Sign in with Apple: 認証成功', {
        userId: data.user.id,
        email: data.user.email || credential.email
      });
    }

    timer();
    return { error: null };

  } catch (error: any) {
    // ユーザーがキャンセルした場合
    if (error.code === 'ERR_REQUEST_CANCELED') {
      safeLog.info(LogCategory.AUTH, 'Sign in with Apple: ユーザーがキャンセル');
      timer();
      return { error: null }; // エラーとして扱わない
    }

    const errorMessage = error.message || 'Sign in with Appleで予期しないエラーが発生しました';
    await logAuth('apple_signin', undefined, false, { error: errorMessage });
    safeLog.error(LogCategory.AUTH, 'Sign in with Apple: エラー', { error: errorMessage });
    timer();
    return { error: new Error(errorMessage) };
  }
};
```

#### 3.3.2 auth-methods.tsへの追加

`/app/Morizo-mobile/lib/auth/auth-methods.ts` に以下を追加：

```typescript
// 既存のimportの後に追加
import { signInWithApple } from './apple-auth';

// 既存のexportの後に追加（ファイルの最後に追加）
export { signInWithApple };
```

#### 3.3.3 index.tsへの追加

`/app/Morizo-mobile/lib/auth/index.ts` に以下を追加：

```typescript
// 既存のexportの後に追加
export {
  signInWithApple,
} from './apple-auth';
```

#### 3.3.4 AuthContext.tsxへの追加

`/app/Morizo-mobile/contexts/AuthContext.tsx` を確認し、以下を追加：

```typescript
// importに追加
import { signInWithApple } from '../lib/auth';

// AuthContextTypeインターフェースに追加（既存のsignInWithGoogleの後に）
signInWithApple: () => Promise<{ error: any }>;

// AuthProviderコンポーネント内の実装に追加
const signInWithAppleHandler = async () => {
  const { error } = await signInWithApple();
  if (error) {
    console.error('Apple認証エラー:', error);
  }
  // 認証状態はonAuthStateChangeで自動的に更新される
  return { error };
};

// valueオブジェクトに追加
signInWithApple: signInWithAppleHandler,
```

#### 3.3.5 LoginScreen.tsxへの追加

`/app/Morizo-mobile/screens/LoginScreen.tsx` を確認し、以下を追加：

```typescript
// importに追加
import { Platform } from 'react-native';
import * as AppleAuthentication from 'expo-apple-authentication';

// useAuthから取得（既存のsignInWithGoogleの後に追加）
const { signIn, signUp, signInWithGoogle, signInWithApple } = useAuth();

// コンポーネント内に追加（handleGoogleSignInの後に）
const handleAppleSignIn = async () => {
  // iOSのみ表示・動作
  if (Platform.OS !== 'ios') {
    return;
  }

  setLoading(true);
  try {
    logComponent('LoginScreen', 'apple_auth_button_clicked');
    
    const { error } = await signInWithApple();
    if (error) {
      await logAuth('apple_signin', undefined, false, { error: error.message });
      showErrorAlert(error.message);
    }
  } catch (error) {
    await logAuth('apple_signin', undefined, false, { error: error.message });
    showErrorAlert('Apple認証に失敗しました');
  } finally {
    setLoading(false);
  }
};

// レンダリング部分に追加（Google認証ボタンの後に）
{Platform.OS === 'ios' && (
  <TouchableOpacity
    style={[styles.button, styles.appleButton]}
    onPress={handleAppleSignIn}
    disabled={loading}
  >
    <AppleAuthentication.AppleAuthenticationButton
      buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
      buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
      cornerRadius={8}
      style={styles.appleButtonInner}
      onPress={handleAppleSignIn}
    />
  </TouchableOpacity>
)}
```

スタイルに追加：

```typescript
appleButton: {
  backgroundColor: '#000',
  borderWidth: 0,
},
appleButtonInner: {
  width: '100%',
  height: 50,
},
```

---

## ステップ4: テスト

### 4.1 実機でのテスト

1. **重要**: Sign in with AppleはiOS実機でのみ動作します。シミュレーターでは動作しません。

2. 実機にアプリをインストール

3. ログイン画面で「Sign in with Apple」ボタンが表示されることを確認

4. ボタンをタップして、Apple ID認証画面が表示されることを確認

5. Apple IDでサインイン

6. アプリに正常にログインできることを確認

### 4.2 トラブルシューティング

#### Service IDの作成時にIdentifierでエラーが出る / 表示されないのにIdentifierが残っている
- **原因**: 
  - Identifierが既に使用されている（表示されないが、データベースには残っている）
  - Apple Developer Consoleの表示の問題（キャッシュ、フィルター、検索の問題）
  - ブラウザのキャッシュの問題
- **対処**: 
  1. **ブラウザのキャッシュをクリア**:
     - ブラウザの設定でキャッシュをクリア
     - または、シークレット/プライベートモードで開く
     - ページを再読み込み（Ctrl+Shift+R または Cmd+Shift+R）
  2. **既存のService IDを徹底的に確認**:
     - Apple Developer Consoleで、**Identifiers** > **Services IDs** を開く
     - 検索ボックスに `jp.co.csngrp.morizo` と入力して検索
     - フィルターをリセットして、すべてのService IDを表示
     - 左側のナビゲーションメニューで、すべてのService IDを確認
  3. **別のIdentifierを使用する（推奨）**:
     - 表示の問題を回避するため、別のIdentifierを使用することを推奨します
     - 例: `jp.co.csngrp.morizo.signin.apple`
     - 例: `jp.co.csngrp.morizo.apple.signin`
     - 例: `jp.co.csngrp.morizo.signin2`
     - 例: `jp.co.csngrp.morizo.applesignin`
  4. **形式エラーの場合**:
     - 逆ドメイン形式（例: `com.example.service`）を使用しているか確認
     - 英数字、ピリオド（.）、ハイフン（-）のみ使用可能
     - 大文字・小文字は区別されます
  5. **長さエラーの場合**:
     - 100文字以内に収めているか確認
  6. **Apple Developer Consoleのサポートに問い合わせ**:
     - 上記の方法で解決しない場合、Apple Developer Supportに問い合わせ
     - Identifierが表示されないのに残っている問題を報告

#### エラー: "Sign in with Apple is not available"
- **原因**: デバイスがSign in with Appleをサポートしていない、または設定が不完全
- **対処**: 
  - iOS 13以降の実機を使用しているか確認
  - Apple IDでサインインしているか確認（設定 > [ユーザー名]）

#### エラー: "Invalid client_id"
- **原因**: SupabaseのService ID設定が間違っている
- **対処**: 
  - Supabase DashboardでService IDを再確認
  - Apple Developer ConsoleのService IDと一致しているか確認

#### エラー: "Invalid key"
- **原因**: Key IDまたはSecret Keyの設定が間違っている
- **対処**: 
  - Supabase DashboardでKey IDとSecret Keyを再確認
  - Keyファイル（.p8）の内容が正しくコピーされているか確認

#### 「Next」ボタンが活性化しない / 「No App ID is available.」と表示される
- **原因**: Primary App IDが選択されていない、またはApp IDでSign In with Appleが有効になっていない
- **対処**: 
  1. **App IDの確認**:
     - Apple Developer Consoleで、1.1で作成したApp IDを開く
     - **Sign In with Apple** が有効になっているか確認
     - 有効になっていない場合は、編集画面で有効化して保存
  2. **ページの再読み込み**:
     - App IDを有効化した後、Service IDの設定画面を一度閉じて再度開く
     - または、ブラウザのページを再読み込み（F5キー）
  3. **Primary App IDの選択**:
     - 「Primary App ID」ドロップダウンに、Sign In with Appleが有効なApp IDが表示されることを確認
     - App IDを選択する
  4. **必須フィールドの確認**:
     - **Domains and Subdomains**: `supabase.co` が入力されているか確認
     - **Return URLs**: 完全なURL（`https://`から始まる）が入力されているか確認
  5. すべての必須項目が正しく入力されていれば、「Next」ボタンが活性化します

#### エラー: "Invalid redirect_uri"
- **原因**: Return URLの設定が間違っている
- **対処**: 
  - Apple Developer ConsoleのService ID設定でReturn URLを確認
  - SupabaseのProject URLと一致しているか確認
  - Return URLは完全な形式（`https://`から始まる）で入力されているか確認

---

## 参考資料

- [Expo Apple Authentication Documentation](https://docs.expo.dev/versions/latest/sdk/apple-authentication/)
- [Supabase Auth - Apple Provider](https://supabase.com/docs/guides/auth/social-login/auth-apple)
- [Apple Sign In with Apple Documentation](https://developer.apple.com/sign-in-with-apple/)
- [Apple Human Interface Guidelines - Sign in with Apple](https://developer.apple.com/design/human-interface-guidelines/components/system-experiences/sign-in-with-apple/)

---

## チェックリスト

### Apple Developer Console
- [ ] App IDでSign In with Appleが有効
- [ ] Service IDを作成
- [ ] Service IDでSign In with Appleを有効化
- [ ] Return URLを設定（SupabaseのコールバックURL）
- [ ] Key IDを作成
- [ ] Keyファイル（.p8）をダウンロードして保存
- [ ] Team IDをメモ

### Supabase Dashboard
- [ ] Apple認証プロバイダーを有効化
- [ ] Service IDを設定
- [ ] Secret Key（.p8ファイルの内容）を設定
- [ ] Key IDを設定
- [ ] Team IDを設定
- [ ] 設定を保存（エラーなし）

### モバイルアプリ
- [ ] `expo-apple-authentication`パッケージをインストール
- [ ] `apple-auth.ts`を作成
- [ ] `auth-methods.ts`に追加
- [ ] `index.ts`に追加
- [ ] `AuthContext.tsx`に追加
- [ ] `LoginScreen.tsx`にボタンを追加
- [ ] iOS実機でテスト成功

---

**作成日**: 2025年11月28日  
**最終更新**: 2025年11月28日

