import telebot
from telebot import types
import yt_dlp as ytdl_module
import os
import subprocess
import platform
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys

# 🔑 ВСТАВЬ СВОЙ ТОКЕН (позже уберём)
TOKEN = "Токен"

if TOKEN == "ВСТАВЬ_ТОКЕН_СЮДА" or len(TOKEN) < 40 or ':' not in TOKEN:
    print("❌ Токен не вставлен или неверный. Получите токен у @BotFather.")
    sys.exit(1)

# Определяем пути к программам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if platform.system() == 'Windows':
    FFMPEG_PATH = os.path.join(BASE_DIR, 'ffmpeg.exe')
    YTDLP_PATH = os.path.join(BASE_DIR, 'yt-dlp.exe')
else:
    # На Linux они будут установлены глобально
    FFMPEG_PATH = 'ffmpeg'
    YTDLP_PATH = 'yt-dlp'

# Проверка существования только на Windows
if platform.system() == 'Windows':
    if not os.path.exists(FFMPEG_PATH):
        print(f"❌ Не найден {FFMPEG_PATH}. Положи ffmpeg.exe в папку с main.py")
        sys.exit(1)
    if not os.path.exists(YTDLP_PATH):
        print(f"❌ Не найден {YTDLP_PATH}. Положи yt-dlp.exe в папку с main.py")
        sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# ── ПРИВЕТСТВИЕ ──
@bot.message_handler(commands=['start'])
def start(m):
    text = (
        "Привет! Я твой медиа-бот 🦾\n\n"
        "🎬 *Скачать TikTok:* Просто кинь ссылку.\n"
        "⚙️ *Обработка медиа:* Скинь мне любое видео или аудио, "
        "и я выдам меню с выбором формата."
    )
    bot.reply_to(m, text, parse_mode='Markdown')


# ── СКАЧИВАНИЕ TIKTOK ──
@bot.message_handler(func=lambda m: 'tiktok.com' in m.text)
def handle_tiktok(m):
    msg = bot.reply_to(m, "⏳ Скачиваю видео...")
    video_path = f"video_{m.chat.id}.mp4"
    try:
        subprocess.run(
            ['yt-dlp', '-o', video_path, m.text],
            check=True, capture_output=True, text=True
        )
        if not os.path.exists(video_path):
            raise FileNotFoundError("Файл не был создан")
        with open(video_path, 'rb') as f:
            bot.send_video(m.chat.id, f)
    except subprocess.CalledProcessError as e:
        err = e.stderr[:200] if e.stderr else "Неизвестная ошибка"
        bot.send_message(m.chat.id, f"❌ Ошибка скачивания TikTok: {err}")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка: {e}")
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        try:
            bot.delete_message(m.chat.id, msg.message_id)
        except:
            pass


# ── ПРИЁМ МЕДИА И КНОПКИ ──
@bot.message_handler(content_types=['video', 'audio', 'document'])
def handle_media(m):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("В голосовое 🎙", callback_data="to_voice")
    btn2 = types.InlineKeyboardButton("В кружок ⭕️", callback_data="to_round")
    btn3 = types.InlineKeyboardButton("В MP3 🎵", callback_data="to_mp3")
    markup.row(btn1, btn2)
    markup.row(btn3)
    bot.reply_to(m, "Что сделать с этим файлом?", reply_markup=markup)


# ── ОБРАБОТКА КНОПОК (устойчивая, ошибки видны) ──
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    bot.answer_callback_query(call.id)  # чтобы не было повторов

    orig_msg = call.message.reply_to_message
    if not orig_msg:
        bot.send_message(call.message.chat.id, "❌ Файл не найден, отправь заново.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    file_id = None
    is_video = False
    if orig_msg.video:
        file_id = orig_msg.video.file_id
        is_video = True
    elif orig_msg.audio:
        file_id = orig_msg.audio.file_id
    elif orig_msg.document:
        file_id = orig_msg.document.file_id

    if not file_id:
        bot.send_message(call.message.chat.id, "❌ Не удалось найти файл.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    status_msg = bot.send_message(call.message.chat.id, "⏳ Загружаю файл...")
    in_file = f'in_{call.message.chat.id}.tmp'
    out_file = f'out_{call.message.chat.id}.tmp'

    try:
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        with open(in_file, 'wb') as f:
            f.write(downloaded)

        action = call.data

        if action == "to_voice":
            out_file = f'out_{call.message.chat.id}.ogg'
            bot.edit_message_text("🎙 Делаю голосовое сообщение...",
                                  status_msg.chat.id, status_msg.message_id)
            cmd = [
                FFMPEG_PATH, '-i', in_file,
                '-vn', '-c:a', 'libopus', '-b:a', '48k', '-vbr', 'on', '-ac', '1',
                '-y', out_file
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            with open(out_file, 'rb') as voice:
                bot.send_voice(call.message.chat.id, voice)

        elif action == "to_mp3":
            out_file = f'out_{call.message.chat.id}.mp3'
            bot.edit_message_text("🎵 Вытаскиваю чистый звук...",
                                  status_msg.chat.id, status_msg.message_id)
            cmd = [
                FFMPEG_PATH, '-i', in_file,
                '-q:a', '0', '-map', 'a',
                '-y', out_file
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            with open(out_file, 'rb') as audio:
                bot.send_audio(call.message.chat.id, audio, title="Извлечённый звук")

        elif action == "to_round":
            if not is_video:
                bot.edit_message_text("❌ Из аудио кружок не сделать. Скинь видео!",
                                      status_msg.chat.id, status_msg.message_id)
                return
            out_file = f'out_{call.message.chat.id}.mp4'
            bot.edit_message_text("⭕️ Обрезаю видео под кружок...",
                                  status_msg.chat.id, status_msg.message_id)
            cmd = [
                FFMPEG_PATH, '-i', in_file,
                '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '24',
                '-c:a', 'aac', '-b:a', '128k',
                '-max_muxing_queue_size', '1024',
                '-y', out_file
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            with open(out_file, 'rb') as video_note:
                bot.send_video_note(call.message.chat.id, video_note)

    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if e.stderr else "Ошибка ffmpeg"
        bot.send_message(call.message.chat.id, f"❌ Ошибка обработки: {err[:500]}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ Неизвестная ошибка: {e}")
    finally:
        for f in [in_file, out_file]:
            if os.path.exists(f):
                os.remove(f)
        try:
            bot.delete_message(status_msg.chat.id, status_msg.message_id)
        except:
            pass
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass


# ── ВЕБ-СЕРВЕР (чтобы Render не усыплял) ──
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

def run_web():
    HTTPServer(("0.0.0.0", 10000), DummyHandler).serve_forever()

threading.Thread(target=run_web, daemon=True).start()


# ── ЗАПУСК ──
if __name__ == '__main__':
    print("✅ Бот успешно запущен!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)