#!/usr/bin/env python3
# bot.py - Telegram CMS Bot - SePay QR + Auto Credit

import asyncio
import os
import json
import time
import random
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ======================== CONFIG ========================
BOT_TOKEN = "8770603050:AAEVcAsHAWG-PWUYNNAlpSj5r-Eedfl3Lh8"
ADMIN_IDS = [8343227510]

# SePay Config (ĐÃ CẬP NHẬT TOKEN)
SEPAY_API_TOKEN = "VOPZJZX7MVTL2NB6EZT9AYD3FQKP7IYKGIIDPP5RX3R8DG5CJAXH1SQVLUFNQM1O"
SEPAY_ACCOUNT_NUMBER = "0896451858"
SEPAY_ACCOUNT_NAME = "NGUYEN THI BICH HUYEN"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")
# bot.py - Phần 2

# ======================== DATABASE ========================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT,
                parent_id INTEGER,
                type TEXT NOT NULL DEFAULT 'category',
                price INTEGER DEFAULT 0,
                price_seller INTEGER DEFAULT 0,
                key_type TEXT,
                active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_type TEXT NOT NULL,
                key_value TEXT NOT NULL,
                status TEXT DEFAULT 'available',
                sold_to INTEGER,
                sold_at TEXT,
                FOREIGN KEY (sold_to) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pending_nap (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                trans_id TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        try:
            await db.execute('ALTER TABLE categories ADD COLUMN price_seller INTEGER DEFAULT 0')
        except:
            pass
        await db.commit()
    print("✅ Database initialized!")
    # bot.py - Phần 3

# ======================== CORE FUNCTIONS ========================
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?,?)', (user_id, username))
        await db.commit()

async def update_balance(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id=?', (amount, user_id))
        await db.commit()

async def get_categories(parent_id: Optional[int] = None, active_only: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = 'SELECT * FROM categories WHERE parent_id IS ?'
        params = [parent_id]
        if active_only:
            query += ' AND active=1'
        query += ' ORDER BY sort_order, id'
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_category(cat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM categories WHERE id=?', (cat_id,)) as cursor:
            return await cursor.fetchone()

async def add_category(name: str, icon: Optional[str], parent_id: Optional[int],
                       cat_type: str = 'category', price: int = 0, price_seller: int = 0,
                       key_type: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            INSERT INTO categories (name, icon, parent_id, type, price, price_seller, key_type)
            VALUES (?,?,?,?,?,?,?)
        ''', (name, icon, parent_id, cat_type, price, price_seller, key_type))
        await db.commit()
        return cursor.lastrowid

async def get_available_stock(key_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM keys WHERE key_type=? AND status="available"', (key_type,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def take_one_key(key_type: str, user_id: int) -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT id, key_value FROM keys WHERE key_type=? AND status="available" LIMIT 1', (key_type,))
        key = await cursor.fetchone()
        if not key:
            return None
        key_id, key_value = key
        await db.execute('UPDATE keys SET status="sold", sold_to=?, sold_at=datetime("now") WHERE id=?', (user_id, key_id))
        await db.commit()
        return key_value

async def add_key(key_type: str, key_value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO keys (key_type, key_value) VALUES (?,?)', (key_type, key_value))
        await db.commit()
        # bot.py - Phần 4

# ======================== SEPAY API ========================
def generate_sepay_qr(amount, description):
    """Tạo mã QR chuyển khoản SePay"""
    try:
        encoded_info = urllib.parse.quote(description)
        account_no = SEPAY_ACCOUNT_NUMBER
        
        # SePay QR URL
        qr_url = f"https://qr.sepay.vn/img?acc={account_no}&bank=MB&amount={amount}&des={encoded_info}"
        print(f"🔄 Tạo QR SePay: {qr_url}")
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(qr_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            qr_path = f"qr_{int(time.time())}.png"
            with open(qr_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ QR SePay thành công: {qr_path}")
            return qr_path
        else:
            print(f"❌ Lỗi tải QR SePay: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Lỗi tạo QR: {e}")
        return None

def sepay_get_transactions(limit=50):
    """Lấy danh sách giao dịch từ SePay"""
    url = "https://my.sepay.vn/userapi/transactions/list"
    headers = {
        "Authorization": f"Bearer {SEPAY_API_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {
        "account_number": SEPAY_ACCOUNT_NUMBER,
        "limit": limit
    }
    
    try:
        print(f"📡 Gọi SePay API lấy giao dịch...")
        response = requests.get(url, headers=headers, params=params, timeout=15)
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 200:
                transactions = data.get('transactions', [])
                print(f"✅ Lấy được {len(transactions)} giao dịch")
                return transactions
            else:
                print(f"❌ SePay Error: {data.get('message')}")
                return []
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Exception: {e}")
        return []

async def sepay_polling(context: ContextTypes.DEFAULT_TYPE):
    """Polling SePay mỗi 30 giây để kiểm tra giao dịch mới và tự động cộng tiền"""
    print("🔄 Bắt đầu polling SePay...")
    while True:
        await asyncio.sleep(30)
        try:
            transactions = sepay_get_transactions(50)
            if not transactions:
                continue
            
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM pending_nap WHERE status="pending"') as cursor:
                    pendings = await cursor.fetchall()
            
            if not pendings:
                continue
            
            print(f"📋 Có {len(pendings)} lệnh đang chờ, {len(transactions)} giao dịch mới")
            
            for pending in pendings:
                order_code = pending['trans_id']
                amount = pending['amount']
                user_id = pending['user_id']
                
                print(f"🔍 Tìm giao dịch với nội dung: {order_code}")
                
                for tx in transactions:
                    tx_content = tx.get('transaction_content', '')
                    tx_amount = abs(tx.get('amount', 0))
                    
                    if order_code.strip().lower() in tx_content.strip().lower() and tx_amount == amount:
                        print(f"✅ TÌM THẤY GIAO DỊCH KHỚP!")
                        print(f"   Nội dung: {tx_content}")
                        print(f"   Số tiền: {tx_amount}")
                        
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute('UPDATE pending_nap SET status="completed" WHERE id=?', (pending['id'],))
                            await db.commit()
                        
                        await update_balance(user_id, amount)
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)',
                                             (user_id, amount, 'deposit', f'Nạp tiền tự động - {order_code}'))
                            await db.commit()
                        
                        try:
                            user = await get_user(user_id)
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=f"✅ **Nạp tiền thành công!**\n\n"
                                     f"💰 Số tiền: +{amount:,}đ\n"
                                     f"💳 Số dư mới: {user['balance'] + amount:,}đ\n"
                                     f"📝 Mã giao dịch: `{order_code}`",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                        break
        except Exception as e:
            print(f"Polling error: {e}")
            # bot.py - Phần 5

# ======================== KEYBOARDS ========================
def admin_main_menu():
    keyboard = [
        [InlineKeyboardButton("📂 Danh mục", callback_data="admin:category")],
        [InlineKeyboardButton("🔑 Key", callback_data="admin:key")],
        [InlineKeyboardButton("👥 User", callback_data="admin:user")],
        [InlineKeyboardButton("💰 Tiền", callback_data="admin:money")],
        [InlineKeyboardButton("📊 Thống kê", callback_data="admin:stats")],
        [InlineKeyboardButton("⚙️ Cài đặt", callback_data="admin:settings")],
        [InlineKeyboardButton("📢 Thông báo", callback_data="admin:broadcast")],
    ]
    return InlineKeyboardMarkup(keyboard)

def user_main_menu():
    keyboard = [
        [InlineKeyboardButton("🛒 Mua Key", callback_data="user:buy")],
        [InlineKeyboardButton("💰 Số dư", callback_data="user:balance")],
        [InlineKeyboardButton("📋 Lịch sử", callback_data="user:history")],
        [InlineKeyboardButton("💳 Nạp tiền", callback_data="user:nap")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ======================== USER HANDLERS ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await create_user(user.id, user.username or user.full_name)
    await update.message.reply_text(
        f"Xin chào {user.full_name}!",
        reply_markup=user_main_menu()
    )

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None):
    cats = await get_categories(parent_id)
    keyboard = []
    for cat in cats:
        icon = cat['icon'] + ' ' if cat['icon'] else ''
        text = f"{icon}{cat['name']} {'▶️' if cat['type']=='category' else ''}"
        cb = f"cat:{cat['id']}" if cat['type']=='category' else f"prod:{cat['id']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=cb)])
    if parent_id is not None:
        p = await get_category(parent_id)
        grand = p['parent_id'] if p else None
        back = f"cat_back:{grand}" if grand is not None else "cat_back:root"
        keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data=back)])
    else:
        keyboard.append([InlineKeyboardButton("🔙 Trang chính", callback_data="user:menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("🛒 Chọn danh mục:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("🛒 Chọn danh mục:", reply_markup=reply_markup)

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "cat_back:root":
        await show_categories(update, context, None)
    elif data.startswith("cat_back:"):
        parent_id = int(data.split(":")[1])
        await show_categories(update, context, parent_id)
    elif data.startswith("cat:"):
        cat_id = int(data.split(":")[1])
        await show_categories(update, context, cat_id)
    elif data.startswith("prod:"):
        prod_id = int(data.split(":")[1])
        await product_detail(update, context, prod_id)

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: int):
    query = update.callback_query
    prod = await get_category(prod_id)
    if not prod or prod['type'] != 'product':
        await query.answer("Sản phẩm không tồn tại!")
        return
    user = await get_user(update.effective_user.id)
    role = user['role'] if user else 'user'
    if role == 'seller' and prod['price_seller'] > 0:
        price = prod['price_seller']
        label = "🏷️ Giá đại lý"
    else:
        price = prod['price']
        label = "💰 Giá bán lẻ"
    stock = await get_available_stock(prod['key_type'])
    text = f"🛍 {prod['name']}\n{label}: {price:,}đ\n📦 Còn: {stock}"
    parent = prod['parent_id']
    back_cb = f"cat_back:{parent}" if parent is not None else "cat_back:root"
    keyboard = [
        [InlineKeyboardButton("🛒 Mua ngay", callback_data=f"buy:{prod_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data=back_cb)],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    # bot.py - Phần 5

# ======================== KEYBOARDS ========================
def admin_main_menu():
    keyboard = [
        [InlineKeyboardButton("📂 Danh mục", callback_data="admin:category")],
        [InlineKeyboardButton("🔑 Key", callback_data="admin:key")],
        [InlineKeyboardButton("👥 User", callback_data="admin:user")],
        [InlineKeyboardButton("💰 Tiền", callback_data="admin:money")],
        [InlineKeyboardButton("📊 Thống kê", callback_data="admin:stats")],
        [InlineKeyboardButton("⚙️ Cài đặt", callback_data="admin:settings")],
        [InlineKeyboardButton("📢 Thông báo", callback_data="admin:broadcast")],
    ]
    return InlineKeyboardMarkup(keyboard)

def user_main_menu():
    keyboard = [
        [InlineKeyboardButton("🛒 Mua Key", callback_data="user:buy")],
        [InlineKeyboardButton("💰 Số dư", callback_data="user:balance")],
        [InlineKeyboardButton("📋 Lịch sử", callback_data="user:history")],
        [InlineKeyboardButton("💳 Nạp tiền", callback_data="user:nap")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ======================== USER HANDLERS ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await create_user(user.id, user.username or user.full_name)
    await update.message.reply_text(
        f"Xin chào {user.full_name}!",
        reply_markup=user_main_menu()
    )

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None):
    cats = await get_categories(parent_id)
    keyboard = []
    for cat in cats:
        icon = cat['icon'] + ' ' if cat['icon'] else ''
        text = f"{icon}{cat['name']} {'▶️' if cat['type']=='category' else ''}"
        cb = f"cat:{cat['id']}" if cat['type']=='category' else f"prod:{cat['id']}"
        keyboard.append([InlineKeyboardButton(text, callback_data=cb)])
    if parent_id is not None:
        p = await get_category(parent_id)
        grand = p['parent_id'] if p else None
        back = f"cat_back:{grand}" if grand is not None else "cat_back:root"
        keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data=back)])
    else:
        keyboard.append([InlineKeyboardButton("🔙 Trang chính", callback_data="user:menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text("🛒 Chọn danh mục:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("🛒 Chọn danh mục:", reply_markup=reply_markup)

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "cat_back:root":
        await show_categories(update, context, None)
    elif data.startswith("cat_back:"):
        parent_id = int(data.split(":")[1])
        await show_categories(update, context, parent_id)
    elif data.startswith("cat:"):
        cat_id = int(data.split(":")[1])
        await show_categories(update, context, cat_id)
    elif data.startswith("prod:"):
        prod_id = int(data.split(":")[1])
        await product_detail(update, context, prod_id)

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: int):
    query = update.callback_query
    prod = await get_category(prod_id)
    if not prod or prod['type'] != 'product':
        await query.answer("Sản phẩm không tồn tại!")
        return
    user = await get_user(update.effective_user.id)
    role = user['role'] if user else 'user'
    if role == 'seller' and prod['price_seller'] > 0:
        price = prod['price_seller']
        label = "🏷️ Giá đại lý"
    else:
        price = prod['price']
        label = "💰 Giá bán lẻ"
    stock = await get_available_stock(prod['key_type'])
    text = f"🛍 {prod['name']}\n{label}: {price:,}đ\n📦 Còn: {stock}"
    parent = prod['parent_id']
    back_cb = f"cat_back:{parent}" if parent is not None else "cat_back:root"
    keyboard = [
        [InlineKeyboardButton("🛒 Mua ngay", callback_data=f"buy:{prod_id}")],
        [InlineKeyboardButton("🔙 Quay lại", callback_data=back_cb)],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    # bot.py - Phần 6

async def buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    prod_id = int(query.data.split(":")[1])
    prod = await get_category(prod_id)
    if not prod or prod['type'] != 'product' or not prod['active']:
        await query.answer("Sản phẩm không khả dụng.", show_alert=True)
        return
    user = await get_user(user_id)
    if not user:
        await query.answer("Bạn chưa đăng ký.", show_alert=True)
        return
    if user['role'] == 'seller' and prod['price_seller'] > 0:
        price = prod['price_seller']
    else:
        price = prod['price']
    if user['balance'] < price:
        await query.answer(f"Không đủ tiền! Số dư: {user['balance']:,}đ", show_alert=True)
        return
    key_value = await take_one_key(prod['key_type'], user_id)
    if not key_value:
        await query.answer("Hết key! Liên hệ admin.", show_alert=True)
        return
    await update_balance(user_id, -price)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)',
                         (user_id, -price, 'purchase', f'Mua {prod["name"]}'))
        await db.commit()
    await query.edit_message_text(f"✅ Mua thành công!\n🔑 Key: `{key_value}`", parse_mode='Markdown')

async def user_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    print(f"📌 User menu: {data}")
    
    if data == "user:menu":
        await query.edit_message_text("🏠 Menu chính", reply_markup=user_main_menu())
    elif data == "user:balance":
        user = await get_user(update.effective_user.id)
        await query.edit_message_text(f"💰 Số dư: {user['balance']:,}đ")
    elif data == "user:history":
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 10',
                                  (update.effective_user.id,)) as cursor:
                trans = await cursor.fetchall()
        if trans:
            text = "📋 Lịch sử:\n" + "\n".join(
                [f"{t['type']}: {abs(t['amount']):,}đ - {t['description']} ({t['created_at']})" for t in trans])
        else:
            text = "Chưa có giao dịch."
        await query.edit_message_text(text)
    elif data == "user:buy":
        await show_categories(update, context, None)
    elif data == "user:nap":
        await query.edit_message_text(
            "💳 **Hướng dẫn nạp tiền:**\n\n"
            "Sử dụng lệnh: `/nap <số tiền>`\n"
            "Ví dụ: `/nap 100000`\n\n"
            "Bot sẽ tạo mã QR SePay cho bạn chuyển khoản.\n"
            "Sau khi chuyển, bot sẽ **tự động cộng tiền** vào số dư!",
            parse_mode='Markdown'
        )
        # bot.py - Phần 7

# ======================== LỆNH NẠP TIỀN ========================
async def nap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /nap <số tiền> - Tạo QR SePay và tự động cộng tiền"""
    
    print("🚨 LỆNH NAP ĐƯỢC GỌI!")
    print(f"📥 Tin nhắn: {update.message.text}")
    print(f"👤 User ID: {update.effective_user.id}")
    
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Vui lòng nhập số tiền.\n"
            "Ví dụ: `/nap 100000`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số tiền hợp lệ (số nguyên dương).")
        return
    
    print(f"📥 User {user_id} nạp {amount}đ")
    
    # Tạo mã giao dịch duy nhất
    order_code = f"NAP_{user_id}_{int(time.time())}_{random.randint(100,999)}"
    transfer_content = order_code
    
    print(f"📝 Mã giao dịch: {order_code}")
    
    # Lưu vào database với trạng thái pending
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO pending_nap (user_id, amount, trans_id) VALUES (?,?,?)',
                         (user_id, amount, order_code))
        await db.commit()
    
    context.user_data['nap_trans_id'] = order_code
    
    # Tạo QR SePay
    qr_path = generate_sepay_qr(amount, transfer_content)
    
    keyboard = [
        [InlineKeyboardButton("🔄 Kiểm tra đã nhận", callback_data=f"check_nap:{order_code}")],
        [InlineKeyboardButton("❌ Hủy", callback_data=f"cancel_nap:{order_code}")]
    ]
    
    caption = (
        f"💳 **Chuyển khoản {amount:,}đ**\n\n"
        f"🏦 Ngân hàng: **MB Bank**\n"
        f"📋 Số tài khoản: `{SEPAY_ACCOUNT_NUMBER}`\n"
        f"👤 Chủ tài khoản: {SEPAY_ACCOUNT_NAME}\n"
        f"📝 **Nội dung bắt buộc:** `{transfer_content}`\n\n"
        f"✅ **Bot sẽ TỰ ĐỘNG cộng tiền** khi bạn chuyển khoản thành công!\n"
        f"⏱️ Thời gian xử lý: 1-2 phút\n"
        f"⏰ Lệnh có hiệu lực trong 60 phút."
    )
    
    # Gửi QR
    if qr_path and os.path.exists(qr_path):
        try:
            with open(qr_path, 'rb') as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            os.remove(qr_path)
            print(f"✅ Đã gửi QR SePay cho user {user_id}")
            return
        except Exception as e:
            print(f"❌ Lỗi gửi ảnh QR: {e}")
    
    # Fallback: gửi link QR
    qr_url = f"https://qr.sepay.vn/img?acc={SEPAY_ACCOUNT_NUMBER}&bank=MB&amount={amount}&des={urllib.parse.quote(transfer_content)}"
    caption += f"\n\n🔗 [Bấm vào đây để xem mã QR]({qr_url})"
    await update.message.reply_text(
        caption,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )
    print(f"✅ Đã gửi QR link cho user {user_id}")
    # bot.py - Phần 8

# ======================== CANCEL NAP ========================
async def cancel_nap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_code = query.data.split(":")[1]
    if order_code:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE pending_nap SET status="failed" WHERE trans_id=?', (order_code,))
            await db.commit()
        await query.edit_message_text("✅ Đã hủy lệnh nạp tiền.")
    else:
        await query.edit_message_text("❌ Không tìm thấy lệnh nạp.")

# ======================== CHECK NAP ========================
async def check_nap_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra trạng thái lệnh nạp thủ công"""
    query = update.callback_query
    await query.answer()
    
    order_code = query.data.split(":")[1]
    print(f"🔍 Kiểm tra lệnh: {order_code}")
    
    status_msg = await query.message.reply_text("⏳ Đang kiểm tra giao dịch...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM pending_nap WHERE trans_id=?', (order_code,)) as cursor:
            pending = await cursor.fetchone()
    
    if not pending:
        await status_msg.edit_text("❌ Không tìm thấy lệnh nạp.")
        return
    
    if pending['status'] == 'completed':
        await status_msg.edit_text("✅ Đã xác nhận trước đó.")
        try:
            await query.message.delete()
        except:
            pass
        return
    
    # Lấy giao dịch từ SePay
    transactions = sepay_get_transactions(50)
    found = False
    
    if transactions:
        for tx in transactions:
            tx_content = tx.get('transaction_content', '')
            tx_amount = abs(tx.get('amount', 0))
            
            if order_code.strip().lower() in tx_content.strip().lower() and tx_amount == pending['amount']:
                found = True
                break
    
    if found:
        print(f"✅ Lệnh {order_code} đã thanh toán!")
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE pending_nap SET status="completed" WHERE id=?', (pending['id'],))
            await db.commit()
        
        await update_balance(pending['user_id'], pending['amount'])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)',
                             (pending['user_id'], pending['amount'], 'deposit', f'Nạp tiền tự động - {order_code}'))
            await db.commit()
        
        user = await get_user(pending['user_id'])
        
        try:
            await query.message.delete()
            await status_msg.delete()
        except:
            pass
        
        await query.message.reply_text(
            f"✅ **Nạp tiền thành công!**\n\n"
            f"💰 Số tiền: +{pending['amount']:,}đ\n"
            f"💳 Số dư mới: {user['balance'] + pending['amount']:,}đ\n"
            f"📝 Mã giao dịch: `{order_code}`",
            parse_mode='Markdown'
        )
    else:
        await status_msg.edit_text(
            f"⏳ Chưa nhận giao dịch.\n\n"
            f"🔍 **Bạn cần chuyển:**\n"
            f"• Số tiền: **{pending['amount']:,}đ**\n"
            f"• Nội dung: `{order_code}`\n\n"
            f"💡 **Lưu ý:**\n"
            f"• Chuyển khoản đúng nội dung `{order_code}`\n"
            f"• Có thể mất 1-2 phút để ngân hàng cập nhật\n"
            f"• Bấm lại nút 'Kiểm tra' sau vài phút\n"
            f"• Bot cũng sẽ tự động cộng tiền qua polling"
        )
        # bot.py - Phần 9

# ======================== ADMIN COMMANDS ========================
async def add_seller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Không có quyền.")
        return
    if not context.args:
        await update.message.reply_text("Cách dùng: /addseller <user_id>")
        return
    try:
        seller_id = int(context.args[0])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('UPDATE users SET role="seller" WHERE user_id=?', (seller_id,))
            await db.commit()
        await update.message.reply_text(f"✅ User {seller_id} đã thành Seller.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("👑 Admin Panel", reply_markup=admin_main_menu())
    else:
        await update.message.reply_text("👑 Admin Panel", reply_markup=admin_main_menu())
        # bot.py - Phần 10

# ======================== MAIN ========================
async def main():
    await init_db()
    
    print("🔄 Đang kiểm tra kết nối SePay...")
    test_transactions = sepay_get_transactions(1)
    if test_transactions is not None:
        print("✅ Kết nối SePay thành công!")
    else:
        print("⚠️ Không thể kết nối SePay. Kiểm tra lại API Token.")
    
    application = Application.builder().token(BOT_TOKEN).build()
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addseller", add_seller))
    application.add_handler(CommandHandler("nap", nap_command))
    print("✅ Đã đăng ký các lệnh: /start, /addseller, /nap")

    application.add_handler(CallbackQueryHandler(user_menu_handler, pattern="^user:"))
    application.add_handler(CallbackQueryHandler(category_callback, pattern="^(cat:|prod:|buy:|cat_back:)"))
    application.add_handler(CallbackQueryHandler(check_nap_callback, pattern="^check_nap:"))
    application.add_handler(CallbackQueryHandler(cancel_nap, pattern="^cancel_nap:"))
    application.add_handler(CallbackQueryHandler(admin_menu, pattern="^admin:menu$"))
    print("✅ Đã đăng ký các callback handlers")

    asyncio.create_task(sepay_polling(application.bot))
    print("🔄 Đã khởi tạo polling SePay")

    print("🚀 Đang khởi động bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    print("✅ Bot đã sẵn sàng!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())