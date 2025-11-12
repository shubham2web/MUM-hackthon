"""
Quick Frontend Smoke Test

Tests that Phase 2 endpoints are accessible and working.
"""
import requests
import time

BASE_URL = "http://localhost:8000"

def test_server_health():
    """Test if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/memory/health", timeout=2)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
    except Exception as e:
        print(f"❌ Server not responding: {e}")
        print("   Please start server: cd backend && python server.py")
        return False
    return False

def test_diagnostics():
    """Test Phase 3 diagnostics endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/memory/diagnostics", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Diagnostics endpoint working")
            print(f"   Short-term: {data['memory_usage']['short_term_messages']} messages")
            return True
    except Exception as e:
        print(f"❌ Diagnostics failed: {e}")
        return False

def test_role_reversal_endpoints():
    """Test Phase 2 role reversal endpoints"""
    tests_passed = 0
    tests_total = 3
    
    # Test 1: Initialize debate
    try:
        response = requests.post(
            f"{BASE_URL}/memory/debate/start",
            json={"debate_id": "smoke_test_001"},
            timeout=2
        )
        if response.status_code == 200:
            print("✅ Debate initialization working")
            tests_passed += 1
    except Exception as e:
        print(f"❌ Debate init failed: {e}")
    
    # Test 2: Add memory
    try:
        response = requests.post(
            f"{BASE_URL}/memory/add",
            json={
                "role": "proponent",
                "content": "Test argument for smoke test"
            },
            timeout=2
        )
        if response.status_code == 201:
            print("✅ Memory addition working")
            tests_passed += 1
    except Exception as e:
        print(f"❌ Memory add failed: {e}")
    
    time.sleep(1)  # Give time for memory to index
    
    # Test 3: Role history
    try:
        response = requests.post(
            f"{BASE_URL}/memory/role/history",
            json={"role": "proponent"},
            timeout=2
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Role history working ({data['count']} memories)")
            tests_passed += 1
    except Exception as e:
        print(f"❌ Role history failed: {e}")
    
    return tests_passed == tests_total

def main():
    print("\n🧪 Frontend Smoke Test - Phase 2 & Phase 3\n")
    print("=" * 60)
    
    # Check server
    if not test_server_health():
        return 1
    
    print("\nTesting Phase 3 Diagnostics...")
    print("-" * 60)
    test_diagnostics()
    
    print("\nTesting Phase 2 Role Reversal Endpoints...")
    print("-" * 60)
    all_passed = test_role_reversal_endpoints()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All smoke tests passed!")
        print("\n🌐 Frontend should be accessible at:")
        print("   http://localhost:8000/")
        print("\n📚 Role Reversal UI panel should be visible on homepage")
        return 0
    else:
        print("⚠️  Some tests failed - check server logs")
        return 1

if __name__ == "__main__":
    exit(main())
