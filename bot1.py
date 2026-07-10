import asyncio, logging, sys
from telegram.ext import Application

logging.basicConfig(level=logging.DEBUG)
TOKEN = "8770603050:AAEVcAsHAWG-PWUYNNAlpSj5r-Eedfl3Lh8"

async def main():
    print("Đang khởi tạo bot...")
    app = Application.builder().token(TOKEN).build()
    print("Bắt đầu polling...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Lỗi:", e)
        logging.exception(e)