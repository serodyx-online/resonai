# ResonAI - Discord Sohbet Botu (Gemini API Entegrasyonlu)

## 🤖 Bot Hakkında

ResonAI, Discord sunucularında belirli bir uzmanlık alanında (varsayılan olarak **Müzik Teknolojileri**) yapay zeka destekli sohbet ve bilgi sağlama amacıyla geliştirilmiş modüler bir Python botudur. Google'ın Gemini API'sini kullanarak metin tabanlı soruları yanıtlar ve görselleri analiz edebilir. Open-source olarak sunduğum bu botu kendi ihtiyaçlarınıza göre kolayca yapılandırabilir ve farklı uzmanlık alanlarına uyarlayabilirsiniz.

**Temel Özellikler:**

* **Modüler Tasarım:** Kolaylıkla düzenlenebilir geliştirilebilir modüler yapı.
* **Gemini API Entegrasyonu:** Yapay zeka entegrasyonu sayesinde sorularınızı doğrusal şekilde cevaplar.
* **Görsel Analizi:** Desteklenen formatlardaki görselleri analiz edebilir (varsayılan olarak örn; ekipman fotoğrafları, nota kağıtları).
* **Sohbet Geçmişi Yönetimi:** Her kullanıcı için (her kanalda ayrı ayrı) sohbet geçmişi tutar ve bu geçmişi API isteklerinde kullanır.
* **Kalıcı Hafıza:** Her kullanıcı için ayrı tutulan bu geçmiş, bot yeniden başlatılsa bile korunur (komutlarla manuel veya inaktiflikten otomatik silinme durumları hariç).
* **Moderasyon Araçları:** Küfür filtresi, kısa/tekrar mesaj engelleme, GIF/Sticker engelleme gibi temel moderasyon özellikleri içerir.
* **Kullanıcı ve Yönetici Komutları:** Sohbeti yönetmek, botla etkileşim kurmak için bazı komutlar sunar.
* **Yapılandırılabilirlik:** Botun adı, uzmanlık alanı, komut ön eki ve diğer temel ayarları kolayca değiştirilebilir.
* **Detaylı Loglama:**
    * Ana konsol logları, sistem olayları, uyarı ve hatalar. (Gereksiz loglar #yorum olarak ayarlanarak önemli ölçüde azaltıldı)
    * Her kullanıcı için ayrı kanal etkileşim logları (`user_logs/`).
    * Her kullanıcı için ayrı DM etkileşim logları (`dm_logs/`).
* **Başlangıç İşlemleri:** Bot başlatılırken belirlenen kanallarda otomatik olarak açıklama embed mesajı gönderir/sabitler ve "Bot Aktif" mesajı yayınlar.
* **DM Yönetimi:** Kullanıcıların kendi DM'lerine gönderilen bot mesajlarını ve bot sahibinin tüm DM'lere giden bot mesajlarını temizleyebilmesi için komutlar içerir.

## 🚀 Kurulum

Botu kendi sunucunuzda çalıştırmak için aşağıdaki adımları izleyin:

### 1. Ön Gereksinimler

* **Python 3.8 veya üzeri:** [Python İndirme Sayfası](https://www.python.org/downloads/)
* **pip:** Python paket yükleyicisi (genellikle Python ile birlikte gelir).
* **Discord Bot Token:** [Discord Developer Portal](https://discord.com/developers/applications) üzerinden yeni bir uygulama oluşturup bot token'ınızı alın. Botunuza aşağıdaki "Privileged Gateway Intents" yetkilerini vermeyi unutmayın:
    * `MESSAGE CONTENT INTENT`
    * `SERVER MEMBERS INTENT` yetkileri
* **Gemini API Anahtarı:** [Google AI Studio veya Google Cloud](https://aistudio.google.com/app/apikey) üzerinden bir API anahtarı oluşturun.

### 2. Projeyi İndirme ve Kurulum

1.  **Projeyi Klonlayın veya İndirin:**
    ```bash
    git clone https://github.com/serodyx-online/resonai/
    cd resonai
    ```
    Veya projeyi ZIP olarak indirip bir klasöre çıkarın.

2.  **Gerekli Python Kütüphanelerini Yükleyin:**
    Proje ana dizininde bir terminal veya komut istemcisi açarak aşağıdaki komutu çalıştırın:
    ```bash
    pip install -r requirements.txt
    ```
    Veya aşağıdaki komutla kütüphaneleri manuel olarak kurabilirsiniz:
    ```bash
    pip install discord.py python-dotenv google-generativeai Pillow aiohttp better-profanity fpdf2
    ```

### 3. Yapılandırma Dosyalarını Ayarlama

1.  **`.env` Dosyasını Düzenleyin:**
    Proje ana dizininde bulunan `.env.example` dosyasını kendi bilgilerinize göre düzenleyerek, ismini `.env` olarak değiştirin.
    Örnek .env içeriği aşağıdaki gibi olmalıdır;

    ```env
    # Discord Bot Token'ınız
    DISCORD_TOKEN=SENİN_DISCORD_BOT_TOKENİN_BURAYA

    # Gemini API Anahtarınız
    GEMINI_API_KEY=SENİN_GEMINI_API_ANAHTARIN_BURAYA

    # Bot Sahibinin Discord Kullanıcı ID'si (Örn: 123456789012345678)
    BOT_OWNER_ID=SENİN_KULLANICI_IDN_BURAYA

    # Yönetici Rol ID'leri (Opsiyonel, virgülle ayırın, örn: ROL_ID_1,ROL_ID_2)
    ADMIN_ROLE_IDS=

    # Botun Sadece Dinleyeceği Kanal ID'leri (Opsiyonel, virgülle ayırın)
    # Boş bırakılırsa bot izinleri olan tüm kanalları dinler.
    ALLOWED_CHANNEL_IDS=

    # Bot Komut Ön Eki (Opsiyonel, varsayılanı: !)
    COMMAND_PREFIX=!

    # Botun Yoksayacağı Mesaj Ön Eki (Opsiyonel, varsayılanı: .r)
    IGNORE_PREFIX=.r
    ```

2.  **`constants.py` Dosyasını Düzenleyin (Bot Kimliği ve Amacı İçin):**
    `constants.py` dosyasını açın ve botunuzun kimliğini ve amacını yansıtacak şekilde aşağıdaki değişkenleri güncelleyin:

    ```python
    # --- BOT KİMLİK VE UZMANLIK AYARLARI (Open-source için kolayca değiştirilebilir) ---
    BOT_ADI = "YeniBotAdi"
    BOT_YAPIMCISI = "SizinAdınız" # Sistem talimatında sadece bir kez geçiyor
    BOT_UZMANLIK_ALANI = "Yeni Uzmanlık Alanı (Örn: Tarih, Bilim, Sanat)"
    # --- BOT KİMLİK VE UZMANLIK AYARLARI BİTTİ ---
    ```
    config.py Dosyasında değişiklik yapmanıza gerek yoktur. CONSTANTS.PY'deki Bu değişiklikler, botun sistem talimatlarına, yardım mesajlarına, embed mesajlarına ve Discord aktivite durumuna yansıyacaktır. Diğer sabitleri (moderasyon eşikleri, inaktiflik süreleri vb.) de bu dosyadan ihtiyacınıza göre düzenleyebilirsiniz.

3.  **`turkish_profanity.txt` Dosyasını isteğinize göre düzenleyin:**
    Proje ana dizininde `turkish_profanity.txt` adında bir liste mevcut. Küfür filtresinin yakalamasını istediğiniz kelimeleri her satıra bir kelime gelecek şekilde bu dosyaya ekleyin. Dosyanın UTF-8 formatında kaydedildiğinden emin olun.

4.  **Font Dosyalarını Kontrol Edin (`assets/`):**
    PDF oluşturma özelliği için `assets/` klasöründe `DejaVuSans.ttf` ve `DejaVuSans-Bold.ttf` font dosyalarının bulunduğundan emin olun. Gerekirse bu fontları temin edin.

### 4. Botu Çalıştırma

Tüm ayarları yaptıktan ve kütüphaneleri kurduktan sonra, terminal veya komut istemcisini projenizin ana dizininde açın ve aşağıdaki komutu çalıştırarak botu başlatın:

```bash
python resonai.py
```
Bot başarıyla bağlandığında ve Cog'ları yüklediğinde konsolda aşağıdaki çıktıyı görmeniz gerekiyor;

```
-----------------------------------------
ResonAI tamamen hazır ve komutları bekliyor.
-----------------------------------------
```
Eğer bot sahibi olarak DM'den bota (prefix)restart komutu gönderebilmek istiyorsanız botu ana dizindeki "start.bat" dosyasından çalıştırmanız gerekmektedir.
Ayrıca botun kapanış mesajının kanallara gitmesi için botun sahibi tarafından dm atılarak "sdown" komutuyla kapatılması gerekir.

## KOMUTLAR (PREFIX DEĞİŞTİRİLEBİLİR)

### ⚙️ Genel Kullanıcı Komutları (Botun dinlediği kanallarda);


`!yardim (veya !help, !yardım)`
Botun yapabilecekleri, kanal kuralları ve komutlar hakkında detaylı bir yardım mesajını kullanıcıya DM olarak gönderir.

`!kaydet`
Komutu kullanan kullanıcının bot ile o kanaldaki sohbet geçmişini PDF formatında oluşturur ve kullanıcıya DM ile gönderir.

`!temizle` Komutu kullanan kullanıcının botla olan sohbet geçmişini kanaldan ve botun **hafızasından** temizler.

#### Kullanıcı DM Komutları (Bota DM Göndererek)
`!dmtemizle` Botun o kullanıcıya daha önce gönderdiği tüm DM'ler silinmeye başlar. Kullanıcıya işlem sonucu hakkında DM ile bilgi verilir.

Not: Diğer DM mesajlarına (bu komut hariç) bot yanıt vermez, güvenlik amacıyla dm_logs altına kaydeder ve kullanıcıya sadece bu komutu kullanabileceğini belirten bir bilgi mesajı gönderir.

### ⚙️ Yönetici Komutları (Sunucu Kanalında - Yönetici Yetkisi Gerekir)
`!embedaciklama` Mevcut kanala botun ana açıklama embed'ini gönderir/günceller ve sabitler. Varsa eski embed mesaj silinir.

`!temizlechat` Komutun kullanıldığı kanaldaki tüm mesajları siler (sabitlenmiş mesajlar ve botun son durum mesajı hariç). Onay gerektirir.

`!sifirla <@kullanıcı/ID> <küfür/konu>` Belirtilen kullanıcının küfür veya konu dışı ihlal sayacını sıfırlar.

`!cl <@kullanıcı/ID>` Belirtilen kullanıcının botla olan sohbet geçmişini (hafıza) temizler ve kanaldaki o kullanıcıya ait/yanıt olan mesajları (son 14 gün, bazı özel mesajlar hariç) siler. Onay gerektirir.

`!cl herkes` Kanaldaki tüm kullanıcıların botla olan sohbet geçmişlerini (hafıza) temizler ve kanaldaki tüm mesajları (sabitlenmişler ve bot durum mesajı hariç) siler. Onay gerektirir.

### ⚙️ Bot Sahibi Komutları (Bu komutlar yalnızca bot sahibi tarafından Bota **DM** Göndererek kullanılır - çalışması için .env içerisinde BOT_OWNER_ID doldurulması gereklidir.)
`!sdown` Botu güvenli bir şekilde kapatır. Verileri kaydeder ve izin verilen kanallara kapanış mesajı gönderir.

`!restart` Botu yeniden başlatmak üzere kapatır (çıkış kodu 5 verir). Verileri kaydeder ve izin verilen kanallara yeniden başlatma mesajı gönderir. (Bu komutun botu gerçekten yeniden başlatması için, botun daima ana dizinde verilen baslat.bat dosyası ile çalıştırılması gerekmektedir.)

`!dmtemizle <kullanıcı_id>` Belirtilen kullanıcı ID'sine bot tarafından gönderilmiş tüm DM'leri siler. Hedef kullanıcıya ve bot sahibine işlem hakkında bilgi verir.

`!dmtemizle herkes` Botun o ana kadar özel mesaj tüm kullanıcılardan DM'leri siler. Etkilenen her kullanıcıya ve bot sahibine işlem hakkında bilgi verir.

---

## 📁 Klasör Yapısı
[Projenin detaylı klasör yapısını görmek için tıklayınız.](structure.md)

## 🤝 Katkıda Bulunma
Bu proje açık kaynaklıdır. Katkıda bulunmak isterseniz, lütfen bir "issue" açın veya "pull request" gönderin. Yapıcı geri bildirimler her zaman değerlidir.

## 📜 Lisans
Bu proje GNU GPLv3 Lisansı altında lisanslanmıştır.
