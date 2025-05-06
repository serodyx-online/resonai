# resonai.py
# Ana bot dosyası. Botu başlatır, Cog'ları yükler ve temel ayarları yapar.

import discord
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime, timezone # active_chats_data için
import logging

# Yerel modüllerimizi import edelim
import config # config.py dosyasını import et
import constants # constants.py dosyasını import et
from utils import persistence # utils klasöründeki persistence.py'yi import et
from utils import helpers   # utils klasöründeki helpers.py'yi import et

# --- Bot için Gerekli Intent'ler ---
intents = discord.Intents.default()
intents.messages = True         # Mesajları almak için (on_message)
intents.message_content = True  # Mesaj içeriğine erişmek için (komutlar, Gemini işleme)
intents.members = True          # Üye bilgilerini (roller vb.) almak için (is_admin, timeout)
intents.guilds = True           # Sunucu bilgilerini almak için (kanal listesi vb.)

# --- Bot Oluştur ---
bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents, help_command=None)

# --- Paylaşılan Durum Değişkenlerini Bot'a Ekle ---
bot.active_chats_data = {}
bot.user_violations = {}
bot.pinned_embed_message_id = {}
bot.split_message_map = {}
bot.latest_status_messages = {}
bot.user_last_message = {}
bot.active_chat_sessions = {}


# --- Bot Hazır Olduğunda Çalışacak Olay ---
@bot.event
async def on_ready():
    print(f'{bot.user.name} olarak Discord\'a bağlandım.')
    print(f'Bot ID: {bot.user.id}')
    print(f"Discord.py Versiyon: {discord.__version__}")
    print('-----------------------------------------')

    # Kaydedilmiş veriyi yükle
    bot.active_chats_data = persistence.load_chat_data()
    bot.latest_status_messages = persistence.load_status_messages()
    print('-----------------------------------------')

    print("Cog'lar yükleniyor...")
    await load_all_extensions() # Cog'ları yükle
    print('-----------------------------------------')

    # --- CoreListenersCog'u Manuel Başlatma ---
    core_listeners_cog = bot.get_cog('CoreListenersCog')
    if core_listeners_cog:
        try:
            await core_listeners_cog.initialize_cog()
        except Exception as e_init_cog:
            print(f"HATA [resonai.py]: CoreListenersCog.initialize_cog() çağrılırken hata oluştu: {e_init_cog}")
            import traceback
            traceback.print_exc()
    else:
        print("HATA [resonai.py]: CoreListenersCog bulunamadı! Başlangıç işlemleri yapılamayacak.")
    # --- CoreListenersCog Başlatma Bitti ---

    # Botun aktivitesini ayarla
    try:
        activity_name = f"{config.COMMAND_PREFIX}yardim | {constants.BOT_UZMANLIK_ALANI}"
        activity = discord.Activity(name=activity_name, type=discord.ActivityType.listening)
        await bot.change_presence(status=discord.Status.online, activity=activity)
        print(f"Bot aktivitesi ayarlandı: {activity.type.name.capitalize()} {activity.name}")
    except Exception as e:
        print(f"HATA [resonai.py]: Bot aktivitesi ayarlanamadı: {e}")

    # Font dosyalarının varlığını kontrol et (PDF için)
    if not helpers.FPDF_FONT_AVAILABLE:
        print(f"UYARI [resonai.py]: DejaVu font dosyaları ({constants.DEJAVU_FONT_PATH}, {constants.DEJAVU_FONT_PATH_BOLD}) bulunamadı. PDF kaydetme özelliği Türkçe karakterlerde sorun yaşayabilir.")
    else:
        print("Bilgi [resonai.py]: PDF oluşturma için gereken fontlar mevcut.")

    print('-----------------------------------------')
    print(f"{bot.user.name} tamamen hazır ve komutları/mesajları bekliyor.")
    print('-----------------------------------------')


# --- Cog (Eklenti/Modül) Yükleme Fonksiyonu ---
async def load_all_extensions():
    """cogs klasöründeki tüm Python dosyalarını (Cog'ları) yükler."""
    loaded_cogs = []
    failed_cogs = []
    cog_count = 0
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            cog_count += 1
            extension_name = f'cogs.{filename[:-3]}'
            try:
                await bot.load_extension(extension_name)
                loaded_cogs.append(extension_name)
            except commands.ExtensionAlreadyLoaded:
                loaded_cogs.append(extension_name)
            except commands.ExtensionNotFound:
                print(f'  ERROR: {extension_name} bulunamadı.')
                failed_cogs.append(f"{extension_name} (Bulunamadı)")
            except commands.NoEntryPointError:
                print(f'  ERROR: {extension_name} içinde `setup` fonksiyonu bulunamadı.')
                failed_cogs.append(f"{extension_name} (setup eksik)")
            except Exception as e:
                print(f'  ERROR: {extension_name} yüklenirken hata oluştu.')
                print(f'    {type(e).__name__}: {e}')
                failed_cogs.append(f"{extension_name} ({type(e).__name__})")

    if cog_count == 0:
        print("UYARI [resonai.py]: 'cogs' klasöründe yüklenecek Cog bulunamadı.")
    else:
        print(f"Toplam {len(loaded_cogs)}/{cog_count} Cog başarıyla yüklendi.")
        if failed_cogs:
            print("Başarısız olan Cog'lar:")
            for failed_cog in failed_cogs:
                print(f"  - {failed_cog}")


# --- Ana Çalıştırma Bloğu ---
async def main():
    if not config.DISCORD_TOKEN:
        print("KRİTİK HATA [resonai.py]: DISCORD_TOKEN .env dosyasında veya config.py'de bulunamadı! Bot başlatılamaz.")
        return
    if not config.GEMINI_API_KEY:
        print("KRİTİK HATA [resonai.py]: GEMINI_API_KEY .env dosyasında veya config.py'de bulunamadı! Bot başlatılamaz.")
        return

    async with bot:
        try:
            await bot.start(config.DISCORD_TOKEN)
        except discord.LoginFailure:
            print("KRİTİK HATA [resonai.py]: Geçersiz Discord Token. .env dosyasındaki DISCORD_TOKEN değerini kontrol edin.")
        except discord.PrivilegedIntentsRequired:
            print("KRİTİK HATA [resonai.py]: Gerekli Intent'ler (Members ve/veya Message Content) Discord Developer Portal'da etkinleştirilmemiş.")
            print("Lütfen botunuzun ayarlarından 'Privileged Gateway Intents' bölümünü kontrol edin.")
        except Exception as e:
            print(f"KRİTİK HATA [resonai.py]: Bot çalıştırılırken beklenmedik bir hata oluştu: {e}")
            print("Beklenmedik kapanış, veriler kaydediliyor...")
            persistence.save_chat_data(bot.active_chats_data)
            persistence.save_status_messages(bot.latest_status_messages)
            print("Veriler kaydedildi.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('fontTools').setLevel(logging.WARNING)

    # --- DEĞİŞİKLİK: DM_LOGS_DIRECTORY eklendi ---
    # `data`, `assets`, `user_logs` ve `dm_logs` klasörlerinin varlığını kontrol et
    for dir_name in [constants.LOGS_DIRECTORY, constants.DM_LOGS_DIRECTORY, "data", constants.ASSETS_DIRECTORY]:
    # --- DEĞİŞİKLİK BİTTİ ---
        if not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
                print(f"Bilgi [resonai.py]: '{dir_name}' klasörü oluşturuldu.")
            except OSError as e:
                print(f"HATA [resonai.py]: '{dir_name}' klasörü oluşturulamadı: {e}")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot manuel olarak (Ctrl+C) kapatılıyor...")
    except SystemExit as e:
        if e.code == 5:
            print("Bot yeniden başlatılmak üzere kapatıldı (Exit Code 5). Başlatıcı betik devralmalı.")
        else:
            print(f"Bot beklenmedik bir SystemExit ile kapatıldı (Exit Code: {e.code}).")
    finally:
        print("Ana program sonlandırılıyor.")

