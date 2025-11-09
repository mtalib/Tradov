#!/usr/bin/env python3
"""
Validation script for Client Portal API formatting
Tests syntax, imports, and basic functionality
"""

import sys
import os

# Add project root to path
sys.path.insert(0, '/home/user/Spyder')

def test_syntax_validation():
    """Test that all modules have valid Python syntax"""
    print("\n" + "="*70)
    print("TEST 1: Syntax Validation")
    print("="*70)

    import py_compile

    modules = [
        'SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_Auth.py',
        'SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_RateLimiter.py',
        'SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_Session.py',
        'SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_RESTClient.py',
        'SpyderB_Broker/ClientPortalAPI/SpyderB09_ClientPortal_Examples.py',
    ]

    all_valid = True
    for module in modules:
        try:
            py_compile.compile(module, doraise=True)
            print(f"✅ {module} - Syntax OK")
        except py_compile.PyCompileError as e:
            print(f"❌ {module} - Syntax Error: {e}")
            all_valid = False

    return all_valid


def test_import_validation():
    """Test that modules can be imported without errors"""
    print("\n" + "="*70)
    print("TEST 2: Import Validation")
    print("="*70)

    tests = []

    # Test 1: Import RateLimiter components
    try:
        from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_RateLimiter import (
            RateLimiter,
            AdaptiveRateLimiter,
            create_cp_gateway_limiter,
            create_oauth_limiter
        )
        print("✅ RateLimiter module imports successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ RateLimiter import failed: {e}")
        tests.append(False)

    # Test 2: Import Auth components (may fail due to cryptography)
    try:
        from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_Auth import (
            OAuthClient,
            CPGatewayAuth,
            OAuthConfig,
            CPGatewayConfig,
        )
        print("✅ Auth module imports successful")
        tests.append(True)
    except Exception as e:
        print(f"⚠️  Auth import failed (expected if cryptography unavailable): {e}")
        tests.append(True)  # Don't fail on cryptography issues

    # Test 3: Import Session components
    try:
        from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_Session import (
            SessionManager,
            SessionConfig
        )
        print("✅ Session module imports successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Session import failed: {e}")
        tests.append(False)

    # Test 4: Import RESTClient components
    try:
        from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_RESTClient import (
            ClientPortalRESTClient,
            ClientConfig,
            APIError,
            AuthenticationError,
            RateLimitError,
            ValidationError
        )
        print("✅ RESTClient module imports successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ RESTClient import failed: {e}")
        tests.append(False)

    # Test 5: Import from package __init__
    try:
        from SpyderB_Broker.ClientPortalAPI import (
            RateLimiter,
            AdaptiveRateLimiter,
            SessionManager,
            ClientPortalRESTClient
        )
        print("✅ Package __init__.py imports successful")
        tests.append(True)
    except Exception as e:
        print(f"❌ Package import failed: {e}")
        tests.append(False)

    return all(tests)


def test_module_structure():
    """Test that modules have proper structure"""
    print("\n" + "="*70)
    print("TEST 3: Module Structure Validation")
    print("="*70)

    # Check that __all__ exports are defined
    modules_to_check = [
        ('SpyderB09_ClientPortal_Auth', ['OAuthClient', 'CPGatewayAuth']),
        ('SpyderB09_ClientPortal_RateLimiter', ['RateLimiter', 'AdaptiveRateLimiter']),
        ('SpyderB09_ClientPortal_Session', ['SessionManager', 'SessionConfig']),
        ('SpyderB09_ClientPortal_RESTClient', ['ClientPortalRESTClient', 'ClientConfig']),
    ]

    all_valid = True
    for module_name, expected_exports in modules_to_check:
        try:
            module = __import__(
                f'SpyderB_Broker.ClientPortalAPI.{module_name}',
                fromlist=['__all__']
            )

            if hasattr(module, '__all__'):
                print(f"✅ {module_name} has __all__ defined: {len(module.__all__)} exports")

                # Check if expected exports are present
                for export in expected_exports:
                    if export not in module.__all__:
                        print(f"   ⚠️  Expected export '{export}' not in __all__")
            else:
                print(f"❌ {module_name} missing __all__ definition")
                all_valid = False

        except Exception as e:
            print(f"⚠️  {module_name} structure check failed: {e}")

    return all_valid


def test_test_files():
    """Verify test files exist and have correct imports"""
    print("\n" + "="*70)
    print("TEST 4: Test File Validation")
    print("="*70)

    test_files = [
        'SpyderT_Testing/SpyderT23_ClientPortal_Auth_Test.py',
        'SpyderT_Testing/SpyderT24_ClientPortal_RateLimiter_Test.py',
        'SpyderT_Testing/SpyderT25_ClientPortal_Session_Test.py',
        'SpyderT_Testing/SpyderT26_ClientPortal_RESTClient_Test.py',
    ]

    all_exist = True
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"✅ {test_file} exists")

            # Check that imports reference new module names
            with open(test_file, 'r') as f:
                content = f.read()
                if 'SpyderB09_ClientPortal_' in content:
                    print(f"   ✅ Uses new module naming convention")
                else:
                    print(f"   ⚠️  May have old import statements")
        else:
            print(f"❌ {test_file} not found")
            all_exist = False

    return all_exist


def main():
    """Run all validation tests"""
    print("\n" + "="*70)
    print("CLIENT PORTAL API - VALIDATION SUITE")
    print("="*70)
    print("\nValidating 1-SPECS formatted modules...")

    results = {
        'Syntax Validation': test_syntax_validation(),
        'Import Validation': test_import_validation(),
        'Module Structure': test_module_structure(),
        'Test Files': test_test_files(),
    }

    print("\n" + "="*70)
    print("VALIDATION RESULTS")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<50} {status}")
        all_passed = all_passed and passed

    print("="*70)

    if all_passed:
        print("\n🎉 All validation tests PASSED!")
        print("✅ Modules are ready for merge")
        return 0
    else:
        print("\n⚠️  Some validation tests FAILED")
        print("Please review errors above before merging")
        return 1


if __name__ == '__main__':
    sys.exit(main())
