import requests
import json

# Thông tin API của bạn
API_KEY = "ntd_tm8ogi2s5tjbma4a5chbbvxev2ezsk0l"
API_SECRET = "sk_hQdT3WUeAqOxiGaP9mmZ50fmRH9r6AZ29a9yTIJSs6bBbLWG"
BASE_URL = "https://apibankvn.com/api"

print("="*60)
print("🔍 TEST KẾT NỐI API BANKVN")
print("="*60)

headers = {
    "X-API-KEY": API_KEY,
    "X-API-SECRET": API_SECRET,
    "Content-Type": "application/json"
}

# TEST 1: Lấy thông tin tài khoản
print("\n📌 TEST 1: GET /v1/me")
print("-"*40)
try:
    response = requests.get(f"{BASE_URL}/v1/me", headers=headers, timeout=10)
    print(f"✅ Status: {response.status_code}")
    data = response.json()
    if data.get('status') == True:
        user = data.get('data', {})
        print(f"👤 User: {user.get('full_name')}")
        print(f"📧 Email: {user.get('email')}")
        print(f"💰 Balance: {user.get('wallet', {}).get('balance', 0)}đ")
        print("✅ Kết nối API THÀNH CÔNG!")
    else:
        print(f"❌ Lỗi: {data.get('message')}")
except Exception as e:
    print(f"❌ Lỗi: {e}")

# TEST 2: Lấy danh sách ngân hàng
print("\n📌 TEST 2: GET /v1/list-bank-accounts")
print("-"*40)
try:
    response = requests.get(f"{BASE_URL}/v1/list-bank-accounts", headers=headers, timeout=10)
    print(f"✅ Status: {response.status_code}")
    data = response.json()
    
    if data.get('status') == True:
        banks = data.get('data', {}).get('bank_accounts', [])
        print(f"✅ Tìm thấy {len(banks)} tài khoản ngân hàng:")
        for bank in banks:
            print(f"\n  🏦 Ngân hàng: {bank.get('bank_name')}")
            print(f"  📋 Số TK: {bank.get('account_number')}")
            print(f"  👤 Chủ TK: {bank.get('account_name')}")
            print(f"  🆔 Bank ID: {bank.get('bank_id')}")
            bank_id = bank.get('bank_id')
    else:
        print(f"❌ Lỗi: {data.get('message')}")
except Exception as e:
    print(f"❌ Lỗi: {e}")

# TEST 3: Tạo lệnh nạp
print("\n📌 TEST 3: POST /v1/recharge-orders")
print("-"*40)
try:
    # Lấy bank_id từ test 2
    bank_response = requests.get(f"{BASE_URL}/v1/list-bank-accounts", headers=headers, timeout=10)
    if bank_response.status_code == 200:
        bank_data = bank_response.json()
        if bank_data.get('status') == True:
            banks = bank_data.get('data', {}).get('bank_accounts', [])
            if banks:
                bank_id = banks[0].get('bank_id')
                print(f"✅ Sử dụng bank_id: {bank_id}")
                
                # Tạo lệnh nạp
                payload = {
                    "bank_id": bank_id,
                    "amount": 10000
                }
                response = requests.post(f"{BASE_URL}/v1/recharge-orders", 
                                         json=payload, 
                                         headers=headers, 
                                         timeout=10)
                print(f"✅ Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == True:
                        order = data.get('data', {})
                        print("✅ Tạo lệnh nạp THÀNH CÔNG!")
                        print(f"  📝 Mã lệnh: {order.get('order_code')}")
                        print(f"  💰 Số tiền: {order.get('amount')}đ")
                        print(f"  🏦 Ngân hàng: {order.get('bank_account', {}).get('bank_name')}")
                        print(f"  📋 Số TK: {order.get('bank_account', {}).get('account_number')}")
                        print(f"  👤 Chủ TK: {order.get('bank_account', {}).get('account_name')}")
                        print(f"  📝 Nội dung: {order.get('transfer_content')}")
                        print(f"  ⏰ Trạng thái: {order.get('status')}")
                    else:
                        print(f"❌ API báo lỗi: {data.get('message')}")
                else:
                    print(f"❌ HTTP Lỗi: {response.status_code}")
            else:
                print("❌ Không tìm thấy tài khoản ngân hàng")
        else:
            print(f"❌ Không lấy được danh sách ngân hàng")
    else:
        print(f"❌ Không thể lấy danh sách ngân hàng")
except Exception as e:
    print(f"❌ Lỗi: {e}")

print("\n" + "="*60)
print("✅ KẾT THÚC TEST")
print("="*60)