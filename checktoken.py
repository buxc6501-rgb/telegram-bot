import asyncio, logging, sys, traceback
from telegram import Bot
from telegram.error import InvalidToken, TelegramError
from telegram.ext import Application

# Bật logging DEBUG để thấy mọi log của thư viện
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Buộc flush output ngay
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

TOKEN = "8770603050:AAEVcAsHAWG-PWUYNNAlpSj5r-Eedfl3Lh8"

async def main():
    print("1. Bắt đầu kiểm tra token...")
    bot = Bot(token=TOKEN)
    try:
        print("2. Đang gọi getMe()...")
        me = await bot.get_me()
        print(f"3. Kết nối OK! Bot: @{me.username} (ID: {me.id})")
    except InvalidToken:
        print("❌ Token không hợp lệ.")
        return
    except TelegramError as e:
        print(f"❌ Lỗi Telegram: {e}")
        return

    print("4. Token OK, tạo Application...")
    try:
        app = Application.builder().token(TOKEN).build()
        print("5. Application đã tạo. Bắt đầu polling...")
        await app.run_polling()
    except Exception as e:
        print(f"❌ Lỗi khi tạo Application/polling: {e}")
        traceback.print_exc()
        logger.exception("Chi tiết lỗi:")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot dừng.")
    except Exception as e:
        print(f"❌ Lỗi ngoài cùng: {e}")
        traceback.print_exc()
        logger.exception("Lỗi ngoài cùng:")