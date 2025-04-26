import hashlib
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackContext
import json
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv
from flask import Flask
app = Flask(__name__)

@app.route('/ping')
def ping():
    return "alive", 200


load_dotenv()
SUBSCRIBERS_FILE = "subscribers.json"

def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "r") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_subscribers():
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(list(subscribers), f)


subscribers = load_subscribers()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\nUse /subscribe to get notified when new results come out.\n"
        "Use /unsubscribe if you want to stop receiving updates."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id not in subscribers:
        subscribers.add(user_id)
        save_subscribers()
        await update.message.reply_text("You've subscribed to notifications!")
    else:
        await update.message.reply_text("You're already subscribed.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if user_id in subscribers:
        subscribers.remove(user_id)
        save_subscribers()
        await update.message.reply_text("You've been unsubscribed from notifications. We miss you :(")
    else:
        await update.message.reply_text("You're not subscribed. Subscribe now!")

# Notify all subscribers (you could hook this to an event or admin-only command)
async def notify_all(context: ContextTypes.DEFAULT_TYPE, old, data):
    message = """
    <b>📢 New Results Out !!!</b>\n
    """
    data = data["Data"]
    old = old["Data"]
    old_items = []
    for y in old:
        old_items.append(y["Item"])
    for x in data:
        if x["Item"] not in list(old):
            Details = x['Details']
            message += f"<b>{x['Item']}</b> - {x['Category']}\n"
            message += "————————————\n"
            for i in Details:
                message += f"<b>{i['Position']} • {i['Points']}</b>\n"
                message += f"<b>{i['Name']}</b>\n"
                message += f"<b>{i['ChestNo']}</b>\n"
                message += f"<b>{i['Company']}</b>\n\n"
            message += "\n\n\n"
    print(message)
    for user_id in subscribers:
        try:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to notify {user_id}: {e}")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


# Main function
async def main():
    global subscribers
    subscribers = load_subscribers()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))

    # Schedule scraping every 5 minutes
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scrape, "interval", minutes=0.5, args=[app.bot])
    scheduler.start()

    print("Bot running...")
    await app.run_polling()



async def scrape(context):
    data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('https://tarang.progressivetechies.org/website/home')
        await page.get_by_text("Results").click()
        time.sleep(1)
        content = await page.content()
        soup = BeautifulSoup(content, features="html.parser")
        top_level = soup.css.select_one(".css-cxtdg3")
        for child in top_level.children:
            temp = {}
            Type = child.css.select_one(".css-118rqfc").string
            Category = child.css.select_one(".css-t0aa7t").string
            print("------------------")
            print(Type, Category)
            temp["Item"] = Type
            temp["Category"] = Category
            temp2 = []

            for rank in child.css.select(".css-xw1di6"):
                temp3 = {}
                Position = rank.css.select_one(".css-1rpbqdy").get_text(strip=True)
                Position, Points = Position.split("•")
                Name = rank.css.select_one(".css-118rqfc").string
                ChestNo = rank.css.select_one(".css-t0aa7t").string
                Company = rank.css.select_one(".css-ywq6ra").string
                print(f"Postion: {Position}")
                print(f"Points: {Points}")
                print(f"Name: {Name}")
                print(f"ChestNo: {ChestNo}")
                print(f"Company: {Company}")
                print("--------")
                temp3["Postion"] = Position
                temp3["Points"] = Points
                temp3["Name"] = Name
                temp3["ChestNo"] = ChestNo
                temp3["Company"] = Company

                temp2.append(temp3)

            temp["Details"] = temp2
            data.append(temp)
        #page.screenshot(path=f'example-{browser_type.name}.png')
        await browser.close()
    data = {"Data": data}
    with open("data.json", "r") as file:
        prev = json.load(file)
    print(data["Data"])

    if prev != data:
        with open("data.json", "w") as file:
            json.dump(data, file, indent=2)
        print("New Notification!!")
        await notify_all(context, prev, data)


import asyncio
import nest_asyncio

if __name__ == "__main__":
    nest_asyncio.apply()  # <- patch the running loop
    asyncio.get_event_loop().run_until_complete(main())
