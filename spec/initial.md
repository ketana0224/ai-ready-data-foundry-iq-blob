# Azure AI Search - Blob Knowledge Source 作成仕様書

## 概要

Azure Blob Storageをデータソースとして、Azure AI Searchのナレッジソースとナレッジベースを作成し、取得テストを実行するPythonスクリプト。

## 参考ドキュメント

- [Azure AI Search - Agentic Knowledge Source (Blob)](https://learn.microsoft.com/ja-jp/azure/search/agentic-knowledge-source-how-to-blob?pivots=python)
- [Azure AI Search - Knowledge Base Retrieval](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)

## 技術要件

### 認証方式

- **Entra ID認証**（Azure AD）を使用
- `DefaultAzureCredential` による資格情報取得
- API キーは不要（キーレス認証）
- Azure CLI ログインチェック機能を実装（Windows `az.cmd` 対応）

### Azure リソース

1. **Azure AI Search**
   - API Version: `2025-11-01-preview`
   - REST API を使用（SDK の preview 機能制限のため）
   - エンドポイント: `https://srch-ketana-prod-centralus.search.windows.net`

2. **Azure Blob Storage**
   - ResourceId 形式での接続指定
   - フォーマット: `ResourceId=/subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{account-name};`
   - コンテナ: `docs`

3. **Azure OpenAI**
   - チャットモデル用リソース: `aif-ketana-prod-swedencentral`
     - モデル: `gpt-4.1`
   - 埋め込みモデル用リソース: `aoai-ketana-prod-eastus2`
     - モデル: `text-embedding-3-large`

4. **Azure AI Services**
   - リソース: `aif-ketana-prod-swedencentral`
   - エンドポイント: `https://aif-ketana-prod-swedencentral.cognitiveservices.azure.com`
   - Content Understanding 機能を提供

### コンテンツ抽出モード

- **STANDARD mode** を使用
  - Content Understanding による高度なドキュメント解析
  - PDF/Word/画像からのテキスト抽出とレイアウト解析
  - テーブル認識と構造化データ抽出
  - 画像のキャプション生成と Asset Store への保存
  - AI Services エンドポイント必須: `https://aif-ketana-prod-swedencentral.cognitiveservices.azure.com`
  - Asset Store 必須: `asset-store` コンテナ

### Reasoning Effort

- **medium** レベル
  - LLM による高度な query planning と answer synthesis
  - 会話履歴の分析とサブクエリ生成
  - 並列クエリ実行と結果統合
  - `messages` 形式でのクエリ実行
  - 自然言語による回答生成（引用付き）

## 実装機能

### 1. ナレッジソース作成

- API: `PUT /knowledgesources/{name}`
- パラメータ:
  - `name`: ナレッジソース名
  - `dataSourceConnection`: Blob Storage 接続情報（ResourceId 形式）
  - `contentExtractionMode`: `standard`（Content Understanding 使用）
  - `embeddingModel`: Azure OpenAI embedding deployment 指定

### 2. インジェスト状態監視

- API: `GET /knowledgesources/{name}`
- `synchronizationStatus` フィールドをチェック
- 状態: `creating` → `active`
- インジェスト完了まで待機
### 2.5. インデクサーリセット・再実行

- インデクサー名: `{knowledge_source_name}-indexer`
- API（リセット）: `POST /indexers/{name}/reset`
- API（再実行）: `POST /indexers/{name}/run`
- API（状態確認）: `GET /indexers/{name}/status`
- 目的: ナレッジソース更新後、最新の設定（STANDARD mode、Content Understanding）で全ドキュメントを再処理
- HTTP 200/202/204 で成功
- バックグラウンドで実行継続

**注記：**
- 16MB超のドキュメントは Content Understanding の処理制限により警告が記録される
- 警告が出てもインデクサーは停止せず、他のドキュメント処理は継続される
- 16MB超のドキュメント本文は検索対象にならない可能性がある

## 検索方式

### エンベディングと検索

Azure AI Search の Knowledge Source/Knowledge Base は以下の機能を提供：

- **エンベディング**: 
  - Azure OpenAI `text-embedding-3-large` (3072次元)
  - ドキュメントとクエリのベクトル化

- **検索方式**:
  - Azure AI Search がクエリに応じて最適な検索方式を自動選択
  - ベクトル検索、キーワード検索（BM25）、またはハイブリッド
  - セマンティックランキング対応（Azure AI Searchで有効化が必要）

- **LLM統合（medium reasoning effort）**:
  - Azure OpenAI `gpt-4.1` によるクエリプランニング
  - 複数のサブクエリ生成と並列実行
  - 自然言語による回答生成（answerSynthesis）

### 3. ナレッジベース作成

- API: `PUT /knowledgebases/{name}`
- パラメータ:
  - `name`: ナレッジベース名
  - `knowledgeSources`: 関連付けるナレッジソース
  - `models`: Azure OpenAI モデル設定（LLM統合）
  - `outputMode`: answerSynthesis（自然言語回答）
  - `answerInstructions`: 回答生成の指示
  - `retrievalReasoningEffort.kind`: medium

### 4. 取得テスト

- API: `POST /knowledgebases/{name}/retrieve`
- リクエスト形式（medium mode）:
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "検索クエリ"
          }
        ]
      }
    ]
  }
  ```
- レスポンス:
  - LLMによる自然言語回答（引用付き）
  - クエリプランニングの詳細（サブクエリ、トークン数）
  - 参照ドキュメント配列

## HTTP ステータスコード処理

- **200**: 取得成功
- **201**: 作成成功
- **204**: 更新成功（No Content）
  - ナレッジソース/ナレッジベースの更新時に返される
  - 成功として扱う

## 環境変数（.env）

```env
# Azure OpenAI Model
AZURE_OPENAI_API_ENDPOINT=https://aif-ketana-prod-swedencentral.openai.azure.com
AZURE_OPENAI_MODEL=gpt-4.1

# Azure OpenAI Embedding Model
AZURE_OPENAI_EMBEDDING_ENDPOINT=https://aoai-ketana-prod-eastus2.openai.azure.com
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# AI Search
AI_SEARCH_ENDPOINT=https://srch-ketana-prod-centralus.search.windows.net
AI_SEARCH_API_VERSION=2025-11-01-preview

# Knowledge Source/Base
KNOWLEDGE_SOURCE_NAME=knowledge-source-blob-standard
KNOWLEDGE_BASE_NAME=knowledge-base-blob-standard
RUN_RETRIEVE_TEST=true
RETRIEVE_TEST_QUERY=このナレッジベースの対象領域を説明して

# Blob Storage (ResourceId形式)
blob_storage_account=ResourceId=/subscriptions/d1bf4d07-2dac-43a8-9060-4d5274fc7e33/resourceGroups/rg-ketana-prod-eastus2/providers/Microsoft.Storage/storageAccounts/stketanaprodeastus2;
blob_container_name=docs

# Content Understanding (AI Services)
AI_SERVICES_ENDPOINT=https://aif-ketana-prod-swedencentral.cognitiveservices.azure.com

# Asset Store (画像抽出用)
ASSET_STORE_ACCOUNT=ResourceId=/subscriptions/d1bf4d07-2dac-43a8-9060-4d5274fc7e33/resourceGroups/rg-ketana-prod-eastus2/providers/Microsoft.Storage/storageAccounts/stketanaprodeastus2;
ASSET_STORE_CONTAINER_NAME=asset-store
```

## RBAC 要件

1. **Search サービス**:
   - `Search Index Data Reader` （クエリ実行）
   - `Search Service Contributor` （ナレッジソース/ベース作成）

2. **Blob Storage**:
   - `Storage Blob Data Reader` （データ読み取り）

3. **Azure OpenAI**:
   - `Cognitive Services OpenAI User` （モデル呼び出し）

4. **Azure AI Services**:
   - `Cognitive Services User` （Content Understanding 使用）

5. **Asset Store (Blob Storage)**:
   - `Storage Blob Data Contributor` （画像書き込み）

## 実行フロー

1. Azure CLI ログイン確認（Windows `az.cmd` 対応）
2. 環境変数読み込み
3. Entra ID トークン取得
4. ナレッジソース作成/更新（STANDARD mode、HTTP 204 許容）
5. インジェスト状態監視（`synchronizationStatus: active` まで）
6. **インデクサーリセット・再実行**
   - インデクサーの状態をリセット
   - 最新のContent Understanding設定で全ドキュメント再処理
   - バックグラウンドで実行継続
7. ナレッジベース作成/更新（medium reasoning effort、HTTP 204 許容）
8. 取得テスト実行（`messages` 形式クエリ、自然言語回答生成）

## エラーハンドリング

- 認証エラー: Azure CLI ログイン状態確認
- 400 エラー: リクエストボディの形式確認
- 404 エラー: リソース存在確認
- 405 エラー: エンドポイント/HTTP メソッド確認

## 出力

- ✓ 成功メッセージ
- ✗ エラーメッセージとレスポンス詳細
- JSON 形式の取得結果（整形済み、日本語対応）
