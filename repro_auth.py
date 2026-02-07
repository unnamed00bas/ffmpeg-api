
import requests
import random
import string
import sys

BASE_URL = "https://ffmpeg.promaren.ru/api/v1"

def generate_username():
    return "testuser_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def main():
    username = generate_username()
    password = "TestUser123!"
    email = f"{username}@example.com"

    print(f"Attempting to register user: {username}")

    # 1. Register
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        if resp.status_code != 201:
            print(f"Registration failed: {resp.status_code} {resp.text}")
            sys.exit(1)
        print("Registration successful.")
    except Exception as e:
        print(f"Registration exception: {e}")
        sys.exit(1)

    # 2. Login
    print("Attempting to login...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", data={
            "username": username,
            "password": password
        })
        if resp.status_code != 200:
            print(f"Login failed: {resp.status_code} {resp.text}")
            sys.exit(1)
        
        token_data = resp.json()
        access_token = token_data["access_token"]
        print("Login successful. Token obtained.")
    except Exception as e:
        print(f"Login exception: {e}")
        sys.exit(1)

    # 3. Access Protected Endpoint
    print("Attempting to access protected endpoint /auth/me...")
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        
        if resp.status_code == 200:
            print("Access successful!")
            print(resp.json())
        else:
            print(f"Access failed: {resp.status_code} {resp.text}")
            sys.exit(1)

    except Exception as e:
        print(f"Access exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
