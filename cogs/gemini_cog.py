# cogs/gemini_cog.py
# Bu Cog, Gemini API ile etkileşimi, metin ve görsel işlemeyi,
# güvenlik kontrollerini ve konu dışı yanıt takibini yönetir.

import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timezone
import io # PIL.Image.open için BytesIO gerekebilir
import re # Geçmiş sorgusu kontrolü için eklendi
import logging # logging seviyeleri için

# Google Gemini API
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold # Güvenlik ayarları için
import google.api_core.exceptions # API hatalarını yakalamak için

# Pillow (PIL) görsel işleme için
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("UYARI [GeminiCog]: 'Pillow' kütüphanesi bulunamadı. Görsel işleme özellikleri çalışmayabilir veya sınırlı olabilir.")

# aiohttp (görsel indirme için)
import aiohttp

# Yerel modüller
import config
import constants # BOT_ADI ve BOT_UZMANLIK_ALANI için eklendi
from utils import helpers # log_interaction, send_long_message, apply_timeout vb. için
from utils import persistence # save_chat_data için

class GeminiCog(commands.Cog, name="Gemini API Etkileşimi"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.model = None
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
        # Geçmiş sorgusu için anahtar kelimeler (küçük harf)
        self.past_query_keywords = ["hatırla", "neydi", "ne sordum", "ne konuştuk", "en son", "geçmiş", "önceki"]

        if config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(constants.GEMINI_MODEL_NAME)
                print(f"Gemini API'sine bağlanıldı. Model: {self.model.model_name}")
            except Exception as e:
                print(f"KRİTİK HATA [GeminiCog]: Gemini API yapılandırılamadı: {e}")
                self.model = None # Model kullanılamaz durumda
        else:
            print("KRİTİK HATA [GeminiCog]: GEMINI_API_KEY bulunamadı. GeminiCog çalışmayacak.")

    def is_past_related_query(self, text: str) -> bool:
        """Kullanıcının mesajının geçmişle ilgili bir soru olup olmadığını kontrol eder."""
        text_lower = text.lower()
        # Basit anahtar kelime kontrolü
        if any(keyword in text_lower for keyword in self.past_query_keywords):
            return True
        # Soru kalıplarını kontrol et (daha gelişmiş olabilir)
        if re.search(r"(en son|daha önce|geçen sefer)\s+(ne)\s+(sordum|konuştuk|demiştim|yazmıştım)", text_lower):
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # --- 1. BAŞLANGIÇ KONTROLLERİ (Gemini Cog için) ---
        if not self.model: # Model yüklenememişse hiçbir şey yapma
            return

        if message.author == self.bot.user: # Botun kendi mesajlarını yoksay
            return
        if message.guild is None: # DM mesajlarını bu Cog'da işleme
            return
        if message.content.startswith(config.COMMAND_PREFIX): # Komutları bu Cog'da işleme
            return
        if message.content.startswith(config.IGNORE_PREFIX): # Yoksayma prefix'li mesajları işleme
            return

        # Sadece izin verilen kanallardaki mesajları işle (config'den)
        if config.ALLOWED_CHANNEL_IDS and message.channel.id not in config.ALLOWED_CHANNEL_IDS:
            return

        user = message.author
        channel = message.channel
        chat_key = (channel.id, user.id)
        user_message_text = message.content.strip()
        image_parts_for_gemini = []
        image_filename_for_log = None

        helpers.log_interaction(user.id, user.name, "Kullanıcı", user_message_text, message.attachments)

        # --- 2. GÖRSEL İŞLEME (varsa) ---
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.filename.lower().endswith(constants.SUPPORTED_IMAGE_EXTENSIONS):
                print(f"GeminiCog: Görsel eki algılandı: {attachment.filename}, Boyut: {attachment.size} bytes")
                try:
                    async with aiohttp.ClientSession() as http_session:
                        async with http_session.get(attachment.url) as resp:
                            if resp.status == 200:
                                image_bytes = await resp.read()
                                image_filename_for_log = attachment.filename
                                if PIL_AVAILABLE:
                                    try:
                                        img = Image.open(io.BytesIO(image_bytes))
                                        mime_type = "image/jpeg"
                                        if image_filename_for_log.lower().endswith(".png"): mime_type = "image/png"
                                        elif image_filename_for_log.lower().endswith(".webp"): mime_type = "image/webp"
                                        image_parts_for_gemini.append({'mime_type': mime_type, 'data': image_bytes})
                                        print(f"GeminiCog: Görsel başarıyla indirildi ve işlendi: {image_filename_for_log} (MIME: {mime_type})")
                                    except Exception as pil_error:
                                        print(f"HATA [GeminiCog]: PIL ile görsel işlenirken hata: {pil_error}")
                                        await channel.send(f"{user.mention}, gönderdiğiniz görsel işlenirken bir sorun oluştu. Lütfen farklı bir formatta deneyin.", delete_after=7)
                                        helpers.log_interaction(user.id, user.name, "Sistem", f"PIL görsel işleme hatası: {pil_error}", log_to_console=True, console_level=logging.ERROR)
                                        return
                                else:
                                    mime_type = "image/jpeg"
                                    if image_filename_for_log.lower().endswith(".png"): mime_type = "image/png"
                                    elif image_filename_for_log.lower().endswith(".webp"): mime_type = "image/webp"
                                    image_parts_for_gemini.append({'mime_type': mime_type, 'data': image_bytes})
                                    print(f"GeminiCog: Görsel indirildi (PIL yok, MIME: {mime_type}): {image_filename_for_log}")
                            else:
                                error_msg = f"Görsel indirme hatası (Status: {resp.status}): {attachment.url}"
                                print(f"HATA [GeminiCog]: Görsel indirilemedi. Status: {resp.status}")
                                await channel.send(f"{user.mention}, görseli indirirken bir sorun oluştu (HTTP {resp.status}).", delete_after=7)
                                helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                                return
                except Exception as e_download:
                    error_msg = f"Görsel indirme/işleme istisnası: {e_download}"
                    print(f"HATA [GeminiCog]: Görsel indirilirken/işlenirken genel istisna: {e_download}")
                    await channel.send(f"{user.mention}, görsel işlenirken beklenmedik bir hata oluştu.", delete_after=7)
                    helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                    return
            elif not user_message_text:
                print(f"GeminiCog: Desteklenmeyen ek ({attachment.filename}) ve metin yok, mesaj yoksayıldı.")
                return

        if not user_message_text and not image_parts_for_gemini:
            print(f"GeminiCog: İşlenecek metin veya desteklenen görsel bulunamadı. Kullanıcı: {user.name}, Kanal: {channel.name}")
            return

        # --- 3. GEMINI API ÇAĞRISI ---
        try:
            async with channel.typing():
                if chat_key not in self.bot.active_chats_data:
                    self.bot.active_chats_data[chat_key] = {'history': [], 'last_interaction': datetime.now(timezone.utc), 'warning_sent': None}

                chat_session: genai.ChatSession = self.bot.active_chat_sessions.get(chat_key)

                if not chat_session:
                    retrieved_history_for_session = self.bot.active_chats_data.get(chat_key, {}).get('history', [])
                    if not retrieved_history_for_session and self.is_past_related_query(user_message_text):
                        custom_response = "Hafızam inaktiflikten ya da kullanıcı/yönetici isteğiyle sıfırlandığı için, eğer varsa, önceki sohbetlerimizi hatırlamıyorum."
                        print(f"GeminiCog: Hafıza boş ve geçmiş soruldu, özel yanıt veriliyor: {user.name}")
                        await helpers.send_long_message(self.bot, message, custom_response)
                        helpers.log_interaction(self.bot.user.id, self.bot.user.name, "Bot", custom_response, log_to_console=False)
                        return

                if not chat_session:
                    print(f"GeminiCog: Kullanıcı {user.name} (ID: {user.id}) için Kanal {channel.id}'de yeni Gemini sohbet oturumu başlatılıyor.")
                    retrieved_history_for_session = self.bot.active_chats_data.get(chat_key, {}).get('history', [])
                    api_history = []
                    for entry in retrieved_history_for_session:
                        role = 'user' if entry['author'] != self.bot.user.display_name else 'model'
                        api_history.append({'role': role, 'parts': [entry['content']]})

                    # --- DEĞİŞİKLİK: constants.BOT_ADI ve constants.BOT_UZMANLIK_ALANI kullanıldı ---
                    initial_history_for_api = [
                        {'role': 'user', 'parts': [constants.SYSTEM_INSTRUCTION]},
                        {'role': 'model', 'parts': [f"Anlaşıldı. Ben {constants.BOT_ADI}. Sadece '{constants.BOT_UZMANLIK_ALANI}' hakkında sorularınızı ve görsellerinizi yanıtlayacağım."]}
                    ] + api_history
                    # --- DEĞİŞİKLİK BİTTİ ---

                    try:
                        chat_session = self.model.start_chat(history=initial_history_for_api)
                        self.bot.active_chat_sessions[chat_key] = chat_session
                    except Exception as start_chat_error:
                        error_msg = f"Sohbet oturumu başlatma hatası: {start_chat_error}"
                        print(f"KRİTİK HATA [GeminiCog]: Sohbet oturumu başlatılamadı (muhtemelen geçmiş çok uzun veya API hatası): {start_chat_error}")
                        helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                        await channel.send(f"{user.mention}, üzgünüm, sohbet geçmişin çok uzun olduğu için veya bir API sorunu nedeniyle yeni oturum başlatılamıyor. Lütfen `{config.COMMAND_PREFIX}temizle` komutunu kullan veya daha sonra tekrar dene.", delete_after=10)
                        if chat_key in self.bot.active_chats_data:
                            try: del self.bot.active_chats_data[chat_key]; persistence.save_chat_data(self.bot.active_chats_data)
                            except KeyError: pass
                        if chat_key in self.bot.active_chat_sessions:
                            try: del self.bot.active_chat_sessions[chat_key]
                            except KeyError: pass
                        return

                self.bot.active_chats_data[chat_key]['last_interaction'] = datetime.now(timezone.utc)
                self.bot.active_chats_data[chat_key]['warning_sent'] = None

                prompt_content_for_api = []
                if image_parts_for_gemini:
                    prompt_content_for_api.extend(image_parts_for_gemini)

                final_user_text_for_api = user_message_text
                if not user_message_text and image_parts_for_gemini:
                    final_user_text_for_api = "Bu görseli analiz et. Eğer bir müzik notası içeriyorsa, anahtarını, donanımını ve olası tonalitesini belirt. Eğer başka bir müzik teknolojisi görseliyse, ne olduğunu açıkla."

                if final_user_text_for_api:
                    prompt_content_for_api.append(final_user_text_for_api)

                api_response = None
                if prompt_content_for_api:
                    try:
                        api_response = await chat_session.send_message_async(
                            prompt_content_for_api,
                            safety_settings=self.safety_settings
                        )
                    except google.api_core.exceptions.InvalidArgument as invalid_arg_err:
                        error_str = str(invalid_arg_err).lower()
                        error_msg = f"API Geçersiz Argüman Hatası: {invalid_arg_err}"
                        if "token limit" in error_str or "request payload size" in error_str or "context length" in error_str or "user input is required" in error_str:
                            error_msg = f"API içerik/token limiti aşıldı: {invalid_arg_err}"
                            print(f"HATA [GeminiCog]: {error_msg}")
                            helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                            await channel.send(f"{user.mention}, üzgünüm, sohbet geçmişimiz çok uzadığı için isteğini işleyemiyorum. Geçmişi kaydetmek için `{config.COMMAND_PREFIX}kaydet` kullanıp, ardından `{config.COMMAND_PREFIX}temizle` ile **kendi** sohbet geçmişini temizleyebilirsin.", delete_after=10)
                            if chat_key in self.bot.active_chat_sessions: del self.bot.active_chat_sessions[chat_key]
                            if chat_key in self.bot.active_chats_data: del self.bot.active_chats_data[chat_key]; persistence.save_chat_data(self.bot.active_chats_data)
                            return
                        else:
                            print(f"HATA [GeminiCog]: API'ye geçersiz argüman gönderildi: {invalid_arg_err}")
                            helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                            await channel.send(f"{user.mention}, isteğini işlerken bir API hatası oluştu (Geçersiz Argüman).", delete_after=7)
                            return
                    except Exception as general_api_err:
                        error_msg = f"Gemini API Çağrı Hatası: {general_api_err}"
                        print(f"HATA [GeminiCog]: Gemini API çağrısı sırasında genel hata: {general_api_err}")
                        helpers.log_interaction(user.id, user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
                        await channel.send(f"{user.mention}, üzgünüm, isteğini işlerken bir API hatası oluştu. Lütfen daha sonra tekrar dene.", delete_after=7)
                        return
                else:
                    print("HATA [GeminiCog]: API'ye gönderilecek içerik oluşturulamadı.")
                    return

                if not api_response:
                    print("HATA [GeminiCog]: API'den geçerli bir yanıt alınamadı (api_response is None).")
                    await channel.send(f"{user.mention}, üzgünüm, API'den bir yanıt alamadım. Lütfen tekrar deneyin.", delete_after=7)
                    return

                prompt_blocked = api_response.prompt_feedback and api_response.prompt_feedback.block_reason != HarmBlockThreshold.BLOCK_NONE
                response_blocked_by_safety = not api_response.candidates or any(cand.finish_reason == HarmCategory.HARM_CATEGORY_UNSPECIFIED for cand in api_response.candidates if cand.finish_reason)

                if prompt_blocked or response_blocked_by_safety:
                    reason_msg = f"Sebep: {api_response.prompt_feedback.block_reason.name if prompt_blocked else 'Yanıt güvenlik nedeniyle engellendi.'}"
                    log_msg = f"Güvenlik filtresi tetiklendi ({'Prompt/Görsel' if prompt_blocked else 'Yanıt'}): {reason_msg}"
                    print(f"UYARI [GeminiCog]: Güvenlik filtresi tetiklendi. {reason_msg}")
                    helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
                    try:
                        await message.delete()
                        await channel.send(f"{user.mention}, gönderdiğiniz içerik (metin veya görsel) güvenlik filtrelerimize takıldığı için işlenemedi.", delete_after=7)
                    except Exception as e_del_sec: print(f"HATA [GeminiCog]: Güvenlik sonrası mesaj silme/uyarı hatası: {e_del_sec}")
                    return

                bot_response_text = ""
                try:
                    bot_response_text = api_response.text.strip()
                except ValueError:
                    log_msg = "API yanıtı boş veya alınamadı (muhtemelen güvenlik)."
                    print("UYARI [GeminiCog]: API yanıtı .text ile alınamadı, muhtemelen güvenlik nedeniyle boş yanıt.")
                    helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
                    await channel.send(f"{user.mention}, gönderdiğiniz içerik güvenlik filtrelerimiz nedeniyle işlenemedi veya API bir yanıt üretemedi.", delete_after=7)
                    try: await message.delete()
                    except: pass
                    return

                if not bot_response_text:
                    print("UYARI [GeminiCog]: API'den boş yanıt metni alındı.")
                    await channel.send(f"{user.mention}, API'den anlamlı bir yanıt alınamadı. Lütfen tekrar deneyin veya içeriğinizi kontrol edin.", delete_after=7)
                    return

                off_topic_keywords = ["uzmanlık alanım sadece", "bu konuda yardımcı olamam", "konu dışı", "bilgi veremem", "yorum yapamam"]
                is_off_topic_reply = any(keyword in bot_response_text.lower() for keyword in off_topic_keywords) and len(bot_response_text.split()) < 15

                if is_off_topic_reply:
                    log_msg = f"Konu dışı yanıt verildi. Kullanıcı: '{final_user_text_for_api}' Bot: '{bot_response_text}'"
                    print(f"GeminiCog: Konu dışı yanıt tespit edildi: Kullanıcı={user.name}")
                    helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)

                    if user.id not in self.bot.user_violations:
                        self.bot.user_violations[user.id] = {'profanity_count': 0, 'off_topic_count': 0, 'last_warning_type': None}
                    self.bot.user_violations[user.id]['off_topic_count'] += 1
                    off_topic_count = self.bot.user_violations[user.id]['off_topic_count']
                    print(f"Kullanıcı {user.name} konu dışı ihlali: {off_topic_count}/{constants.OFF_TOPIC_TIMEOUT_THRESHOLD}")

                    remaining_violations = constants.OFF_TOPIC_TIMEOUT_THRESHOLD - off_topic_count
                    warning_text_add = ""
                    if off_topic_count >= constants.OFF_TOPIC_TIMEOUT_THRESHOLD:
                        await helpers.apply_timeout(self.bot, user, constants.DEFAULT_TIMEOUT_DURATION_MINUTES, "tekrarlanan konu dışı mesajlar", channel)
                        self.bot.user_violations[user.id]['off_topic_count'] = 0
                        self.bot.user_violations[user.id]['last_warning_type'] = None
                    else:
                        warning_text_add = f" (**Kalan hak: {remaining_violations}**. Limit aşılırsa timeout alacaksınız!)"
                        if off_topic_count >= constants.OFF_TOPIC_WARN_THRESHOLD and \
                           self.bot.user_violations[user.id].get('last_warning_type') != 'off_topic_final':
                            warning_text_add += f" **DİKKAT: {remaining_violations} ihlal hakkınız kaldı!**"
                            self.bot.user_violations[user.id]['last_warning_type'] = 'off_topic_final'
                        elif off_topic_count < constants.OFF_TOPIC_WARN_THRESHOLD:
                            self.bot.user_violations[user.id]['last_warning_type'] = None
                        await channel.send(f"{user.mention}, lütfen kanalın konusu olan '{constants.BOT_UZMANLIK_ALANI}' hakkında konuşmaya özen gösterin."+warning_text_add, delete_after=10)

                sent_reply_messages = await helpers.send_long_message(self.bot, message, bot_response_text)
                helpers.log_interaction(user.id, user.name, "Bot", bot_response_text, log_to_console=True)

                if chat_key in self.bot.active_chats_data:
                    user_content_for_history = final_user_text_for_api
                    if image_filename_for_log:
                        user_content_for_history = f"[{image_filename_for_log} görseli ile] {final_user_text_for_api if final_user_text_for_api else '(görsel analizi istendi)'}"
                    user_timestamp = message.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                    user_author_name = user.display_name
                    self.bot.active_chats_data[chat_key]['history'].append({
                        'timestamp': user_timestamp,
                        'author': user_author_name,
                        'content': user_content_for_history
                    })
                    bot_timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
                    bot_author_name = self.bot.user.display_name
                    self.bot.active_chats_data[chat_key]['history'].append({
                        'timestamp': bot_timestamp,
                        'author': bot_author_name,
                        'content': bot_response_text
                    })
                    persistence.save_chat_data(self.bot.active_chats_data)
                    # print(f"GeminiCog: Sohbet verisi güncellendi ve kaydedildi: {chat_key}") # Kaldırıldı

        except Exception as e_general_gemini:
            error_msg = f"GeminiCog genel işleme hatası: {e_general_gemini}"
            print(f"KRİTİK HATA [GeminiCog]: Mesaj işlenirken genel hata: {e_general_gemini}")
            import traceback
            traceback_str = traceback.format_exc()
            print(traceback_str)
            helpers.log_interaction(user.id, user.name, "Sistem", f"{error_msg}\n{traceback_str}", log_to_console=True, console_level=logging.ERROR)
            try:
                await channel.send(f"{user.mention}, üzgünüm, isteğini işlerken beklenmedik bir sorun oluştu. Lütfen tekrar dene veya durumu yetkililere bildir.", delete_after=7)
            except Exception as e_send_fail: print(f"HATA [GeminiCog]: Genel hata sonrası kullanıcıya mesaj gönderilemedi: {e_send_fail}")


async def setup(bot: commands.Bot):
    if not PIL_AVAILABLE:
        print("UYARI: Pillow kütüphanesi eksik olduğu için GeminiCog tam işlevsel olmayabilir (görsel işleme).")

    cog_instance = GeminiCog(bot)
    if cog_instance.model is None:
        print("GeminiCog yüklenemedi: Gemini modeli başlatılamadı (API anahtarı veya yapılandırma sorunu).")
        return

    await bot.add_cog(cog_instance)
    # print("GeminiCog başarıyla yüklendi ve ayarlandı.") # Kaldırıldı

