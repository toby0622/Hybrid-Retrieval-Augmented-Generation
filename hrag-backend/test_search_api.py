import json

import requests

BASE_URL = "http://localhost:8000"


def test_search():
    print("Testing Document Search...")
    try:
        # Test 1: List documents without search
        response = requests.get(f"{BASE_URL}/documents?limit=5")
        if response.status_code == 200:
            print(f"List documents successful. Count: {len(response.json())}")
        else:
            print(f"List documents failed: {response.text}")

        # Test 2: List documents WITH search (mock search)
        response = requests.get(f"{BASE_URL}/documents?limit=5&search=test")
        if response.status_code == 200:
            print(f"Search documents successful. Count: {len(response.json())}")
        else:
            print(f"Search documents failed: {response.text}")

    except Exception as e:
        print(f"Document search test error: {e}")

    print("\nTesting Node Search...")
    try:
        # Test 3: List nodes without search
        response = requests.get(f"{BASE_URL}/nodes?limit=5")
        if response.status_code == 200:
            print(f"List nodes successful. Count: {len(response.json())}")
        else:
            print(f"List nodes failed: {response.text}")

        # Test 4: List nodes WITH search (mock search)
        response = requests.get(f"{BASE_URL}/nodes?limit=5&search=test")
        if response.status_code == 200:
            print(f"Search nodes successful. Count: {len(response.json())}")
        else:
            print(f"Search nodes failed: {response.text}")

    except Exception as e:
        print(f"Node search test error: {e}")


if __name__ == "__main__":
    test_search()
