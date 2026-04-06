"""
Azure AI Search - 認証とRBACの診断ツール
"""

import subprocess
import json
import sys
import platform
from dotenv import load_dotenv
import os

# Windowsでは az.cmd を使用
AZ_COMMAND = 'az.cmd' if platform.system() == 'Windows' else 'az'


def run_command(cmd):
    """コマンドを実行して結果を返す"""
    try:
        # Windows対応: shell=Trueを使用
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            shell=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def check_azure_cli():
    """Azure CLIのインストール確認"""
    print("\n" + "="*60)
    print("1. Azure CLIのチェック")
    print("="*60)
    
    success, stdout, stderr = run_command(f"{AZ_COMMAND} --version")
    if success:
        print("✓ Azure CLIがインストールされています")
        version_line = stdout.split('\n')[0]
        print(f"  {version_line}")
        return True
    else:
        print("✗ Azure CLIがインストールされていません")
        print("\nインストール方法:")
        print("  https://docs.microsoft.com/cli/azure/install-azure-cli")
        return False


def check_login():
    """ログイン状態の確認"""
    print("\n" + "="*60)
    print("2. ログイン状態のチェック")
    print("="*60)
    
    success, stdout, stderr = run_command(f"{AZ_COMMAND} account show")
    if success:
        account = json.loads(stdout)
        print("✓ Azure CLIにログインしています")
        print(f"  - アカウント: {account.get('user', {}).get('name', 'N/A')}")
        print(f"  - サブスクリプション: {account.get('name', 'N/A')} ({account.get('id', 'N/A')})")
        print(f"  - テナント: {account.get('tenantId', 'N/A')}")
        print(f"  - 状態: {account.get('state', 'N/A')}")
        return True, account
    else:
        print("✗ Azure CLIにログインしていません")
        print("\nログイン方法:")
        print("  az login")
        return False, None


def check_search_service(subscription_id, resource_group, search_service):
    """AI Searchサービスの確認"""
    print("\n" + "="*60)
    print("3. Azure AI Searchサービスのチェック")
    print("="*60)
    
    cmd = f"{AZ_COMMAND} search service show --name {search_service} --resource-group {resource_group} --subscription {subscription_id}"
    success, stdout, stderr = run_command(cmd)
    
    if success:
        service = json.loads(stdout)
        print(f"✓ Azure AI Searchサービスが見つかりました")
        print(f"  - 名前: {service.get('name', 'N/A')}")
        print(f"  - リソースグループ: {service.get('resourceGroup', 'N/A')}")
        print(f"  - 場所: {service.get('location', 'N/A')}")
        print(f"  - SKU: {service.get('sku', {}).get('name', 'N/A')}")
        
        # マネージドIDの確認
        identity = service.get('identity', {})
        if identity and identity.get('type') == 'SystemAssigned':
            principal_id = identity.get('principalId', 'N/A')
            print(f"\n  ✓ システム割り当てマネージドIDが有効")
            print(f"    - Principal ID: {principal_id}")
            return True, service, principal_id
        else:
            print(f"\n  ✗ システム割り当てマネージドIDが無効")
            print(f"\n  有効化コマンド:")
            print(f"    az search service update --name {search_service} --resource-group {resource_group} --identity-type SystemAssigned")
            return False, service, None
    else:
        print(f"✗ Azure AI Searchサービスが見つかりません")
        print(f"\nエラー: {stderr}")
        return False, None, None


def check_role_assignments(principal_id, subscription_id):
    """ロール割り当ての確認"""
    print("\n" + "="*60)
    print("4. ロール割り当てのチェック")
    print("="*60)
    
    cmd = f"{AZ_COMMAND} role assignment list --assignee {principal_id} --all --subscription {subscription_id}"
    success, stdout, stderr = run_command(cmd)
    
    if success:
        assignments = json.loads(stdout)
        
        if len(assignments) > 0:
            print(f"✓ {len(assignments)}個のロール割り当てが見つかりました:\n")
            
            required_roles = [
                "Storage Blob Data Reader",
                "Storage Blob Data Contributor",
                "Cognitive Services OpenAI User",
                "Cognitive Services User"
            ]
            
            assigned_roles = {}
            for assignment in assignments:
                role_name = assignment.get('roleDefinitionName', 'N/A')
                scope = assignment.get('scope', 'N/A')
                print(f"  - {role_name}")
                print(f"    スコープ: {scope}")
                assigned_roles[role_name] = scope
            
            print(f"\n必要なロールのチェック:")
            for role in required_roles:
                if role in assigned_roles:
                    print(f"  ✓ {role}")
                else:
                    print(f"  ✗ {role} (未割り当て)")
            
            return True
        else:
            print("✗ ロール割り当てが見つかりません")
            print("\nSETUP_RBAC.mdを参照して、必要なロールを割り当ててください")
            return False
    else:
        print(f"✗ ロール割り当ての確認に失敗")
        print(f"エラー: {stderr}")
        return False


def check_user_permissions(subscription_id, resource_group, search_service):
    """現在のユーザーの権限確認"""
    print("\n" + "="*60)
    print("5. 現在のユーザーの権限チェック")
    print("="*60)
    
    # 現在のユーザーのオブジェクトIDを取得
    success, stdout, stderr = run_command(f"{AZ_COMMAND} ad signed-in-user show --query id -o tsv")
    
    if success:
        user_id = stdout.strip()
        
        # Search Service Contributorロールの確認
        cmd = f"{AZ_COMMAND} role assignment list --assignee {user_id} --scope /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Search/searchServices/{search_service}"
        success2, stdout2, stderr2 = run_command(cmd)
        
        if success2:
            assignments = json.loads(stdout2)
            
            has_contributor = any(
                a.get('roleDefinitionName') in ['Search Service Contributor', 'Contributor', 'Owner']
                for a in assignments
            )
            
            if has_contributor:
                print("✓ Azure AI Searchサービスへの管理権限があります")
                return True
            else:
                print("✗ Azure AI Searchサービスへの管理権限がありません")
                print("\n必要なロール: Search Service Contributor")
                print("\n割り当てコマンド:")
                print(f"  az role assignment create \\")
                print(f"    --role 'Search Service Contributor' \\")
                print(f"    --assignee {user_id} \\")
                print(f"    --scope /subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Search/searchServices/{search_service}")
                return False
        else:
            print(f"✗ 権限の確認に失敗: {stderr2}")
            return False
    else:
        print(f"✗ ユーザーIDの取得に失敗: {stderr}")
        return False


def check_environment_variables():
    """環境変数の確認"""
    print("\n" + "="*60)
    print("6. 環境変数のチェック (.env)")
    print("="*60)
    
    load_dotenv()
    
    required_vars = {
        "AI_SEARCH_ENDPOINT": "Azure AI Searchのエンドポイント",
        "AZURE_OPENAI_API_ENDPOINT": "Azure OpenAIのエンドポイント",
        "blob_storage_account": "Blob Storageアカウント",
        "blob_container_name": "Blobコンテナー名",
        "AI_SERVICES_ENDPOINT": "AI Servicesエンドポイント",
    }
    
    all_set = True
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            # 機密情報をマスク
            if "endpoint" in var.lower() or "account" in var.lower():
                masked = value[:30] + "..." if len(value) > 30 else value
                print(f"  ✓ {var}: {masked}")
            else:
                print(f"  ✓ {var}: {value}")
        else:
            print(f"  ✗ {var}: 未設定 ({description})")
            all_set = False
    
    return all_set


def main():
    print("\n" + "="*60)
    print("Azure AI Search - 認証とRBACの診断ツール")
    print("="*60)
    
    # Azure CLIのチェック
    if not check_azure_cli():
        return
    
    # ログイン状態のチェック
    logged_in, account = check_login()
    if not logged_in:
        return
    
    subscription_id = account.get('id')
    
    # 環境変数のチェック
    env_ok = check_environment_variables()
    if not env_ok:
        print("\n⚠ .envファイルに必要な環境変数を設定してください")
    
    # AI Searchサービスの情報を取得
    print("\n" + "="*60)
    print("Azure AI Searchサービス情報の入力")
    print("="*60)
    
    # 環境変数から取得を試みる
    search_endpoint = os.getenv("AI_SEARCH_ENDPOINT", "")
    if search_endpoint:
        # エンドポイントからサービス名を抽出
        import re
        match = re.search(r'https://([^.]+)\.search\.windows\.net', search_endpoint)
        if match:
            search_service = match.group(1)
            print(f"\n環境変数から検出:")
            print(f"  サービス名: {search_service}")
        else:
            search_service = input("\nAzure AI Searchサービス名: ")
    else:
        search_service = input("\nAzure AI Searchサービス名: ")
    
    resource_group = input("リソースグループ名: ")
    
    # AI Searchサービスのチェック
    search_ok, service, principal_id = check_search_service(subscription_id, resource_group, search_service)
    
    if search_ok and principal_id:
        # ロール割り当てのチェック
        check_role_assignments(principal_id, subscription_id)
    
    # 現在のユーザーの権限チェック
    check_user_permissions(subscription_id, resource_group, search_service)
    
    print("\n" + "="*60)
    print("診断完了")
    print("="*60)
    print("\n問題がある場合は、SETUP_RBAC.mdを参照して設定してください")


if __name__ == "__main__":
    main()
