# cogs/dm_handler_cog.py
# Bu Cog, gelen DM'leri yakalar, loglar ve kullanıcıların kendi DM'lerini temizlemesini sağlar.

import discord
from discord.ext import commands
import asyncio
import logging

# Yerel modüller
import config
import constants
from utils import helpers # log_interaction için

class DMHandlerCog(commands.Cog, name="DM İşleyici"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dm_cleanup_in_progress = set() # Aynı anda birden fazla temizleme isteğini engellemek için

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Sadece DM mesajlarını işle
        if message.guild is not None:
            return
        # Botun kendi mesajlarını yoksay
        if message.author == self.bot.user:
            return

        user = message.author
        user_id = user.id
        user_name = user.name
        content_lower = message.content.lower().strip()

        # Gelen DM'yi logla (konsola yazdırma, sadece dosyaya)
        # author_type "Kullanıcı DM" olarak belirtilebilir.
        # user_id ve user_name, mesajı gönderen kullanıcıya ait olacak.
        helpers.log_interaction(
            user_id=user_id,
            user_name=user_name,
            author_type="Kullanıcı DM", # DM gönderen kullanıcı
            text=message.content,
            attachments=message.attachments,
            log_to_console=False, # DM'leri ana konsola yazdırma
            is_dm_log=True
        )
        # Konsola sadece kısa bir bilgi (isteğe bağlı)
        # print(f"DM Alındı: {user_name} (ID: {user_id}) -> '{message.content[:50]}...'")

        # Bot sahibi DM'leri için özel durumlar (OwnerDMCog zaten !sdown, !restart gibi komutları dinliyor)
        if user_id == config.BOT_OWNER_ID:
            # Bot sahibi !dmtemizle komutunu OwnerDMCog'dan kullanmalı.
            # Bu Cog, bot sahibinden gelen ve OwnerDMCog tarafından işlenmeyen diğer DM'lere yanıt vermemeli.
            # OwnerDMCog'un on_message'ı da DM'leri dinlediği için çakışma olmaması adına,
            # burada bot sahibinden gelen mesajlara dokunmuyoruz, OwnerDMCog ilgilenecek.
            return # Bot sahibinden gelen DM'ler için bu Cog'da işlem yapma

        # Kullanıcıların kendi DM'lerini temizleme komutu
        if content_lower == f"{config.COMMAND_PREFIX}dmtemizle":
            if user_id in self.dm_cleanup_in_progress:
                await message.author.send("DM temizleme işleminiz zaten devam ediyor. Lütfen tamamlanmasını bekleyin.")
                return

            self.dm_cleanup_in_progress.add(user_id)
            print(f"Kullanıcı {user_name} (ID: {user_id}) kendi DM'lerini temizleme komutu verdi.")
            helpers.log_interaction(user_id, user_name, "Kullanıcı DM", f"{config.COMMAND_PREFIX}dmtemizle komutu kullanıldı.", log_to_console=True, is_dm_log=True)

            deleted_count = 0
            processed_msg = await message.author.send("Özel mesaj geçmişinizdeki bana ait mesajlar temizleniyor...")
            try:
                dm_channel = user.dm_channel
                if not dm_channel:
                    dm_channel = await user.create_dm()

                if not dm_channel:
                    await message.author.send("DM kanalınız oluşturulamadı, bu nedenle mesajlar silinemiyor.")
                    self.dm_cleanup_in_progress.discard(user_id)
                    return

                # Botun bu kullanıcıya gönderdiği mesajları bul ve sil
                async for msg_history in dm_channel.history(limit=None): # Tüm geçmişi tara
                    if msg_history.author == self.bot.user:
                        try:
                            await msg_history.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.6) # Rate Limitine takılmamak için için küçük bir bekleme
                        except discord.Forbidden:
                            print(f"HATA [DMHandlerCog]: DM silinemedi (izin yok) - Mesaj ID: {msg_history.id}")
                        except discord.NotFound:
                            pass # Zaten silinmiş
                        except Exception as e_del:
                            print(f"HATA [DMHandlerCog]: DM silinirken beklenmedik hata: {e_del}")

                response_msg_text = f"Sizinle olan özel mesaj geçmişimden bana ait {deleted_count} mesaj silindi."
                if deleted_count == 0:
                    response_msg_text = "Sizinle olan özel mesaj geçmişimde bana ait silinebilecek bir mesaj bulunamadı."

                await message.author.send(response_msg_text)
                helpers.log_interaction(user_id, user_name, "Sistem", response_msg_text, log_to_console=True, is_dm_log=True)

            except discord.Forbidden:
                await message.author.send("DM geçmişinizi alırken veya mesajları silerken bir izin sorunu oluştu.")
                helpers.log_interaction(user_id, user_name, "Sistem", "Kullanıcı DM temizleme hatası: İzin yok.", log_to_console=True, console_level=logging.ERROR, is_dm_log=True)
            except Exception as e:
                await message.author.send("DM mesajlarınızı temizlerken beklenmedik bir hata oluştu.")
                print(f"HATA [DMHandlerCog]: Kullanıcı DM temizleme hatası: {e}")
                helpers.log_interaction(user_id, user_name, "Sistem", f"Kullanıcı DM temizleme hatası: {e}", log_to_console=True, console_level=logging.ERROR, is_dm_log=True)
            finally:
                self.dm_cleanup_in_progress.discard(user_id)
                try:
                    if processed_msg: await processed_msg.delete() # "Temizleniyor..." mesajını sil
                except: pass
            return # Komut işlendi

        # Bot sahibi dışındaki kullanıcılardan gelen ve komut olmayan DM'lere yanıt verme,
        # sadece logla (yukarıda yapıldı). İsteğe bağlı olarak bir bilgi mesajı gönderilebilir.
        else:
            # print(f"Kullanıcıdan DM alındı (işlenmedi): {user_name} -> {message.content}")
            # Kullanıcıya sadece !dmtemizle komutunu kullanabileceğini belirten bir mesaj gönder.
            # Bu, botun diğer DM'lere yanıt vermediğini açıkça belirtir.
            try:
                await message.author.send(
                    f"Merhaba! Benimle yalnızca sunucuda izin verilen kanallar üzerinden etkileşim kurabilirsiniz. "
                    f"Özel mesajlar (DM) üzerinden sadece `{config.COMMAND_PREFIX}dmtemizle` komutunu kullanarak "
                    f"benim size gönderdiğim mesajları temizleyebilirsiniz.",
                    delete_after=30 # Mesaj 30 saniye sonra silinsin
                )
                # Bu bilgilendirme mesajını da loglayalım (sadece DM loguna)
                helpers.log_interaction(
                    user_id=self.bot.user.id, # Bot gönderdiği için
                    user_name=self.bot.user.name,
                    author_type="Bot DM",
                    text="Kullanıcıya DM komut bilgisi gönderildi.",
                    log_to_console=False,
                    is_dm_log=True, # Karşıdaki kullanıcının DM loguna yaz
                    # DM loguna yazarken user_id ve user_name alıcıya ait olmalı
                    # Bu yüzden log_interaction çağrısını düzenlemek gerekebilir veya
                    # burada doğrudan alıcının ID'si ile loglama yapılmalı.
                    # Şimdilik, log_interaction'ın bu durumu nasıl ele aldığına bağlı.
                    # En iyisi, botun gönderdiği DM'leri loglarken hedef kullanıcı ID'sini kullanmak.
                    # Bu nedenle, bu logu helpers.log_interaction(user_id, user_name, "Bot DM", ...) şeklinde çağırmalıyız.
                )
                # Botun kullanıcıya gönderdiği bu bilgilendirme mesajını logla:
                helpers.log_interaction(
                    user_id=user_id, # Hedef kullanıcı
                    user_name=user_name,
                    author_type="Bot DM",
                    text="Kullanıcıya DM komut bilgisi gönderildi.",
                    log_to_console=False,
                    is_dm_log=True
                )
            except discord.Forbidden:
                pass # DM kapalıysa bir şey yapma
            except Exception as e:
                print(f"HATA [DMHandlerCog]: Kullanıcıya DM bilgi mesajı gönderilirken hata: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(DMHandlerCog(bot))
    # print(f"DMHandlerCog yüklendi.") Log kalabalığını önlemek için kapatıldı.