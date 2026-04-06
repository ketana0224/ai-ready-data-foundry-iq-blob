# Entra ID認証とRBACセットアップガイド

このドキュメントでは、Azure AI SearchのマネージドIDを使用してEntra ID認証を設定する手順を説明します。

## 概要

このプロジェクトでは以下のリソースにEntra ID（マネージドID）でアクセスします：

- Azure Blob Storage（ドキュメントソース）
- Azure OpenAI（埋め込み、チャット完了、クエリプランニング、回答生成）
- Azure AI Services（Content Understanding - STANDARD mode）
- Azure Blob Storage（Asset Store - 画像保存）

## 前提条件

- Azure CLI がインストールされていること
- 適切な権限を持つAzureアカウント（Owner または User Access Administrator）
- Azure AI Searchサービスが作成済みであること

## Step 1: Azure AI Searchのマネージドアイデンティティを有効化

```bash
# リソースグループとサービス名を設定
RESOURCE_GROUP="your-resource-group"
SEARCH_SERVICE_NAME="your-search-service"

# システム割り当てマネージドIDを有効化
az search service update \
  --name $SEARCH_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --identity-type SystemAssigned

# プリンシパルIDを取得
SEARCH_PRINCIPAL_ID=$(az search service show \
  --name $SEARCH_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --query identity.principalId \
  -o tsv)

echo "Search Service Principal ID: $SEARCH_PRINCIPAL_ID"
```

## Step 2: Blob Storageへのロール割り当て

```bash
# ストレージアカウント名を設定
STORAGE_ACCOUNT_NAME="your-storage-account"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Storage Blob Data Readerロールを割り当て
az role assignment create \
  --role "Storage Blob Data Reader" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME"

echo "✓ Blob Storageへのアクセス権を付与しました"
```

## Step 3: Azure OpenAIへのロール割り当て

```bash
# OpenAIアカウント名を設定
OPENAI_ACCOUNT_NAME="your-openai-account"

# Cognitive Services OpenAI Userロールを割り当て
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$OPENAI_ACCOUNT_NAME"

echo "✓ Azure OpenAIへのアクセス権を付与しました"
```

## Step 4: AI Services (Content Understanding) へのロール割り当て

**STANDARD modeで必須**

```bash
# AI Servicesアカウント名を設定
AI_SERVICES_ACCOUNT_NAME="your-ai-services-account"
AI_SERVICES_RG="your-ai-services-resource-group"  # AI Servicesのリソースグループ

# Cognitive Services Userロールを割り当て
az role assignment create \
  --role "Cognitive Services User" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AI_SERVICES_RG/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_ACCOUNT_NAME"

echo "✓ AI Services (Content Understanding) へのアクセス権を付与しました"
```

**注意**: AI Servicesエンドポイントは `cognitiveservices.azure.com` である必要があります（`openai.azure.com` ではありません）。

## Step 5: Asset Store用のBlob Storageへのロール割り当て

**STANDARD modeで必須** - 抽出された画像を保存するために必要

```bash
# Asset Store用のストレージアカウント名を設定
ASSET_STORE_ACCOUNT_NAME="your-asset-store-account"

# asset-store コンテナを作成
az storage container create \
  --name asset-store \
  --account-name $ASSET_STORE_ACCOUNT_NAME \
  --auth-mode login

# Storage Blob Data Contributorロールを割り当て（書き込み権限が必要）
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$ASSET_STORE_ACCOUNT_NAME"

echo "✓ Asset Storeへのアクセス権を付与しました"
```

ソースと同じストレージアカウントの場合は、既存の割り当てを`Storage Blob Data Contributor`にアップグレードしてください。

## Step 6: ローカル開発環境の認証設定

### Azure CLI認証（推奨）

```bash
# Azureにログイン
az login

# 正しいサブスクリプションが選択されているか確認
az account show

# 必要に応じてサブスクリプションを変更
az account set --subscription $SUBSCRIPTION_ID
```

### サービスプリンシパル認証

```bash
# サービスプリンシパルを作成
az ad sp create-for-rbac --name "search-knowledge-source-sp" --role Contributor

# 出力されたcredentialsを.envに設定
# AZURE_TENANT_ID=...
# AZURE_CLIENT_ID=...
# AZURE_CLIENT_SECRET=...
```

## Step 7: 権限の確認

```bash
# Azure AI Searchのロール割り当てを確認
az role assignment list --assignee $SEARCH_PRINCIPAL_ID --output table

# 以下のロールが表示されるはずです：
# - Storage Blob Data Reader (または Contributor)
# - Cognitive Services OpenAI User
# - Cognitive Services User
```

## トラブルシューティング

### "Authorization failed" エラー

ロール割り当てが反映されるまで数分かかる場合があります。以下を試してください：

```bash
# ロール割り当てを再確認
az role assignment list --assignee $SEARCH_PRINCIPAL_ID --all --output table

# 必要に応じて再度ロールを割り当て
```

### "Principal not found" エラー

マネージドIDが有効化されていない可能性があります：

```bash
# マネージドIDの状態を確認
az search service show \
  --name $SEARCH_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --query identity
```

### ローカル実行時の認証エラー

```bash
# Azure CLIのログイン状態を確認
az account show

# トークンをクリアして再ログイン
az account clear
az login
```

## 一括設定スクリプト

以下のスクリプトで全ての設定を一度に実行できます：

```bash
#!/bin/bash

# 変数を設定
RESOURCE_GROUP="your-rg"
SEARCH_SERVICE_NAME="your-search"
STORAGE_ACCOUNT_NAME="your-storage"
OPENAI_ACCOUNT_NAME="your-openai"
AI_SERVICES_ACCOUNT_NAME="your-ai-services"
ASSET_STORE_ACCOUNT_NAME="your-asset-storage"  # オプション

SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# マネージドIDを有効化
az search service update \
  --name $SEARCH_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --identity-type SystemAssigned

SEARCH_PRINCIPAL_ID=$(az search service show \
  --name $SEARCH_SERVICE_NAME \
  --resource-group $RESOURCE_GROUP \
  --query identity.principalId \
  -o tsv)

# Blob Storage
az role assignment create \
  --role "Storage Blob Data Reader" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME"

# Azure OpenAI
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$OPENAI_ACCOUNT_NAME"

# AI Services
az role assignment create \
  --role "Cognitive Services User" \
  --assignee $SEARCH_PRINCIPAL_ID \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AI_SERVICES_ACCOUNT_NAME"

# Asset Store (オプション)
if [ -n "$ASSET_STORE_ACCOUNT_NAME" ]; then
  az role assignment create \
    --role "Storage Blob Data Contributor" \
    --assignee $SEARCH_PRINCIPAL_ID \
    --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$ASSET_STORE_ACCOUNT_NAME"
fi

echo "✓ すべてのロール割り当てが完了しました"
az role assignment list --assignee $SEARCH_PRINCIPAL_ID --output table
```

## 参考資料

- [Azure AI Search - マネージドIDの使用](https://learn.microsoft.com/azure/search/search-howto-managed-identities-data-sources)
- [Azure RBAC ロールの割り当て](https://learn.microsoft.com/azure/role-based-access-control/role-assignments-portal)
- [DefaultAzureCredential](https://learn.microsoft.com/python/api/azure-identity/azure.identity.defaultazurecredential)
