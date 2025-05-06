
📁 Klasör Yapısı
Projenin ana klasör yapısı aşağıdaki gibidir:

/resonai/
|-- resonai.py                     # Ana bot dosyası
|-- start.bat                     # Kolay başlatma dosyası (Restart komutu için gereklidir)
|-- config.py                  # .env'den ayarları okur
|-- constants.py               # Sabit değerler ve bot kimliği
|
|-- cogs/                        # Cog (modül) klasörü
|   |-- __init__.py
|   |-- admin_commands_cog.py    # Yönetici komutları
|   |-- core_listeners_cog.py  # Temel olaylar ve görevler
|   |-- dm_handler_cog.py      # DM mesajlarını işleme ve loglama
|   |-- gemini_cog.py          # Gemini API etkileşimi
|   |-- moderation_cog.py      # Mesaj moderasyonu
|   |-- owner_dm_cog.py        # Sahip DM komutları
|   |-- user_commands_cog.py   # Kullanıcı komutları
|
|-- utils/                       # Yardımcı fonksiyonlar
|   |-- __init__.py
|   |-- helpers.py             # Genel yardımcılar
|   |-- persistence.py         # Veri kaydetme/yükleme
|
|-- data/                        # Kalıcı veriler (otomatik oluşur)
|   |-- chat_data.pkl
|   |-- status_messages.pkl
|
|-- user_logs/                   # Kullanıcıların kanal etkileşim logları (otomatik oluşturulur)
|
|-- dm_logs/                     # Kullanıcıların DM etkileşim logları (otomatik oluşturulur)
|
|-- assets/                      # Font dosyaları vb.
|   |-- DejaVuSans.ttf
|   |-- DejaVuSans-Bold.ttf
|
|-- turkish_profanity.txt      # Küfür listesi
|-- .env                         # Ortam değişkenleri (eğer yoksa siz oluşturacaksınız)
|-- requirements.txt             # Gerekli Python kütüphaneleri
|-- README_TR.md                    # Bu dosya
|-- benioku.md                    # Bu dosya
|-- LICENSE                      # Lisans dosyası
