# utils/persistence.py
# Bu dosya, botun kalıcı verilerini (sohbet geçmişi, durum mesajları vb.)
# dosyaya kaydetmek ve dosyadan yüklemek için fonksiyonlar içerir.

import os
import pickle
import constants # constants.py'deki dosya yollarını kullanmak için

# data klasörünün varlığını kontrol et ve yoksa oluştur
if not os.path.exists("data"):
    try:
        os.makedirs("data")
        print("Bilgi [persistence.py]: 'data' klasörü oluşturuldu.")
    except OSError as e:
        print(f"HATA [persistence.py]: 'data' klasörü oluşturulamadı: {e}")
        # Bu kritik bir hata olabilir, botun veri kaydetmesini/yüklemesini engelleyebilir.
        # Şimdilik devam etmesine izin veriyoruz, ancak loglarda bu hata görünmeli.


def save_data_to_pickle(data, file_path):
    """Verilen veriyi belirtilen pickle dosyasına kaydeder."""
    try:
        # Dosyanın bulunduğu dizini kontrol et, yoksa oluştur
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Bilgi [persistence.py]: '{directory}' klasörü oluşturuldu.")

        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
        # print(f"Veri başarıyla kaydedildi: {file_path}") # Çok sık log üretebilir
        return True
    except Exception as e:
        print(f"HATA [persistence.py]: Veri kaydedilemedi ({file_path}): {e}")
        return False

def load_data_from_pickle(file_path, default_value=None):
    """Belirtilen pickle dosyasından veriyi yükler. Dosya yoksa veya hata oluşursa default_value döner."""
    if default_value is None:
        default_value = {} # Genellikle sözlüklerle çalışıyoruz

    if os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
            print(f"Kaydedilmiş veri yüklendi: {file_path} ({len(data) if isinstance(data, (dict, list)) else 'tek öğe'})")
            return data
        except (pickle.UnpicklingError, EOFError, FileNotFoundError, Exception) as e:
            print(f"HATA [persistence.py]: Veri yüklenemedi ({file_path}): {e}. Varsayılan değer kullanılacak.")
            return default_value
    else:
        print(f"Bilgi [persistence.py]: Veri dosyası bulunamadı ({file_path}). Varsayılan değer kullanılacak.")
        return default_value

# --- Sohbet Verisi Yönetimi ---
def save_chat_data(active_chats_data):
    """
    Aktif sohbet verisini (geçmiş ve meta veriler) kaydeder.
    active_chats_data: {'(channel_id, user_id)': {'history': list, 'last_interaction': datetime, 'warning_sent': str | None}}
    """
    if save_data_to_pickle(active_chats_data, constants.PERSISTENCE_FILE_CHAT):
        # print("Sohbet verisi başarıyla kaydedildi.") # save_data_to_pickle zaten logluyor
        pass


def load_chat_data():
    """
    Kaydedilmiş sohbet verisini yükler.
    Yükleme sonrası eski uyarı durumlarını temizler.
    """
    loaded_data = load_data_from_pickle(constants.PERSISTENCE_FILE_CHAT, default_value={})
    # Yükleme sonrası eski uyarı durumlarını temizle (önemli)
    for key in loaded_data:
        if isinstance(loaded_data.get(key), dict): # Her bir sohbet kaydı bir sözlük olmalı
            loaded_data[key]['warning_sent'] = None # 'warning_sent' anahtarını None yap
    return loaded_data

# --- Durum Mesajı ID'leri Yönetimi ---
def save_status_messages(latest_status_messages):
    """
    Son durum mesajı ID'lerini kaydeder.
    latest_status_messages: {channel_id: message_id}
    """
    if save_data_to_pickle(latest_status_messages, constants.PERSISTENCE_FILE_STATUS):
        # print("Durum mesajı ID'leri başarıyla kaydedildi.")
        pass

def load_status_messages():
    """Kaydedilmiş durum mesajı ID'lerini yükler."""
    return load_data_from_pickle(constants.PERSISTENCE_FILE_STATUS, default_value={})

print("utils/persistence.py yüklendi.")
