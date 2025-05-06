# cogs/owner_dm_cog.py
# Bu Cog, bot sahibine özel DM komutlarını (!sdown, !restart, !dmtemizle) yönetir.

import discord
from discord.ext import commands, tasks # tasks eklendi (gerekirse)
import sys # sys.exit() için
import asyncio # asyncio.sleep için
import logging # logging seviyeleri için

# Yerel modüller
import config
import constants
from utils import persistence # Veri kaydetmek için
from utils import helpers # log_interaction için

class OwnerDMCog(commands.Cog, name="Sahip DM Komutları"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dm_cleanup_in_progress_owner = set() # Sahip komutu için ayrı bir set

    async def _cleanup_user_dms(self, target_user: discord.User, initiated_by_owner: bool = False):
        """Belirtilen kullanıcıya bot tarafından gönderilen DM'leri siler ve kullanıcıyı bilgilendirir."""
        deleted_count = 0
        if target_user.id in self.dm_cleanup_in_progress_owner and initiated_by_owner: # Sahip için ayrı kontrol
            await self.bot.get_user(config.BOT_OWNER_ID).send(f"{target_user.name} (ID: {target_user.id}) için DM temizleme işlemi zaten devam ediyor.")
            return 0
        if not initiated_by_owner and target_user.id in self.bot.get_cog("DM İşleyici").dm_cleanup_in_progress: # Kullanıcı kendi başlattıysa
             # DMHandlerCog zaten mesaj gönderiyor.
            return 0


        if initiated_by_owner:
            self.dm_cleanup_in_progress_owner.add(target_user.id)

        try:
            dm_channel = target_user.dm_channel
            if not dm_channel:
                dm_channel = await target_user.create_dm()

            if not dm_channel:
                if initiated_by_owner:
                    await self.bot.get_user(config.BOT_OWNER_ID).send(f"{target_user.name} (ID: {target_user.id}) için DM kanalı oluşturulamadı.")
                return 0

            async for msg_history in dm_channel.history(limit=None):
                if msg_history.author == self.bot.user:
                    try:
                        await msg_history.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.6)
                    except discord.Forbidden:
                        print(f"HATA [OwnerDMCog]: DM silinemedi (izin yok) - Kullanıcı: {target_user.id}, Mesaj ID: {msg_history.id}")
                    except discord.NotFound:
                        pass
                    except Exception as e_del:
                        print(f"HATA [OwnerDMCog]: DM silinirken beklenmedik hata: {e_del}")
            
            # Temizleme sonrası kullanıcıya bilgilendirme DM'i gönder
            if deleted_count > 0 or initiated_by_owner: # Sahip başlattıysa her zaman mesaj gönder
                try:
                    await target_user.send("Güvenlik ve gizlilik amacıyla sizinle olan özel mesaj geçmişimdeki bana ait mesajlar temizlenmiştir.")
                    helpers.log_interaction(
                        user_id=target_user.id,
                        user_name=target_user.name,
                        author_type="Bot DM",
                        text="DM temizleme sonrası bilgilendirme mesajı gönderildi.",
                        log_to_console=False,
                        is_dm_log=True
                    )
                except discord.Forbidden:
                    print(f"BİLGİ [OwnerDMCog]: {target_user.name} kullanıcısına DM temizleme bildirimi gönderilemedi (DM kapalı).")
                except Exception as e_send_notify:
                    print(f"HATA [OwnerDMCog]: {target_user.name} kullanıcısına DM temizleme bildirimi gönderilirken hata: {e_send_notify}")
            
            return deleted_count
        except discord.Forbidden:
            if initiated_by_owner:
                await self.bot.get_user(config.BOT_OWNER_ID).send(f"{target_user.name} (ID: {target_user.id}) için DM geçmişi alınamadı (izin sorunu).")
            return 0
        except Exception as e:
            print(f"HATA [OwnerDMCog]: _cleanup_user_dms ({target_user.id}) genel hata: {e}")
            if initiated_by_owner:
                await self.bot.get_user(config.BOT_OWNER_ID).send(f"{target_user.name} (ID: {target_user.id}) DM'leri temizlenirken hata oluştu.")
            return 0
        finally:
            if initiated_by_owner:
                self.dm_cleanup_in_progress_owner.discard(target_user.id)


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is not None:
            return
        if message.author == self.bot.user:
            return
        if message.author.id != config.BOT_OWNER_ID:
            # Diğer kullanıcıların DM'leri DMHandlerCog tarafından işlenecek
            return

        owner = message.author
        content_lower = message.content.lower().strip()
        args = message.content.split() # Komut ve argümanları ayır
        command_name = args[0].lower() if args else ""

        # Sahip DM'sini logla
        helpers.log_interaction(
            user_id=owner.id,
            user_name=owner.name,
            author_type="Bot Sahibi DM",
            text=message.content,
            attachments=message.attachments,
            log_to_console=False, # Sahibin DM'lerini konsola yazdırma (isteğe bağlı)
            is_dm_log=True
        )

        if command_name == f"{config.COMMAND_PREFIX}sdown":
            print(f"Bot sahibi '{owner.name}' tarafından DM'den '{config.COMMAND_PREFIX}sdown' komutu alındı.")
            helpers.log_interaction(owner.id, owner.name, "Bot Sahibi", f"{config.COMMAND_PREFIX}sdown komutu kullanıldı.", log_to_console=True, is_dm_log=True)

            shutdown_message_text = f"{self.bot.user.mention} geçici olarak çevrimdışı oluyor. Kısa süre sonra döneceğim!"
            channels_notified = 0
            dm_notification_message = f"Kapatma işlemi başlatıldı."

            if config.ALLOWED_CHANNEL_IDS:
                dm_notification_message += f" {len(config.ALLOWED_CHANNEL_IDS)} izin verilen kanala bildirim gönderilecek..."
                await owner.send(dm_notification_message)
                for channel_id in config.ALLOWED_CHANNEL_IDS:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel and isinstance(channel, discord.TextChannel):
                            old_status_msg_id = self.bot.latest_status_messages.pop(channel.id, None)
                            if old_status_msg_id:
                                try:
                                    old_msg = await channel.fetch_message(old_status_msg_id)
                                    if old_status_msg_id != self.bot.pinned_embed_message_id.get(channel.id):
                                        await old_msg.delete()
                                except: pass
                            if channel.permissions_for(channel.guild.me).send_messages:
                                sent_shutdown_msg = await channel.send(shutdown_message_text)
                                self.bot.latest_status_messages[channel.id] = sent_shutdown_msg.id
                                channels_notified += 1
                                await asyncio.sleep(0.3)
                    except Exception as e_channel_loop:
                        print(f"HATA [OwnerDMCog sdown]: Kanal {channel_id}'ye kapanış mesajı gönderilirken hata: {e_channel_loop}")
                if channels_notified > 0: await owner.send(f"Kapanış mesajı {channels_notified} kanala gönderildi.")
                else: await owner.send(f"Kanallara bildirim yapılamadı.")
            else:
                await owner.send(dm_notification_message + " İzin verilen kanal (ALLOWED_CHANNEL_IDS) belirtilmemiş.")

            await owner.send("Sohbet verisi ve bot durum mesajları kaydediliyor, bot kapatılıyor...")
            print("Sohbet verisi ve bot durum mesajları kaydediliyor, bot kapatılıyor...")
            persistence.save_chat_data(self.bot.active_chats_data)
            persistence.save_status_messages(self.bot.latest_status_messages)
            await self.bot.close()
            return

        elif command_name == f"{config.COMMAND_PREFIX}restart":
            print(f"Bot sahibi '{owner.name}' tarafından DM'den '{config.COMMAND_PREFIX}restart' komutu alındı.")
            helpers.log_interaction(owner.id, owner.name, "Bot Sahibi", f"{config.COMMAND_PREFIX}restart komutu kullanıldı.", log_to_console=True, is_dm_log=True)

            restart_message_text = f"{self.bot.user.mention} yeniden başlatılıyor... Kısa süre içinde döneceğim!"
            channels_notified = 0
            dm_notification_message = f"Yeniden başlatma işlemi başlatıldı."

            if config.ALLOWED_CHANNEL_IDS:
                dm_notification_message += f" {len(config.ALLOWED_CHANNEL_IDS)} izin verilen kanala bildirim gönderilecek..."
                await owner.send(dm_notification_message)
                for channel_id in config.ALLOWED_CHANNEL_IDS:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel and isinstance(channel, discord.TextChannel):
                            old_status_msg_id = self.bot.latest_status_messages.pop(channel.id, None)
                            if old_status_msg_id:
                                try:
                                    old_msg = await channel.fetch_message(old_status_msg_id)
                                    if old_status_msg_id != self.bot.pinned_embed_message_id.get(channel.id):
                                        await old_msg.delete()
                                except: pass
                            if channel.permissions_for(channel.guild.me).send_messages:
                                sent_restart_msg = await channel.send(restart_message_text)
                                self.bot.latest_status_messages[channel.id] = sent_restart_msg.id
                                channels_notified += 1
                                await asyncio.sleep(0.3)
                    except Exception as e_channel_loop_restart:
                         print(f"HATA [OwnerDMCog restart]: Kanal {channel_id}'ye yeniden başlatma mesajı gönderilirken hata: {e_channel_loop_restart}")
                if channels_notified > 0: await owner.send(f"Yeniden başlatma mesajı {channels_notified} kanala gönderildi.")
                else: await owner.send(f"Kanallara bildirim yapılamadı.")
            else:
                await owner.send(dm_notification_message + " İzin verilen kanal (ALLOWED_CHANNEL_IDS) belirtilmemiş.")

            await owner.send("Veriler kaydediliyor, bot yeniden başlatılmak üzere kapatılıyor (Exit Code 5)...")
            print("Veriler kaydediliyor, bot yeniden başlatılmak üzere kapatılıyor (Exit Code 5)...")
            persistence.save_chat_data(self.bot.active_chats_data)
            persistence.save_status_messages(self.bot.latest_status_messages)
            await self.bot.close()
            sys.exit(5)
            return

        elif command_name == f"{config.COMMAND_PREFIX}dmtemizle":
            target_specifier = args[1] if len(args) > 1 else None
            if not target_specifier:
                await owner.send(f"Kullanım: `{config.COMMAND_PREFIX}dmtemizle <kullanıcı_id>` veya `{config.COMMAND_PREFIX}dmtemizle herkes`")
                return

            helpers.log_interaction(owner.id, owner.name, "Bot Sahibi", f"{config.COMMAND_PREFIX}dmtemizle {target_specifier} komutu kullanıldı.", log_to_console=True, is_dm_log=True)
            
            if target_specifier.lower() == "herkes":
                await owner.send("Tüm kullanıcıların DM geçmişindeki bot mesajları temizleniyor... Bu işlem biraz zaman alabilir.")
                cleaned_count_total = 0
                # DM loglarından kullanıcı ID'lerini alabiliriz veya botun açık DM kanallarını gezebiliriz.
                # Şimdilik basitlik adına, botun açık DM kanallarını gezelim.
                # Daha kapsamlısı için dm_logs klasöründeki dosyaları taramak veya bir veritabanı kullanmak gerekir.
                dm_users_cleaned = set()
                for dm_channel_obj in self.bot.private_channels:
                    if isinstance(dm_channel_obj, discord.DMChannel) and dm_channel_obj.recipient:
                        if dm_channel_obj.recipient.id == self.bot.user.id: continue # Botun kendi kendine DM'i atla
                        
                        target_user_obj = dm_channel_obj.recipient
                        if target_user_obj.id in self.dm_cleanup_in_progress_owner: continue

                        print(f"Sahip komutu: {target_user_obj.name} (ID: {target_user_obj.id}) için DM temizliği deneniyor (herkes)...")
                        deleted_for_this_user = await self._cleanup_user_dms(target_user_obj, initiated_by_owner=True)
                        if deleted_for_this_user > 0:
                            cleaned_count_total += deleted_for_this_user
                            dm_users_cleaned.add(target_user_obj.name)
                
                result_msg = f"'herkes' için DM temizleme tamamlandı. Toplam {cleaned_count_total} bot mesajı silindi."
                if dm_users_cleaned:
                    result_msg += f" Etkilenen kullanıcılar (bazıları): {', '.join(list(dm_users_cleaned)[:5])}{'...' if len(dm_users_cleaned) > 5 else ''}"
                await owner.send(result_msg)
                helpers.log_interaction(owner.id, owner.name, "Bot Sahibi", result_msg, log_to_console=True, is_dm_log=True)

            else: # Belirli bir kullanıcı ID'si
                try:
                    target_user_id = int(target_specifier)
                    target_user_obj = self.bot.get_user(target_user_id)
                    if not target_user_obj:
                        target_user_obj = await self.bot.fetch_user(target_user_id) # Cache'de yoksa API'den çek

                    if target_user_obj:
                        if target_user_obj.id in self.dm_cleanup_in_progress_owner:
                            await owner.send(f"{target_user_obj.name} (ID: {target_user_obj.id}) için DM temizleme işlemi zaten devam ediyor.")
                            return
                        
                        await owner.send(f"{target_user_obj.name} (ID: {target_user_obj.id}) kullanıcısının DM geçmişindeki bot mesajları temizleniyor...")
                        deleted_count = await self._cleanup_user_dms(target_user_obj, initiated_by_owner=True)
                        result_msg = f"{target_user_obj.name} (ID: {target_user_obj.id}) için DM temizleme tamamlandı. {deleted_count} bot mesajı silindi."
                        await owner.send(result_msg)
                        helpers.log_interaction(owner.id, owner.name, "Bot Sahibi", result_msg, log_to_console=True, is_dm_log=True)
                    else:
                        await owner.send(f"Kullanıcı ID'si '{target_specifier}' bulunamadı.")
                except ValueError:
                    await owner.send(f"Geçersiz kullanıcı ID'si: '{target_specifier}'. Lütfen sayısal bir ID girin.")
                except discord.NotFound:
                     await owner.send(f"Kullanıcı ID'si '{target_specifier}' Discord'da bulunamadı.")
                except Exception as e_clean_user:
                    await owner.send(f"Kullanıcı '{target_specifier}' için DM temizlenirken hata: {e_clean_user}")
                    print(f"HATA [OwnerDMCog !dmtemizle user]: {e_clean_user}")
            return
        # Diğer sahip DM'leri (komut olmayanlar) için bir şey yapma
        # (veya isteğe bağlı olarak bir "Anlaşılmadı" mesajı gönderilebilir)

async def setup(bot: commands.Bot):
    if config.BOT_OWNER_ID is None:
        print("OwnerDMCog yüklenemedi: BOT_OWNER_ID .env dosyasında tanımlanmamış.")
        return
    await bot.add_cog(OwnerDMCog(bot))
    # print("OwnerDMCog başarıyla yüklendi.") # İsteğe bağlı olarak açılabilir, yükleme bilgi logu.