# config.py
# Bu dosya, .env dosyasındaki ortam değişkenlerini yükler ve
# botun diğer bölümlerinin kullanımına sunar.

# ÖNEMLİ!!!! BURADA HERHANGİ BİR AYARLAMA/DEĞİŞİKLİK YAPILMASINA GEREK YOKTUR.
# Ayarlar .env ve constants.py dosyalarında yapılmalıdır.

import os
from dotenv import load_dotenv

# Proje kök dizinindeki .env dosyasını yükle
# Eğer resonai.py ana dizindeyse ve config.py de oradaysa bu genellikle çalışır.
# Farklı bir klasör yapınız varsa, dotenv_path'ı uygun şekilde ayarlamanız gerekebilir.
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Eğer config.py bir alt klasördeyse
if not os.path.exists(dotenv_path):
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env') # Eğer config.py ana dizindeyse

load_dotenv(dotenv_path=dotenv_path)

print(f".env dosyası şu yoldan yüklendi (veya deneniyor): {os.path.abspath(dotenv_path)}") # Yükleme yolunu logla

# --- Temel API Anahtarları ---
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Bot Ayarları ---
# Bot Sahibi ID'si
BOT_OWNER_ID_STR = os.getenv('BOT_OWNER_ID')
BOT_OWNER_ID = None
if BOT_OWNER_ID_STR and BOT_OWNER_ID_STR.strip():
    try:
        BOT_OWNER_ID = int(BOT_OWNER_ID_STR)
    except ValueError:
        print(f"UYARI [config.py]: .env dosyasındaki BOT_OWNER_ID ('{BOT_OWNER_ID_STR}') geçerli bir sayı değil. Sahip komutları çalışmayabilir.")
else:
    print("BİLGİ [config.py]: .env dosyasında BOT_OWNER_ID tanımlanmamış veya boş. Sahip komutları devre dışı.")

# Yönetici Rol ID'leri
admin_role_ids_str = os.getenv('ADMIN_ROLE_IDS')
ADMIN_ROLE_IDS = []
if admin_role_ids_str and admin_role_ids_str.strip():
    try:
        # Virgülle ayrılmış ID'leri al, boşlukları temizle ve integer'a çevir
        ADMIN_ROLE_IDS = [int(role_id.strip()) for role_id in admin_role_ids_str.split(',') if role_id.strip()]
    except ValueError:
        print(f"UYARI [config.py]: .env dosyasındaki ADMIN_ROLE_IDS ('{admin_role_ids_str}') listesindeki bazı ID'ler geçerli sayı değil. Bu ID'ler yoksayılacak.")
        # Hatalı olmayanları ayıklamaya çalışabiliriz ama şimdilik basit tutalım
        ADMIN_ROLE_IDS = [] # Hata durumunda boş liste ata
if not ADMIN_ROLE_IDS:
    print("BİLGİ [config.py]: .env dosyasında ADMIN_ROLE_IDS tanımlanmamış veya geçerli ID bulunamadı. Yönetici komutları sadece sunucu admin yetkisine sahip olanlar tarafından kullanılabilir.")

# Dinlenecek Kanal ID'leri
allowed_channel_ids_str = os.getenv('ALLOWED_CHANNEL_IDS')
ALLOWED_CHANNEL_IDS = [] # Artık None yerine boş liste kullanacağız, kontrolü kolaylaştırır
if allowed_channel_ids_str and allowed_channel_ids_str.strip():
    try:
        ALLOWED_CHANNEL_IDS = [int(channel_id.strip()) for channel_id in allowed_channel_ids_str.split(',') if channel_id.strip()]
    except ValueError:
        print(f"UYARI [config.py]: .env dosyasındaki ALLOWED_CHANNEL_IDS ('{allowed_channel_ids_str}') listesindeki bazı ID'ler geçerli sayı değil. Bu ID'ler yoksayılacak.")
        ALLOWED_CHANNEL_IDS = [] # Hata durumunda boş liste ata
if not ALLOWED_CHANNEL_IDS:
    print("BİLGİ [config.py]: .env dosyasında ALLOWED_CHANNEL_IDS tanımlanmamış veya geçerli ID bulunamadı. Bot, izinleri olan tüm kanalları dinleyebilir (komut bazlı ek kontroller olabilir).")


# --- Prefix Ayarları ---
# .env'de yoksa varsayılan değerler kullanılır.
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX', '!')
IGNORE_PREFIX = os.getenv('IGNORE_PREFIX', '.r')

# --- Gerekli Anahtarların Kontrolü ---
if DISCORD_TOKEN is None:
    print("KRİTİK HATA [config.py]: DISCORD_TOKEN .env dosyasında bulunamadı veya boş! Bot başlatılamaz.")
    # Burada exit() çağrılabilir veya resonai.py'de bu kontrol yapılabilir.
    # Şimdilik sadece uyarı veriyoruz, resonai.py'de daha kapsamlı kontrol olacak.
if GEMINI_API_KEY is None:
    print("KRİTİK HATA [config.py]: GEMINI_API_KEY .env dosyasında bulunamadı veya boş! Bot başlatılamaz.")

# Ayarların yüklendiğini teyit etmek için bazı değerleri yazdırabiliriz (opsiyonel, debug için)
print(f"config.py yüklendi: COMMAND_PREFIX='{COMMAND_PREFIX}', BOT_OWNER_ID={BOT_OWNER_ID}, ADMIN_ROLE_IDS={ADMIN_ROLE_IDS}, ALLOWED_CHANNEL_IDS={ALLOWED_CHANNEL_IDS}")

