"""
Azure AI Search - Blob Knowledge Source Creator
Azure Blob StorageからAI Searchのナレッジソースを作成するスクリプト
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
import requests
import json
import time
import subprocess


def check_azure_login():
    """Azure CLIのログイン状態を確認"""
    try:
        # Windowsでは az.cmd を使用
        import platform
        az_command = 'az.cmd' if platform.system() == 'Windows' else 'az'
        
        result = subprocess.run([az_command, 'account', 'show'], 
                              capture_output=True, 
                              text=True, 
                              timeout=10,
                              shell=True)  # Windowsで必要
        if result.returncode == 0:
            account_info = json.loads(result.stdout)
            print(f"\n✓ Azure CLIログイン済み")
            print(f"  - アカウント: {account_info.get('user', {}).get('name', 'N/A')}")
            print(f"  - サブスクリプション: {account_info.get('name', 'N/A')}")
            print(f"  - テナント: {account_info.get('tenantId', 'N/A')}")
            return True
        else:
            print("\n⚠ Azure CLIにログインしていません")
            print("以下のコマンドを実行してください:")
            print("  az login")
            return False
    except FileNotFoundError:
        print("\n⚠ Azure CLIがインストールされていません")
        print("以下からインストールしてください:")
        print("  https://docs.microsoft.com/cli/azure/install-azure-cli")
        return False
    except subprocess.TimeoutExpired:
        print("\n⚠ Azure CLIのチェックがタイムアウトしました")
        return False
    except json.JSONDecodeError as e:
        print(f"\n⚠ Azure CLIの出力解析に失敗: {str(e)}")
        print("Azure CLIにログインしていない可能性があります")
        print("コマンド: az login")
        return False
    except Exception as e:
        print(f"\n⚠ Azure CLIのチェックに失敗: {str(e)}")
        print("Azure CLIが正しくインストールされているか確認してください")
        return False


def load_environment():
    """環境変数を読み込む"""
    load_dotenv()
    
    config = {
        # Azure AI Search
        "search_endpoint": os.getenv("AI_SEARCH_ENDPOINT"),
        "search_api_version": os.getenv("AI_SEARCH_API_VERSION", "2025-11-01-preview"),
        
        # Azure OpenAI
        "openai_endpoint": os.getenv("AZURE_OPENAI_API_ENDPOINT"),
        "openai_model": os.getenv("AZURE_OPENAI_MODEL", "gpt-4.1"),
        "embedding_endpoint": os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT", os.getenv("AZURE_OPENAI_API_ENDPOINT")),
        "embedding_model": os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        
        # Blob Storage (Entra ID)
        "blob_storage_account": os.getenv("blob_storage_account"),
        "blob_container_name": os.getenv("blob_container_name"),
        
        # Storage Account Name (for authIdentity)
        "storage_account_resource_id": os.getenv("STORAGE_ACCOUNT_RESOURCE_ID"),  # Optional
        
        # Knowledge Source & Base
        "knowledge_source_name": os.getenv("KNOWLEDGE_SOURCE_NAME", "knowledge-source-blob"),
        "knowledge_base_name": os.getenv("KNOWLEDGE_BASE_NAME", "knowledge-base-blob"),
        
        # AI Services (Content Understanding)
        "ai_services_endpoint": os.getenv("AI_SERVICES_ENDPOINT"),
        
        # Asset Store (for extracted images) - Entra ID
        "asset_store_account": os.getenv("ASSET_STORE_ACCOUNT"),
        "asset_store_container_name": os.getenv("ASSET_STORE_CONTAINER_NAME"),
        
        # Test settings
        "run_retrieve_test": os.getenv("RUN_RETRIEVE_TEST", "true").lower() == "true",
        "retrieve_test_query": os.getenv("RETRIEVE_TEST_QUERY", "このナレッジベースの対象領域を説明して"),
    }
    
    # 必須パラメータの確認
    required = ["search_endpoint", "openai_endpoint", "blob_storage_account", "blob_container_name"]
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError(f"以下の環境変数が設定されていません: {', '.join(missing)}")
    
    return config


def create_knowledge_source(config):
    """ナレッジソースを作成（STANDARD mode, Content Understanding使用）"""
    print(f"\n{'='*60}")
    print("ナレッジソースを作成中（STANDARD mode）...")
    print(f"{'='*60}")
    
    # DefaultAzureCredentialでトークンを取得
    print("\n認証中...")
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token_response = credential.get_token("https://search.azure.com/.default")
        token = token_response.token
        print("✓ 認証成功")
    except Exception as e:
        print(f"✗ 認証に失敗しました: {str(e)}")
        print("\nトラブルシューティング:")
        print("1. Azure CLIでログインしてください: az login")
        print("2. 正しいサブスクリプションを選択してください: az account set --subscription <subscription-id>")
        print("3. 環境変数を確認してください: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET")
        raise
    
    endpoint = f"{config['search_endpoint']}/knowledgesources/{config['knowledge_source_name']}"
    params = {"api-version": config["search_api_version"]}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # ナレッジソースの定義（REST API形式 - Entra ID認証使用）
    knowledge_source_definition = {
        "name": config["knowledge_source_name"],
        "kind": "azureBlob",
        "description": "Azure Blob Storageからのナレッジソース (STANDARD mode with Content Understanding)",
        "azureBlobParameters": {
            "connectionString": config["blob_storage_account"],  # Entra ID: リソースURIのみ
            "containerName": config["blob_container_name"],
            "isADLSGen2": False,
            "ingestionParameters": {
                "disableImageVerbalization": False,
                "chatCompletionModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": config["openai_endpoint"],
                        "deploymentId": config["openai_model"],
                        "modelName": config["openai_model"]
                    }
                },
                "embeddingModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": config["embedding_endpoint"],
                        "deploymentId": config["embedding_model"],
                        "modelName": config["embedding_model"]
                    }
                },
                "contentExtractionMode": "standard"
            }
        }
    }
    
    # AI Services（Content Understanding）を追加 - Entra ID認証
    if config.get("ai_services_endpoint"):
        knowledge_source_definition["azureBlobParameters"]["ingestionParameters"]["aiServices"] = {
            "uri": config["ai_services_endpoint"]
        }
    
    # Asset Store（画像保存）を追加 - Entra ID認証
    if config.get("asset_store_account") and config.get("asset_store_container_name"):
        knowledge_source_definition["azureBlobParameters"]["ingestionParameters"]["assetStore"] = {
            "connectionString": config["asset_store_account"],  # Entra ID: リソースURIのみ
            "containerName": config["asset_store_container_name"]
        }
    
    # ナレッジソースを作成または更新
    print(f"\nAPI呼び出し中: {endpoint}")
    response = requests.put(endpoint, params=params, headers=headers, json=knowledge_source_definition)
    
    if response.status_code in [200, 201, 204]:
        if response.status_code == 204:
            print(f"✓ ナレッジソース '{config['knowledge_source_name']}' を更新しました")
            return {"name": config["knowledge_source_name"]}
        else:
            result = response.json()
            print(f"✓ ナレッジソース '{result['name']}' を作成しました")
            return result
    else:
        print(f"\n✗ ナレッジソースの作成に失敗: HTTP {response.status_code}")
        print(f"\nエラーレスポンス:")
        try:
            error_detail = response.json()
            print(json.dumps(error_detail, indent=2, ensure_ascii=False))
        except:
            print(response.text)
        
        if response.status_code == 401:
            print("\n【認証エラー (401)】")
            print("\n考えられる原因:")
            print("1. Azure CLIでログインしていない")
            print("   → 対処: az login")
            print("\n2. トークンの有効期限が切れている")
            print("   → 対処: az account clear && az login")
            print("\n3. Azure AI Searchへのアクセス権限がない")
            print("   → 対処: Azure AI Searchの'Search Service Contributor'ロールが必要です")
            print(f"   → コマンド: az role assignment create --role 'Search Service Contributor' --assignee $(az ad signed-in-user show --query id -o tsv) --scope <search-service-resource-id>")
            print("\n4. 誤ったAzureテナント/サブスクリプションにログインしている")
            print("   → 確認: az account show")
        
        raise Exception(f"Failed to create knowledge source: {response.status_code}")


def check_ingestion_status(config, max_wait_seconds=300):
    """インジェストの状態を確認"""
    print(f"\n{'='*60}")
    print("インジェストの状態を確認中...")
    print(f"{'='*60}")
    
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://search.azure.com/.default").token
    except Exception as e:
        print(f"✗ 認証に失敗: {str(e)}")
        return False
    
    endpoint = f"{config['search_endpoint']}/knowledgesources/{config['knowledge_source_name']}/status"
    params = {"api-version": config["search_api_version"]}
    headers = {"Authorization": f"Bearer {token}"}
    
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        response = requests.get(endpoint, params=params, headers=headers)
        
        if response.status_code == 200:
            status_data = response.json()
            sync_status = status_data.get("synchronizationStatus", "unknown")
            
            print(f"\n同期状態: {sync_status}")
            
            if "currentSynchronizationState" in status_data and status_data["currentSynchronizationState"]:
                current = status_data["currentSynchronizationState"]
                print(f"  - 処理済みアイテム: {current.get('itemUpdatesProcessed', 0)}")
                print(f"  - 失敗: {current.get('itemsUpdatesFailed', 0)}")
                print(f"  - スキップ: {current.get('itemsSkipped', 0)}")
            
            if sync_status == "active":
                print("\n✓ インジェストが完了しました")
                return True
        
        print(".", end="", flush=True)
        time.sleep(10)
    
    print(f"\n⚠ {max_wait_seconds}秒経過しましたが、まだインジェスト中です")
    return False


def reset_and_run_indexer(config):
    """インデクサーをリセットして再実行"""
    print(f"\n{'='*60}")
    print("インデクサーをリセットして再実行中...")
    print(f"{'='*60}")
    
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://search.azure.com/.default").token
    except Exception as e:
        print(f"✗ 認証に失敗: {str(e)}")
        return False
    
    # インデクサー名はナレッジソース名 + "-indexer"
    indexer_name = f"{config['knowledge_source_name']}-indexer"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    params = {"api-version": config["search_api_version"]}
    
    # インデクサーをリセット
    reset_endpoint = f"{config['search_endpoint']}/indexers/{indexer_name}/reset"
    print(f"\nインデクサー '{indexer_name}' をリセット中...")
    reset_response = requests.post(reset_endpoint, params=params, headers=headers)
    
    if reset_response.status_code in [200, 204]:
        print(f"✓ インデクサーをリセットしました")
    else:
        print(f"⚠ インデクサーのリセットに失敗: {reset_response.status_code}")
        print(reset_response.text)
    
    # インデクサーを再実行
    run_endpoint = f"{config['search_endpoint']}/indexers/{indexer_name}/run"
    print(f"\nインデクサー '{indexer_name}' を再実行中...")
    run_response = requests.post(run_endpoint, params=params, headers=headers)
    
    if run_response.status_code in [200, 202, 204]:
        print(f"✓ インデクサーを再実行しました")
        
        # インデクサーの実行状態を確認
        status_endpoint = f"{config['search_endpoint']}/indexers/{indexer_name}/status"
        print(f"\nインデクサーの実行状態を確認中...")
        
        max_wait = 60  # 60秒待機
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status_response = requests.get(status_endpoint, params=params, headers=headers)
            if status_response.status_code == 200:
                status_data = status_response.json()
                last_result = status_data.get("lastResult")
                if last_result:
                    status_value = last_result.get("status")
                    if status_value == "success":
                        print(f"✓ インデクサーの実行が完了しました")
                        print(f"  - 処理済みドキュメント: {last_result.get('itemsProcessed', 0)}")
                        print(f"  - 失敗: {last_result.get('itemsFailed', 0)}")
                        return True
                    elif status_value == "inProgress":
                        print(".", end="", flush=True)
                    elif status_value == "transientFailure":
                        print(f"\n⚠ 一時的なエラーが発生しましたが、再試行します")
                    else:
                        print(f"\n⚠ インデクサーの状態: {status_value}")
            time.sleep(5)
        
        print(f"\n✓ インデクサーを開始しました（バックグラウンドで実行中）")
        return True
    else:
        print(f"✗ インデクサーの再実行に失敗: {run_response.status_code}")
        print(run_response.text)
        return False


def create_knowledge_base(config):
    """ナレッジベースを作成"""
    print(f"\n{'='*60}")
    print("ナレッジベースを作成中...")
    print(f"{'='*60}")
    
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://search.azure.com/.default").token
    except Exception as e:
        print(f"✗ 認証に失敗: {str(e)}")
        return False
    
    endpoint = f"{config['search_endpoint']}/knowledgebases/{config['knowledge_base_name']}"
    params = {"api-version": config["search_api_version"]}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    knowledge_base_definition = {
        "name": config["knowledge_base_name"],
        "description": "Blob Storageからのナレッジベース",
        "knowledgeSources": [
            {
                "name": config["knowledge_source_name"]
            }
        ],
        "models": [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": config["openai_endpoint"],
                    "deploymentId": config["openai_model"],
                    "modelName": config["openai_model"]
                }
            }
        ],
        "outputMode": "answerSynthesis",
        "answerInstructions": "取得したドキュメントに基づいて、簡潔で情報豊富な回答を提供してください。",
        "retrievalReasoningEffort": {
            "kind": "medium"
        }
    }
    
    response = requests.put(endpoint, params=params, headers=headers, json=knowledge_base_definition)
    
    if response.status_code in [200, 201, 204]:
        print(f"✓ ナレッジベース '{config['knowledge_base_name']}' を作成しました")
        return True
    else:
        print(f"✗ ナレッジベースの作成に失敗: {response.status_code}")
        print(response.text)
        return False


def test_retrieve(config):
    """取得テストを実行"""
    if not config["run_retrieve_test"]:
        print("\n取得テストはスキップされました")
        return
    
    print(f"\n{'='*60}")
    print("取得テストを実行中...")
    print(f"{'='*60}")
    
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        token = credential.get_token("https://search.azure.com/.default").token
    except Exception as e:
        print(f"✗ 認証に失敗: {str(e)}")
        return
    
    endpoint = f"{config['search_endpoint']}/knowledgebases/{config['knowledge_base_name']}/retrieve"
    params = {"api-version": config["search_api_version"]}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    retrieve_request = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": config["retrieve_test_query"]
                    }
                ]
            }
        ]
    }
    
    response = requests.post(endpoint, params=params, headers=headers, json=retrieve_request)
    
    if response.status_code == 200:
        results = response.json()
        print(f"\n✓ 取得成功")
        print(f"\nクエリ: {config['retrieve_test_query']}")
        print(f"\n結果:")
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"\n✗ 取得に失敗: {response.status_code}")
        print(response.text)


def main():
    """メイン処理"""
    try:
        print("\n" + "="*60)
        print("Azure AI Search - Blob Knowledge Source Creator")
        print("="*60)
        
        # Azure CLIのログイン状態を確認
        if not check_azure_login():
            print("\n⚠ Azure CLIにログインしてから再度実行してください")
            print("\nコマンド: az login")
            return
        
        # 環境変数を読み込む
        config = load_environment()
        print("\n✓ 環境変数を読み込みました")
        print(f"  - 認証方法: Entra ID (System-Assigned Managed Identity)")
        print(f"  - Search Endpoint: {config['search_endpoint']}")
        print(f"  - Blob Container: {config['blob_container_name']}")
        print(f"  - Knowledge Source: {config['knowledge_source_name']}")
        print(f"  - Knowledge Base: {config['knowledge_base_name']}")
        print(f"  - Content Extraction: STANDARD mode (with Content Understanding)")
        if config.get('ai_services_endpoint'):
            print(f"  - AI Services: {config['ai_services_endpoint']}")
        if config.get('asset_store_container_name'):
            print(f"  - Asset Store: {config['asset_store_container_name']}")
        
        # ナレッジソースを作成
        create_knowledge_source(config)
        
        # インジェストの状態を確認（最大5分待機）
        check_ingestion_status(config, max_wait_seconds=300)
        
        # インデクサーをリセットして再実行（最新の設定で再処理）
        reset_and_run_indexer(config)
        
        # ナレッジベースを作成
        create_knowledge_base(config)
        
        # 取得テストを実行
        test_retrieve(config)
        
        print(f"\n{'='*60}")
        print("✓ すべての処理が完了しました")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n✗ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
