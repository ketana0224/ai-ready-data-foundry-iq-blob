# AI Ready Data Foundry IQ Blob

Azure Blob StorageからAzure AI Searchのナレッジソースを作成するPythonプロジェクト

## 概要

このプロジェクトは、Azure Blob Storage内のドキュメントからAzure AI Searchのナレッジソースとナレッジベースを自動的に作成します。エージェント型検索（Agentic RAG）パイプラインを構築するためのツールです。

**認証方式**: Entra ID（旧Azure AD）のマネージドIDを使用し、API Keyは不要です。

## 機能

- Azure Blob Storageからのナレッジソース作成
- **Content Understanding (STANDARD mode)** による高度なドキュメント解析:
  - PDF/Word/画像からのテキスト抽出
  - レイアウト解析とテーブル認識
  - 画像キャプション生成
  - インテリジェントなチャンク分割
- **エンベディングと検索**:
  - Azure OpenAI text-embedding-3-large (3072次元) によるベクトル化
  - Azure AI Search が最適な検索方式を自動選択（ベクトル、キーワード、またはハイブリッド）
  - セマンティックランキング対応（Azure AI Search機能、有効化が必要）
- Azure OpenAI gpt-4.1 を使用した高度なクエリ処理:
  - Medium reasoning effort（LLMによるクエリプランニング）
  - 自然言語による回答生成（answerSynthesis）
  - 引用付き回答
- 画像抽出とAsset Storeへの保存
- ナレッジベースの作成と取得テスト

## ⚠️ 重要な制限事項

### Content Understanding のドキュメントサイズ制限

- **16MB以下のドキュメント**: Content Understandingで完全処理（テキスト抽出、レイアウト解析、テーブル認識、画像キャプション）
- **16MB超のドキュメント**: 
  - Content Understandingの処理制限により警告が記録される
  - ドキュメントの本文内容は検索対象にならない可能性がある
  - インデクサーは停止せず、他のドキュメントの処理は継続される
  - **対処方法**: 大きなドキュメントは16MB以下に分割することを推奨

## 前提条件

- Python 3.8以降
- Azure AI Searchサービス（セマンティックランカー有効）
- Azure Blob Storageアカウント
- Azure OpenAIサービス
- **Microsoft Foundry または Azure AI Services**（Content Understanding用）
- DefaultAzureCredentialで認証可能な環境（Azure CLI、環境変数、またはマネージドIDなど）

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の変数を設定してください：

```env
# Azure OpenAI Model
AZURE_OPENAI_API_ENDPOINT=https://your-openai-endpoint.openai.azure.com
AZURE_OPENAI_MODEL=gpt-4.1

# AI Search
AI_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AI_SEARCH_API_VERSION=2025-11-01-preview

# Blob Storage (Entra ID認証 - リソースURIのみ指定)
blob_storage_account=https://yourstorageaccount.blob.core.windows.net/
blob_container_name=docs

# Content Understanding (AI Services) - Entra ID認証
# Azure AI Services (Cognitive Services) のエンドポイント
# 注: OpenAIエンドポイントではなく、cognitiveservices.azure.com を使用
AI_SERVICES_ENDPOINT=https://your-ai-services-endpoint.cognitiveservices.azure.com

# Asset Store (画像抽出用のBlob Storage) - Entra ID認証
ASSET_STORE_ACCOUNT=https://yourstorageaccount.blob.core.windows.net/
ASSET_STORE_CONTAINER_NAME=asset-store

# Knowledge Source & Base
KNOWLEDGE_SOURCE_NAME=knowledge-source-blob-standard
KNOWLEDGE_BASE_NAME=knowledge-base-blob-standard

# Test settings
RUN_RETRIEVE_TEST=true
RETRIEVE_TEST_QUERY=このナレッジベースの対象領域を説明して
```

**重要: Entra ID認証について**

- すべてのAzureリソースへのアクセスは**System-Assigned Managed Identity**を使用します
- API KeyやSAS Tokenは**不要**です  
- Blob Storageには`https://account.blob.core.windows.net/`形式のリソースURIを指定します（接続文字列ではありません）

**Content Extraction Mode について:**

- **MINIMAL**: 標準的なテキストと画像抽出
- **STANDARD**: Azure Content Understanding を使用した高度なドキュメント解析（**このスクリプト**）
  - PDF/Word/PowerPointからのテキスト抽出
  - レイアウト解析（見出し、段落、テーブル、リスト）
  - テーブルの構造認識とデータ抽出
  - 画像からのOCRとキャプション生成
  - インテリジェントなチャンク分割
  - `AI_SERVICES_ENDPOINT`: Content Understanding用のAI Servicesエンドポイント（**必須**、cognitiveservices.azure.com）
  - `ASSET_STORE_*`: 抽出された画像を保存するBlob Storage（**必須**）
  - **制限**: 16MB超のドキュメントは処理制限により警告が記録される（本文検索不可の可能性）

**認証について:**
- すべてのリソースへのアクセスはEntra IDマネージドIDを使用
- API Keyや接続文字列（SAS Token付き）は不要
- Blob Storageは`https://account.blob.core.windows.net/`形式のリソースURIを指定

このスクリプトは **STANDARD** モードで動作します。
```

### 3. Azure認証とRBACの設定

このスクリプトは**Entra ID（マネージドID）**認証を使用します。

**詳細な設定手順は [SETUP_RBAC.md](SETUP_RBAC.md) を参照してください。**

Azure AI Searchのシステム割り当てマネージドIDに以下のロールが必要です：

#### 必要なロール割り当て

1. **Blob Storageへのアクセス**
   ```bash
   # Azure AI SearchのマネージドIDに対して
   az role assignment create \
     --role "Storage Blob Data Reader" \
     --assignee <search-service-principal-id> \
     --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-account>
   ```

2. **Azure OpenAIへのアクセス**
   ```bash
   az role assignment create \
     --role "Cognitive Services OpenAI User" \
     --assignee <search-service-principal-id> \
     --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai-account>
   ```

3. **AI Services (Content Understanding) へのアクセス**
   ```bash
   # STANDARD modeで必須
   az role assignment create \
     --role "Cognitive Services User" \
     --assignee <search-service-principal-id> \
     --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ai-services-account>
   ```

4. **Asset Store (Blob Storage) へのアクセス**
   ```bash
   # STANDARD modeで必須（画像書き込み権限）
   az role assignment create \
     --role "Storage Blob Data Contributor" \
     --assignee <search-service-principal-id> \
     --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage-account>
   ```

#### ローカル実行用の認証

以下のいずれかの方法で認証してください：

##### Azure CLIを使用（推奨）
```bash
az login
```

##### サービスプリンシパルを使用
```bash
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret
```

##### マネージドIDを使用（Azure VM/Container Apps等で実行時）
環境変数の設定は不要です。自動的に検出されます。

## 使用方法

### 認証と権限の診断（推奨）

**まず、認証と権限の状態を確認してください:**

```bash
python diagnose_auth.py
```

このツールは以下をチェックします:
- Azure CLIのインストールとログイン状態
- Azure AI Searchサービスの存在とマネージドID
- 必要なロール割り当て
- 現在のユーザーの権限
- 環境変数の設定

### ナレッジソースの作成

```bash
python create_knowledge_blob.py
```

このスクリプトは以下の処理を実行します：

1. 環境変数の読み込み
2. Azure Blob Storageからナレッジソースを作成（STANDARD mode）
3. Content Understandingによる高度なドキュメント解析
4. インジェスト状態の監視
5. **インデクサーのリセットと再実行**
   - 既存のインデックス状態をリセット
   - 最新のContent Understanding設定で全ドキュメントを再処理
   - バックグラウンドで実行継続
6. ナレッジベースの作成（LLM統合、medium reasoning effort）
7. 取得テスト（自然言語回答生成、引用付き回答）

**📌 処理結果について:**
- **成功**: 16MB以下のドキュメントは完全に処理され、検索可能になります
- **警告**: 16MB超のドキュメントは警告として記録されますが、インデクサーは停止しません
- **制限**: 警告が出たドキュメントの本文内容は検索対象にならない可能性があります

詳細は Azure Portal の「インデクサー」→「実行履歴」で確認できます。

## プロジェクト構成

```
.
├── README.md                      # このファイル
├── SETUP_RBAC.md                  # Entra ID認証とRBACセットアップガイド
├── .env                          # 環境変数設定ファイル
├── requirements.txt              # Pythonパッケージ依存関係
├── create_knowledge_source.py    # メインスクリプト（Entra ID認証版）
├── diagnose_auth.py              # 認証とRBACの診断ツール
├── docs/                         # ドキュメントフォルダ
└── spec/                         # 仕様書フォルダ
    └── initial.md                # 初期仕様書
```

## 出力

スクリプトは以下のAzure AI Searchオブジェクトを自動的に作成・更新します：

- **ナレッジソース (STANDARD mode)**: Blob Storageコンテナーへの接続とContent Understanding統合
- **データソース**: Blobコンテナーの定義（Entra ID認証、ResourceId形式）
- **スキルセット**: Content Understandingを使用した高度なドキュメント解析、コンテンツのチャンク化、ベクトル化
- **インデックス**: エンリッチされたコンテンツの保存
- **インデクサー**: 
  - インデックス作成パイプラインの実行
  - スクリプト実行時に自動的にリセット・再実行
  - 最新のContent Understanding設定で全ドキュメントを再処理
  - 16MB超のドキュメントは警告記録（処理継続）
- **ナレッジベース (medium reasoning effort)**: 
  - LLMによるクエリプランニング（サブクエリ生成、並列実行）
  - outputMode: answerSynthesis（自然言語回答、引用付き）
  - Azure OpenAI gpt-4.1 モデル統合
- **Asset Store**: 抽出された画像の保存（Blob Storage）

## トラブルシューティング

### 診断ツールの実行

**問題が発生した場合、まず診断ツールを実行してください:**

```bash
python diagnose_auth.py
```

このツールが自動的に問題を特定し、解決方法を提案します。

### 認証エラー (401)

**Entra ID認証**を使用しています：

**まず診断ツールを実行:**
```bash
python diagnose_auth.py
```

**手動での確認手順:**

1. Azure CLIでログインしているか確認
   ```bash
   az login
   az account show
   ```

2. 正しいサブスクリプションが選択されているか確認
   ```bash
   az account list --output table
   az account set --subscription <subscription-id>
   ```

3. **Azure AI Searchへのアクセス権限を確認**
   ```bash
   # 現在のユーザーに Search Service Contributor ロールを割り当て
   az role assignment create \
     --role "Search Service Contributor" \
     --assignee $(az ad signed-in-user show --query id -o tsv) \
     --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-service-name>
   ```

4. Azure AI Searchでシステム割り当てマネージドIDが有効か確認
   ```bash
   az search service show --name <search-service-name> --resource-group <rg> --query identity
   
   # 無効の場合は有効化
   az search service update \
     --name <search-service-name> \
     --resource-group <rg> \
     --identity-type SystemAssigned
   ```

5. 必要なロール割り当てが設定されているか確認
   - Storage Blob Data Reader（Blob Storage用）
   - Cognitive Services OpenAI User（Azure OpenAI用）
   - Cognitive Services User（AI Services用）

### 権限エラー

マネージドIDに適切なロールが割り当てられていない場合：

```bash
# Azure AI SearchのプリンシパルIDを取得
search_principal_id=$(az search service show --name <search-service-name> --resource-group <rg> --query identity.principalId -o tsv)

# ロールを割り当て
az role assignment create --role "Storage Blob Data Reader" --assignee $search_principal_id --scope <resource-id>
```

### インジェストが完了しない

- Blob Storageのコンテナーにドキュメントが存在するか確認
- リソースURIが正しいか確認（`https://account.blob.core.windows.net/`形式）
- マネージドIDに必要なロールが割り当てられているか確認
- Azure AI Searchのクォータを確認

### インデクサーに警告が表示される（16MB超のドキュメント）

**症状**: 
- インデクサーの実行履歴に「Document is 'XXXXXXX' bytes, which exceeds the maximum size '16777216' bytes」という警告が表示される

**説明**:
- これはContent Understandingの処理制限（16MB）によるものです
- **インデクサーは停止せず、他のドキュメントの処理は継続されます**
- 16MB超のドキュメントの本文内容は検索対象にならない可能性があります

**対処方法**:
1. **推奨**: 大きなドキュメントを16MB以下の複数ファイルに分割
2. **許容**: 警告を承諾し、16MB以下のドキュメントのみ検索対象とする
3. **確認**: Azure Portal の「インデクサー」→「実行履歴」で処理状況を確認

**影響範囲**:
- ✅ 16MB以下のドキュメント: 完全に処理され、検索可能
- ⚠️ 16MB超のドキュメント: 警告記録、本文検索不可の可能性
- ✅ システム全体: 正常に動作継続

### APIエラー

- API バージョンが正しいか確認（2025-11-01-preview）
- Azure AI Searchサービスでエージェント型検索が有効か確認

## 参考資料

- [Azure AI Search - エージェント型検索](https://learn.microsoft.com/ja-jp/azure/search/agentic-retrieval-overview)
- [Blob ナレッジソースの作成方法](https://learn.microsoft.com/ja-jp/azure/search/agentic-knowledge-source-how-to-blob?pivots=python)
- [Azure SDK for Python](https://docs.microsoft.com/python/api/overview/azure/search-documents-readme)
- [Azure AI Search - マネージドIDの使用](https://learn.microsoft.com/azure/search/search-howto-managed-identities-data-sources)
- [Entra ID認証とRBACセットアップガイド](SETUP_RBAC.md)

## ライセンス

MIT License
