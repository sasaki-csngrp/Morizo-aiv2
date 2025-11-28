# 不足食材チェックAPI実装プラン

## 概要

段階提案時の不足食材チェック機能をバックエンドAPI化し、フロントエンドとモバイルの両方から利用できるようにします。

## 目的

- 不足食材チェックロジックをバックエンドに集約し、DRY原則を実現
- 除外リストの一元管理
- 将来的な拡張（機械学習による食材マッチング等）に対応可能

## 実装内容

### 1. APIエンドポイント

**パス**: `/api/recipe/ingredients/check-missing`

**メソッド**: `POST`

**リクエストボディ**:
```typescript
{
  recipeIngredients: string[];  // レシピに必要な食材リスト
  availableIngredients: string[]; // 使える食材リスト
}
```

**レスポンス**:
```typescript
{
  success: boolean;
  missingIngredients: string[]; // 不足している食材リスト
  excludedCount?: number; // 除外された食材の数（デバッグ用）
}
```

**エラーレスポンス**:
```typescript
{
  success: false;
  error: string;
}
```

### 2. 実装ファイル

#### 2.1 APIルートファイル
**ファイル**: `app/api/recipe/ingredients/check-missing/route.ts`

**実装内容**:
- POSTリクエストハンドラー
- 認証チェック（`authenticateRequest`）
- CORSヘッダー設定
- リクエストバリデーション
- 不足食材チェックロジックの呼び出し
- ロギング（`ServerLogger`）
- エラーハンドリング

#### 2.2 ユーティリティファイル
**ファイル**: `lib/utils/ingredient-checker.ts`

**実装内容**:
- `EXCLUDED_INGREDIENTS`定数（除外リスト）
- `getMissingIngredients`関数（不足食材判定ロジック）

### 3. 除外リスト（EXCLUDED_INGREDIENTS）

一般的な調味料・水などを不足食材として判定しないリスト：

```typescript
const EXCLUDED_INGREDIENTS = [
  '水',
  'はちみつ',
  'ハチミツ',
  '塩',
  'こしょう',
  '胡椒',
  'コショウ',
  '醤油',
  'しょうゆ',
  '味噌',
  'みそ',
  '砂糖',
  'みりん',
  '酒',
  '料理酒',
  '酢',
  '油',
  'サラダ油',
  'オリーブオイル',
  'ごま油',
  'バター',
  'マヨネーズ',
  'ケチャップ',
  'ウスターソース',
  'オイスターソース',
  '豆板醤',
  '甜麺醤',
  '味の素',
  'だし',
  'だしの素',
  'コンソメ',
  '顆粒だし',
  'チューブ生姜',
  'チューブにんにく',
  'ネギ分',
  'ブラックペッパー',
  'ブラックペッパ',
  'ペッパー',
  'ガーリックパウダー',
  'ガーリックパウダ',
  'にんにくパウダー',
  'にんにくパウダ',
  'パルメザンチーズ',
  'パルメザン',
  'パルメザンチーズ粉',
].map(ing => ing.toLowerCase());
```

### 4. 不足食材判定ロジック

```typescript
function getMissingIngredients(
  recipeIngredients: string[],
  availableIngredients: string[]
): string[] {
  if (!availableIngredients || availableIngredients.length === 0) {
    return []; // 使える食材情報がない場合は判定しない
  }

  const availableSet = new Set(
    availableIngredients.map(ing => ing.trim().toLowerCase())
  );

  return recipeIngredients.filter(ingredient => {
    const normalizedIngredient = ingredient.trim().toLowerCase();
    
    // 除外リストに含まれる食材は不足食材として判定しない
    if (EXCLUDED_INGREDIENTS.some(excluded => 
      normalizedIngredient.includes(excluded) || excluded.includes(normalizedIngredient)
    )) {
      return false;
    }

    // 完全一致をチェック
    if (availableSet.has(normalizedIngredient)) {
      return false;
    }
    
    // 部分一致もチェック（「豚バラ肉」と「豚バラ」など）
    const isContained = Array.from(availableSet).some(availableIng => 
      normalizedIngredient.includes(availableIng) || availableIng.includes(normalizedIngredient)
    );
    return !isContained;
  });
}
```

## 実装手順

### Step 1: ユーティリティファイルの作成

1. `lib/utils/ingredient-checker.ts`を作成
2. `EXCLUDED_INGREDIENTS`定数を定義
3. `getMissingIngredients`関数を実装
4. 型定義を追加

### Step 2: APIルートファイルの作成

1. `app/api/recipe/ingredients/check-missing/route.ts`を作成
2. 既存のAPIルート（`app/api/chat/selection/route.ts`）を参考に実装
3. 認証チェック、CORS、ロギング、エラーハンドリングを実装
4. ユーティリティ関数を呼び出して不足食材を判定

### Step 3: 型定義の追加（オプション）

`types/menu.ts`または新しい型定義ファイルに以下を追加：

```typescript
export interface CheckMissingIngredientsRequest {
  recipeIngredients: string[];
  availableIngredients: string[];
}

export interface CheckMissingIngredientsResponse {
  success: boolean;
  missingIngredients: string[];
  excludedCount?: number;
}
```

### Step 4: テスト

1. APIエンドポイントの動作確認
2. 認証チェックの確認
3. エラーハンドリングの確認
4. CORS設定の確認

## 既存コードからの移行

### フロントエンド（Morizo-web）

**変更前**: `components/RecipeListModal.tsx`内に直接実装

**変更後**: 
- `EXCLUDED_INGREDIENTS`と`getMissingIngredients`を削除
- API呼び出しに置き換え

### モバイル（Morizo-mobile）

**変更前**: `components/RecipeListModal.tsx`内に直接実装

**変更後**:
- `EXCLUDED_INGREDIENTS`と`getMissingIngredients`を削除
- API呼び出しに置き換え

## API呼び出し例

### フロントエンド（Next.js）

```typescript
import { authenticatedFetch } from '@/lib/auth';

const checkMissingIngredients = async (
  recipeIngredients: string[],
  availableIngredients: string[]
) => {
  const response = await authenticatedFetch('/api/recipe/ingredients/check-missing', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipeIngredients,
      availableIngredients,
    }),
  });

  if (!response.ok) {
    throw new Error('不足食材チェックに失敗しました');
  }

  return await response.json();
};
```

### モバイル（React Native）

```typescript
import { authenticatedFetch } from '../api/recipe-api';
import { getApiUrl } from '../lib/api-config';

const checkMissingIngredients = async (
  recipeIngredients: string[],
  availableIngredients: string[]
) => {
  const apiUrl = `${getApiUrl()}/recipe/ingredients/check-missing`;
  
  const response = await authenticatedFetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipeIngredients,
      availableIngredients,
    }),
  });

  if (!response.ok) {
    throw new Error('不足食材チェックに失敗しました');
  }

  return await response.json();
};
```

## メリット

1. **DRY原則**: ロジックが1箇所に集約され、保守性が向上
2. **一元管理**: 除外リストの更新が1箇所で済む
3. **拡張性**: 将来的に機械学習による食材マッチング等を追加可能
4. **テスト容易性**: バックエンドAPIとして独立してテスト可能
5. **一貫性**: フロントエンドとモバイルで同じロジックを使用

## デメリット・注意点

1. **ネットワーク依存**: API呼び出しが必要（オフライン時は動作しない）
2. **レイテンシ**: ネットワーク往復のオーバーヘッド
3. **認証必須**: 認証トークンが必要

## 将来の拡張案

1. **キャッシュ機能**: 同じ食材リストの判定結果をキャッシュ
2. **バッチ処理**: 複数のレシピを一度にチェック
3. **機械学習**: より高度な食材マッチング
4. **食材正規化**: 表記ゆれの自動補正

## 参考ファイル

- `app/api/chat/selection/route.ts` - APIルート実装パターン
- `app/api/recipe/ingredients/delete-candidates/[date]/route.ts` - 認証・CORSパターン
- `lib/auth-server.ts` - 認証ヘルパー
- `lib/logging-utils.ts` - ロギングユーティリティ

---

**作成日**: 2025年1月23日  
**対象プロジェクト**: Morizo-web（バックエンドAPI実装）

