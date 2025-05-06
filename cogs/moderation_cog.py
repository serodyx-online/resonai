# cogs/moderation_cog.py
# Bu Cog, mesaj moderasyon mantığını (küfür, kısa/tekrar mesaj, GIF/sticker filtreleri) içerir.

import discord
from discord.ext import commands
import os # turkish_profanity.txt için
import logging # logging seviyeleri için

# better_profanity import'u
try:
    from better_profanity import Profanity
    better_profanity_available = True
except ImportError:
    better_profanity_available = False
    print("UYARI [ModerationCog]: 'better-profanity' kütüphanesi bulunamadı. Küfür filtresi çalışmayacak.")


# Yerel modüller
import config
import constants
from utils import helpers # helpers.py'deki fonksiyonları kullanmak için

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profanity_filter = None
        if better_profanity_available:
            self.profanity_filter = Profanity()
            self.load_custom_profanity_list()
        else:
            print("ModerationCog: better-profanity yüklü olmadığı için küfür filtresi devre dışı.")

    def load_custom_profanity_list(self):
        """Türkçe küfür listesini dosyadan yükler."""
        if not self.profanity_filter:
            return
        try:
            if os.path.exists(constants.TURKISH_PROFANITY_LIST_PATH):
                with open(constants.TURKISH_PROFANITY_LIST_PATH, 'r', encoding='utf-8') as f:
                    custom_words = [line.strip() for line in f if line.strip()]
                if custom_words:
                    self.profanity_filter.add_censor_words(custom_words)
                    print(f"Türkçe küfür listesi yüklendi ({len(custom_words)} kelime).") # Bu log kalabilir, önemli bilgi
                else:
                    print(f"UYARI Türkçe küfür listesi ({constants.TURKISH_PROFANITY_LIST_PATH}) boş.")
            else:
                print(f"UYARI Türkçe küfür listesi ({constants.TURKISH_PROFANITY_LIST_PATH}) bulunamadı. Sadece varsayılan İngilizce filtre aktif olacak.")
        except Exception as e:
            print(f"HATA: Türkçe küfür listesi yüklenemedi: {e}")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # --- 1. BAŞLANGIÇ KONTROLLERİ (Moderasyon Cog için) ---
        if message.author == self.bot.user: # Botun kendi mesajlarını yoksay
            return
        if message.guild is None: # DM mesajlarını bu Cog'da işleme (OwnerDMCog ilgilenecek)
            return
        if message.content.startswith(config.COMMAND_PREFIX): # Komutları bu Cog'da işleme
            return
        if message.content.startswith(config.IGNORE_PREFIX): # Yoksayma prefix'li mesajları işleme
            return

        # Sadece izin verilen kanallardaki mesajları işle (config'den)
        if config.ALLOWED_CHANNEL_IDS and message.channel.id not in config.ALLOWED_CHANNEL_IDS:
            return

        # --- Moderasyon İşlemleri ---
        user = message.author
        channel = message.channel
        content = message.content.strip() # Başındaki/sonundaki boşlukları temizle

        # --- @everyone/@here Kontrolü ---
        if message.mention_everyone:
            log_msg = "@everyone/@here mention içeren mesaj yoksayıldı."
            helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
            try: await message.delete()
            except: pass
            # await channel.send(f"{user.mention}, lütfen herkesi etiketlemeyin.", delete_after=5) # İsteğe bağlı uyarı
            return

        # --- GIF ve Sticker Engelleme ---
        is_gif_or_sticker = False
        reason = ""
        if message.stickers:
            is_gif_or_sticker = True; reason = "Sticker"
        elif message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith('.gif'):
                    is_gif_or_sticker = True; reason = "GIF"; break
        if not is_gif_or_sticker and ('tenor.com/view/' in content or 'giphy.com/media/' in content):
            is_gif_or_sticker = True; reason = "GIF Linki"

        if is_gif_or_sticker:
            log_msg = f"{reason} gönderimi engellendi ve mesaj silindi: {content[:50]}"
            helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
            try:
                await message.delete()
                await channel.send(f"{user.mention}, bu kanalda {reason} göndermek yasaktır.", delete_after=7)
            except Exception as e: print(f"HATA [ModerationCog]: {reason} silme/uyarı hatası: {e}")
            return

        # --- Kısa Mesaj Engelleme (Ekleri de kontrol et) ---
        if len(content) < constants.DEFAULT_MIN_MESSAGE_LENGTH and not message.attachments:
            log_msg = f"Kısa mesaj engellendi ve silindi: '{content}'"
            helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
            try:
                await message.delete()
                await channel.send(f"{user.mention}, lütfen daha anlamlı mesajlar yazın (en az {constants.DEFAULT_MIN_MESSAGE_LENGTH} karakter).", delete_after=7)
            except Exception as e: print(f"HATA [ModerationCog]: Kısa mesaj silme/uyarı hatası: {e}")
            return

        # --- Tekrar Mesaj Engelleme ---
        # self.bot.user_last_message paylaşılan sözlüğünü kullan
        last_msg_content = self.bot.user_last_message.get(user.id)
        if content and content == last_msg_content: # Sadece metin içeriği varsa ve aynıysa
            log_msg = f"Tekrar eden mesaj engellendi ve silindi: '{content}'"
            helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)
            try:
                await message.delete()
                await channel.send(f"{user.mention}, lütfen aynı mesajı tekrar göndermeyin.", delete_after=7)
            except Exception as e: print(f"HATA [ModerationCog]: Tekrar mesaj silme/uyarı hatası: {e}")
            return
        if content: # Sadece metin içeriği varsa son mesajı güncelle
            self.bot.user_last_message[user.id] = content


        # --- Küfür Filtresi (better-profanity) ---
        if self.profanity_filter and content: # Filtre varsa ve metin içeriği varsa
            try:
                if self.profanity_filter.contains_profanity(content):
                    censored_text = self.profanity_filter.censor(content, '*')
                    log_msg = f"Uygunsuz kelime tespit edildi, mesaj siliniyor. Orijinal: '{content}' Sansürlü: '{censored_text}'"
                    helpers.log_interaction(user.id, user.name, "Sistem", log_msg, log_to_console=True, console_level=logging.WARNING)

                    # self.bot.user_violations paylaşılan sözlüğünü kullan
                    if user.id not in self.bot.user_violations:
                        self.bot.user_violations[user.id] = {'profanity_count': 0, 'off_topic_count': 0, 'last_warning_type': None}
                    self.bot.user_violations[user.id]['profanity_count'] += 1
                    profanity_count = self.bot.user_violations[user.id]['profanity_count']
                    print(f"Kullanıcı {user.name} küfür ihlali: {profanity_count}/{constants.PROFANITY_TIMEOUT_THRESHOLD}")

                    try:
                        await message.delete()
                        warning_msg_text = f"{user.mention}, mesajınız uygunsuz kelime içerdiği için silindi."
                        remaining_violations = constants.PROFANITY_TIMEOUT_THRESHOLD - profanity_count

                        if profanity_count >= constants.PROFANITY_TIMEOUT_THRESHOLD:
                            await helpers.apply_timeout(self.bot, user, constants.DEFAULT_TIMEOUT_DURATION_MINUTES, "tekrarlanan küfürlü dil", channel)
                            self.bot.user_violations[user.id]['profanity_count'] = 0
                            self.bot.user_violations[user.id]['last_warning_type'] = None
                        else:
                            warning_msg_text += f" (**Kalan hak: {remaining_violations}**. Limit aşılırsa geçici süreliğine timeout cezası alacaksınız.)"
                            if profanity_count >= constants.PROFANITY_WARN_THRESHOLD and \
                               self.bot.user_violations[user.id].get('last_warning_type') != 'profanity_final':
                                warning_msg_text += f" **DİKKAT: {remaining_violations} ihlal hakkınız kaldı, sonra {constants.DEFAULT_TIMEOUT_DURATION_MINUTES}dk susturulacaksınız!**"
                                self.bot.user_violations[user.id]['last_warning_type'] = 'profanity_final'
                            elif profanity_count < constants.PROFANITY_WARN_THRESHOLD:
                                self.bot.user_violations[user.id]['last_warning_type'] = None
                        await channel.send(warning_msg_text, delete_after=10)
                    except Exception as e:
                        print(f"HATA [ModerationCog]: Küfürlü mesaj silme/uyarı/timeout hatası: {e}")
                    return # Küfürlü mesaj işlendikten sonra GeminiCog'a gitmemeli
            except Exception as filter_error:
                print(f"HATA [ModerationCog]: Küfür filtresi çalıştırılırken hata: {filter_error}")
        # --- Küfür Filtresi Bitti ---

        # Eğer mesaj tüm moderasyon kontrollerinden geçtiyse, GeminiCog tarafından işlenmek üzere
        # bu listener'dan return edilmeden çıkılır. GeminiCog da kendi on_message'ında
        # bu mesajı yakalayacak ve işleyecek.

async def setup(bot: commands.Bot):
    # better-profanity kütüphanesi yoksa Cog'u yükleme
    if not better_profanity_available:
        print("ModerationCog yüklenemedi: 'better-profanity' kütüphanesi eksik.")
        return

    await bot.add_cog(ModerationCog(bot))
    # print("ModerationCog başarıyla yüklendi ve ayarlandı.") # Kaldırıldı

