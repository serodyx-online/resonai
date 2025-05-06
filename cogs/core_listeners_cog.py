# cogs/core_listeners_cog.py
# Bu Cog, temel olay dinleyicilerini (on_ready'nin bir kısmı, on_close)
# ve periyodik görevleri (cleanup_inactive_chats) içerir.

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta # timedelta eklendi
import asyncio # asyncio.sleep için
import logging # logging seviyeleri için

# Yerel modüller
import config
import constants
from utils import persistence
from utils import helpers # helpers.py'deki fonksiyonları kullanmak için

class CoreListenersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.initial_ready_complete = False # initialize_cog'un sadece bir kez tam çalışmasını sağlamak için

    async def initialize_cog(self):
        if self.initial_ready_complete:
             return

        print(f"CoreListenersCog: Başlangıç işlemleri başlıyor...")

        if config.ALLOWED_CHANNEL_IDS:
            print(f"İzin verilen kanallar ({len(config.ALLOWED_CHANNEL_IDS)}) için kontroller başlıyor...")
            for target_channel_id in config.ALLOWED_CHANNEL_IDS:
                channel = self.bot.get_channel(target_channel_id)
                if not channel or not isinstance(channel, discord.TextChannel):
                    print(f"UYARI [CoreListenersCog]: Kanal ID ({target_channel_id}) bulunamadı/geçersiz.")
                    continue

                print(f"--- Kanal Kontrolü Başladı: #{channel.name} (ID: {target_channel_id}) ---")
                guild_member_bot = channel.guild.me
                if not guild_member_bot:
                    print(f"HATA [CoreListenersCog]: Bot üye nesnesi alınamadı! Kanal: #{channel.name}")
                    continue

                found_pinned_main_embed = False
                current_pinned_embed_id = self.bot.pinned_embed_message_id.get(channel.id)

                if current_pinned_embed_id:
                    try:
                        msg = await channel.fetch_message(current_pinned_embed_id)
                        if msg.author.id == self.bot.user.id and msg.embeds and msg.embeds[0].title == constants.EMBED_TITLE and msg.pinned:
                            found_pinned_main_embed = True
                            print(f"Kayıtlı sabitlenmiş açıklama mesajı (ID: {current_pinned_embed_id}) doğrulandı: #{channel.name}")
                        else:
                            self.bot.pinned_embed_message_id.pop(channel.id, None)
                            print(f"Kayıtlı sabitlenmiş mesaj (ID: {current_pinned_embed_id}) geçersiz/sabitli değil. Kanal pinleri taranacak.")
                    except discord.NotFound:
                        self.bot.pinned_embed_message_id.pop(channel.id, None)
                        print(f"Kayıtlı sabitlenmiş mesaj (ID: {current_pinned_embed_id}) bulunamadı. Kanal pinleri taranacak.")
                    except Exception as e:
                        print(f"HATA [CoreListenersCog]: Kayıtlı sabitlenmiş mesaj ({current_pinned_embed_id}) kontrol edilirken hata: {e}")
                        self.bot.pinned_embed_message_id.pop(channel.id, None)

                if not found_pinned_main_embed:
                    print(f"--- Kanal pinleri taranıyor: #{channel.name} ---" )
                    try:
                        pins = await channel.pins()
                        for pin in pins:
                            if pin.author.id == self.bot.user.id and pin.embeds:
                                if pin.embeds[0].title == constants.EMBED_TITLE:
                                    self.bot.pinned_embed_message_id[channel.id] = pin.id
                                    found_pinned_main_embed = True
                                    print(f"Mevcut sabitlenmiş mesaj bulundu (ID: {pin.id}) Kanal: #{channel.name}")
                                    break
                    except discord.Forbidden:
                        print(f"UYARI [CoreListenersCog]: '{channel.name}' kanalında sabitlenmiş mesajları okuma izni yok.")
                    except Exception as e:
                        print(f"HATA [CoreListenersCog]: '{channel.name}' kanalında sabitlenmiş mesajlar taranırken hata: {e}")

                if not found_pinned_main_embed:
                    print(f"Ana embed mesaj bulunamadı: #{channel.name}")
                    can_send = channel.permissions_for(guild_member_bot).send_messages
                    can_manage = channel.permissions_for(guild_member_bot).manage_messages
                    print(f"CoreListenersCog: İzinler: Send={can_send}, Manage={can_manage} Kanal: #{channel.name}")
                    if can_send and can_manage:
                        print(f"Açıklama embed'i gönderiliyor ve sabitleniyor: #{channel.name}")
                        try:
                            await helpers.send_and_pin_embed(self.bot, channel)
                            print(f"Açıklama embed'i başarıyla gönderildi/sabitlendi: #{channel.name}")
                        except Exception as e_send_embed:
                             print(f"HATA [CoreListenersCog]: helpers.send_and_pin_embed çağrılırken hata: {e_send_embed}")
                    else:
                        print(f"UYARI [CoreListenersCog]: Otomatik açıklama embed'i gönderilemedi/sabitlenemedi (izin yok): #{channel.name}")

                old_status_msg_id = self.bot.latest_status_messages.get(channel.id)
                if old_status_msg_id:
                    current_main_embed_id = self.bot.pinned_embed_message_id.get(channel.id)
                    if old_status_msg_id == current_main_embed_id:
                        print(f"BİLGİ - Eski durum mesajı ({old_status_msg_id}) aynı zamanda ana embed mesajı, silinmeyecek.")
                    else:
                        try:
                            old_msg = await channel.fetch_message(old_status_msg_id)
                            await old_msg.delete()
                            print(f"Eski durum mesajı ({old_status_msg_id}) başarıyla silindi: #{channel.name}")
                        except discord.NotFound:
                            pass
                        except discord.Forbidden:
                            print(f"UYARI [CoreListenersCog]: Eski durum mesajını ({old_status_msg_id}) silme izni yok: #{channel.name}")
                        except Exception as e:
                            print(f"HATA [CoreListenersCog]: Eski durum mesajı ({old_status_msg_id}) silinirken hata: {e}")
                        finally:
                            self.bot.latest_status_messages.pop(channel.id, None)
                try:
                    can_send_status = channel.permissions_for(guild_member_bot).send_messages
                    if can_send_status:
                        online_msg_content = f"{self.bot.user.mention} tekrar aktif! {constants.BOT_UZMANLIK_ALANI} konuşmaya devam edelim. 🎵"
                        online_msg = await channel.send(online_msg_content)
                        self.bot.latest_status_messages[channel.id] = online_msg.id
                        persistence.save_status_messages(self.bot.latest_status_messages)
                        print(f"'Bot Aktif' mesajı gönderildi (ID: {online_msg.id}): #{channel.name}")
                    else:
                        print(f"UYARI [CoreListenersCog]: 'Bot Aktif' mesajı gönderilemedi (izin yok): #{channel.name}")
                except Exception as e_send_active:
                    print(f"HATA [CoreListenersCog]: 'Bot Aktif' mesajı gönderilirken hata: {e_send_active}")
                print(f"--- Kanal Kontrolü Bitti: #{channel.name} ---")
        else:
            print("BİLGİ [CoreListenersCog]: Dinlenecek özel kanal (ALLOWED_CHANNEL_IDS) belirtilmemiş. Durum mesajları ve otomatik embed gönderilmeyecek.")

        if not self.cleanup_inactive_chats_task.is_running():
            # print("Arka plan sohbet temizleme görevi başlatılıyor.") # İsteğe bağlı olarak açılabilir.
            self.cleanup_inactive_chats_task.start()
        self.initial_ready_complete = True
        print("--- Başlangıç işlemleri tamamlandı. ---")

    @commands.Cog.listener()
    async def on_close(self):
        print("Bot bağlantısı kapatılıyor (on_close)...")
        print("Son kez sohbet verisi ve durum mesajları kaydediliyor...")
        persistence.save_chat_data(self.bot.active_chats_data)
        persistence.save_status_messages(self.bot.latest_status_messages)
        print("Veriler CoreListenersCog tarafından kaydedildi. Bot tamamen kapatıldı.")

        if config.ALLOWED_CHANNEL_IDS:
            shutdown_message_content = f"{self.bot.user.mention} beklenmedik bir şekilde çevrimdışı oldu. Sorun giderilmeye çalışılıyor."
            for channel_id in config.ALLOWED_CHANNEL_IDS:
                channel = self.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    try:
                        old_status_msg_id = self.bot.latest_status_messages.get(channel.id)
                        if old_status_msg_id:
                            current_main_embed_id = self.bot.pinned_embed_message_id.get(channel.id)
                            if old_status_msg_id == current_main_embed_id:
                                self.bot.latest_status_messages.pop(channel.id, None)
                            else:
                                try:
                                    old_msg = await channel.fetch_message(old_status_msg_id)
                                    await old_msg.delete()
                                except: pass
                                self.bot.latest_status_messages.pop(channel.id, None)
                        if channel.permissions_for(channel.guild.me).send_messages:
                            sent_msg = await channel.send(shutdown_message_content)
                            self.bot.latest_status_messages[channel.id] = sent_msg.id
                    except Exception as e:
                        print(f"HATA [CoreListenersCog on_close]: Kanal {channel_id} için kapanış mesajı gönderilemedi: {e}")

    @tasks.loop(minutes=constants.CHAT_CLEANUP_INTERVAL_MINUTES)
    async def cleanup_inactive_chats_task(self):
        now = datetime.now(timezone.utc)
        inactive_threshold_td = constants.CHAT_INACTIVITY_THRESHOLD_TD
        warn_10_threshold_td = constants.CHAT_WARN_10_MIN_THRESHOLD_TD
        warn_5_threshold_td = constants.CHAT_WARN_5_MIN_THRESHOLD_TD
        fourteen_days_ago = now - timedelta(days=14)

        keys_to_delete = []
        users_to_warn_10 = {}
        users_to_warn_5 = {}
        users_to_notify_deleted = {}
        current_active_chats_keys = list(self.bot.active_chats_data.keys())

        for chat_key in current_active_chats_keys:
            if chat_key not in self.bot.active_chats_data:
                continue
            try:
                session_data = self.bot.active_chats_data[chat_key]
                last_interaction_time = session_data.get('last_interaction')
                if not last_interaction_time:
                    keys_to_delete.append(chat_key)
                    print(f"UYARI [CoreListenersCog]: {chat_key} için 'last_interaction' bulunamadı, silinmek üzere işaretlendi.")
                    continue
                time_since_last = now - last_interaction_time
                warning_status = session_data.get('warning_sent')

                if time_since_last > inactive_threshold_td:
                    keys_to_delete.append(chat_key)
                    users_to_notify_deleted[chat_key[1]] = chat_key[0]
                elif time_since_last > warn_5_threshold_td and warning_status == '10min':
                    users_to_warn_5[chat_key[1]] = chat_key[0]
                    self.bot.active_chats_data[chat_key]['warning_sent'] = '5min'
                elif time_since_last > warn_10_threshold_td and warning_status is None:
                    users_to_warn_10[chat_key[1]] = chat_key[0]
                    self.bot.active_chats_data[chat_key]['warning_sent'] = '10min'
            except KeyError:
                continue
            except Exception as e:
                print(f"HATA [CoreListenersCog]: cleanup_inactive_chats (adım 1) {chat_key} kontrol edilirken: {e}")

        for user_id, channel_id in users_to_warn_10.items():
            try:
                user = await self.bot.fetch_user(user_id)
                channel_mention = f"<#{channel_id}>"
                dm_message_content = (
                    f"Merhaba! {constants.BOT_ADI} ile {channel_mention} kanalındaki sohbetiniz yaklaşık 10 dakika içinde inaktiflik nedeniyle "
                    f"**kanaldan ve hafızadan** silinecektir. Sohbet dökümünüzü isterseniz kanala gidip "
                    f"`{config.COMMAND_PREFIX}kaydet` komutunu kullanabilirsiniz."
                )
                await user.send(dm_message_content)
                print(f"Kullanıcı {user.name} (ID: {user_id}) için 10dk temizleme uyarısı gönderildi.")
                helpers.log_interaction(user_id, user.name, "Bot DM", dm_message_content, log_to_console=False, is_dm_log=True)
            except discord.Forbidden:
                print(f"HATA [CoreListenersCog]: Kullanıcı {user_id} DM'leri kapalı, 10dk uyarısı gönderilemedi.")
                helpers.log_interaction(user_id, f"User_{user_id}", "Sistem", f"10 dakika sohbet temizleme uyarısı gönderilemedi (DM kapalı, Kanal: {channel_id}).", log_to_console=True, console_level=logging.WARNING, is_dm_log=True)
            except Exception as e:
                print(f"HATA [CoreListenersCog]: Kullanıcı {user_id} için 10dk uyarısı gönderilirken hata: {e}")
                helpers.log_interaction(user_id, f"User_{user_id}", "Sistem", f"10 dakika sohbet temizleme uyarısı gönderilirken hata: {e} (Kanal: {channel_id})", log_to_console=True, console_level=logging.ERROR, is_dm_log=True)

        for user_id, channel_id in users_to_warn_5.items():
            try:
                user = await self.bot.fetch_user(user_id)
                channel_mention = f"<#{channel_id}>"
                dm_message_content = (
                    f"Merhaba! {constants.BOT_ADI} ile {channel_mention} kanalındaki sohbetiniz yaklaşık 5 dakika içinde inaktiflik nedeniyle "
                    f"**kanaldan ve hafızadan** silinecektir. Sohbet dökümünüzü isterseniz kanala gidip "
                    f"`{config.COMMAND_PREFIX}kaydet` komutunu kullanabilirsiniz."
                )
                await user.send(dm_message_content)
                print(f"Kullanıcı {user.name} (ID: {user_id}) için 5dk temizleme uyarısı gönderildi.")
                helpers.log_interaction(user_id, user.name, "Bot DM", dm_message_content, log_to_console=False, is_dm_log=True)
            except discord.Forbidden:
                print(f"HATA [CoreListenersCog]: Kullanıcı {user_id} DM'leri kapalı, 5dk uyarısı gönderilemedi.")
                helpers.log_interaction(user_id, f"User_{user_id}", "Sistem", f"5 dakika sohbet temizleme uyarısı gönderilemedi (DM kapalı, Kanal: {channel_id}).", log_to_console=True, console_level=logging.WARNING, is_dm_log=True)
            except Exception as e:
                print(f"HATA [CoreListenersCog]: Kullanıcı {user_id} için 5dk uyarısı gönderilirken hata: {e}")
                helpers.log_interaction(user_id, f"User_{user_id}", "Sistem", f"5 dakika sohbet temizleme uyarısı gönderilirken hata: {e} (Kanal: {channel_id})", log_to_console=True, console_level=logging.ERROR, is_dm_log=True)

        deleted_data_count_loop = 0
        deleted_messages_total_loop = 0
        processed_users_for_notification_loop = set()

        for chat_key_to_delete in keys_to_delete:
            channel_id_del, user_id_del = chat_key_to_delete
            user_log_name = f"User_{user_id_del}"
            channel_obj_del = self.bot.get_channel(channel_id_del)
            channel_log_name_del = f"#{channel_obj_del.name}" if channel_obj_del else f"ID:{channel_id_del}"
            print(f"İnaktiflik temizliği başlıyor: Kullanıcı={user_id_del}, Kanal={channel_log_name_del}")
            deleted_msg_count_user = 0
            if channel_obj_del and isinstance(channel_obj_del, discord.TextChannel):
                try:
                    bot_member = channel_obj_del.guild.me
                    if bot_member.guild_permissions.manage_messages and bot_member.guild_permissions.read_message_history:
                        messages_to_delete_objs = []
                        async for msg_hist in channel_obj_del.history(limit=constants.CLEANUP_MESSAGE_HISTORY_LIMIT):
                            if msg_hist.created_at <= fourteen_days_ago: continue
                            is_user_msg = msg_hist.author.id == user_id_del
                            is_bot_reply = (
                                msg_hist.author.id == self.bot.user.id and
                                msg_hist.reference and msg_hist.reference.resolved and
                                isinstance(msg_hist.reference.resolved, discord.Message) and
                                msg_hist.reference.resolved.author.id == user_id_del
                            )
                            is_bot_follow = False
                            if msg_hist.author.id == self.bot.user.id:
                                for orig_id, follow_ids in self.bot.split_message_map.items():
                                    if msg_hist.id in follow_ids:
                                        try:
                                            orig_reply = await channel_obj_del.fetch_message(orig_id)
                                            if orig_reply.reference and orig_reply.reference.resolved and \
                                               orig_reply.reference.resolved.author.id == user_id_del:
                                                is_bot_follow = True; break
                                        except: pass
                            if is_user_msg or is_bot_reply or is_bot_follow:
                                messages_to_delete_objs.append(msg_hist)
                        if messages_to_delete_objs:
                            chunk_size = 100
                            for i in range(0, len(messages_to_delete_objs), chunk_size):
                                chunk = messages_to_delete_objs[i:i + chunk_size]
                                if not chunk: continue
                                try:
                                    if len(chunk) == 1: await chunk[0].delete()
                                    else: await channel_obj_del.delete_messages(chunk)
                                    deleted_msg_count_user += len(chunk)
                                    await asyncio.sleep(1.1)
                                except discord.HTTPException as http_e:
                                    if http_e.status != 404: print(f"HATA [CoreListenersCog]: İnaktiflik mesaj silme (HTTP {http_e.status}) - {user_id_del}, {channel_log_name_del}: {http_e.text}")
                                except Exception as del_e: print(f"HATA [CoreListenersCog]: İnaktiflik mesaj silme (beklenmedik) - {user_id_del}, {channel_log_name_del}: {del_e}")
                            deleted_messages_total_loop += deleted_msg_count_user
                            if deleted_msg_count_user > 0:
                                print(f"İnaktiflik: Kullanıcı={user_id_del}, Kanal={channel_log_name_del} için {deleted_msg_count_user} mesaj silindi.")
                                helpers.log_interaction(user_id_del, user_log_name, "Sistem", f"İnaktiflik nedeniyle {channel_log_name_del} kanalından {deleted_msg_count_user} mesaj silindi.", log_to_console=True)
                    else: print(f"UYARI [CoreListenersCog]: İnaktiflik mesaj silme için izinler eksik - Kanal={channel_log_name_del}")
                except discord.Forbidden: print(f"HATA [CoreListenersCog]: İnaktiflik mesaj silme için kanala erişim izni yok - Kanal={channel_log_name_del}")
                except Exception as e: print(f"HATA [CoreListenersCog]: İnaktiflik mesaj silme sırasında hata - {user_id_del}, {channel_log_name_del}: {e}")
            else: print(f"UYARI [CoreListenersCog]: İnaktiflik mesaj silme için kanal bulunamadı/metin kanalı değil - ID={channel_id_del}")

            try:
                data_deleted_flag = False
                if chat_key_to_delete in self.bot.active_chats_data:
                    del self.bot.active_chats_data[chat_key_to_delete]
                    deleted_data_count_loop += 1
                    data_deleted_flag = True
                if chat_key_to_delete in self.bot.active_chat_sessions:
                    del self.bot.active_chat_sessions[chat_key_to_delete]
                if data_deleted_flag:
                    print(f"İnaktiflik: Kullanıcı={user_id_del}, Kanal={channel_log_name_del} için sohbet verisi temizlendi.")
                    helpers.log_interaction(user_id_del, user_log_name, "Sistem", f"İnaktiflik nedeniyle {channel_log_name_del} kanalı için sohbet verisi temizlendi.", log_to_console=True)
                    processed_users_for_notification_loop.add(user_id_del)
            except KeyError: pass
            except Exception as e: print(f"HATA [CoreListenersCog]: İnaktif sohbet verisi silinirken hata ({chat_key_to_delete}): {e}")

        for user_id_notify, channel_id_notify in users_to_notify_deleted.items():
            if user_id_notify in processed_users_for_notification_loop:
                try:
                    user = await self.bot.fetch_user(user_id_notify)
                    channel_mention = f"<#{channel_id_notify}>"
                    dm_message_content = (
                        f"{constants.BOT_ADI} ile {channel_mention} sohbet geçmişiniz, {constants.CHAT_INACTIVITY_THRESHOLD_MINUTES} dakikalık "
                        f"inaktiflik süresini aştığı için hafızadan silinmiştir (**kanaldaki mesajlarınız dahil**)."
                    )
                    await user.send(dm_message_content)
                    print(f"Kullanıcı {user.name} (ID: {user_id_notify}) için sohbet geçmişi silme bildirimi gönderildi.")
                    helpers.log_interaction(user_id_notify, user.name, "Bot DM", dm_message_content, log_to_console=False, is_dm_log=True)
                except discord.Forbidden: print(f"HATA [CoreListenersCog]: Kullanıcı {user_id_notify} DM'leri kapalı, silme bildirimi gönderilemedi.")
                except Exception as e: print(f"HATA [CoreListenersCog]: Kullanıcı {user_id_notify} için silme bildirimi gönderilirken hata: {e}")

        if deleted_data_count_loop > 0:
            persistence.save_chat_data(self.bot.active_chats_data)
            print(f"Arka plan temizliği: {deleted_data_count_loop} adet inaktif sohbet verisi temizlendi.")
        if deleted_messages_total_loop > 0:
            print(f"Arka plan temizliği: Toplam {deleted_messages_total_loop} adet inaktif mesaj silindi.")

    @cleanup_inactive_chats_task.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()
        print("--- Arka plan sohbet temizleme görevi başlatıldı. ---")

async def setup(bot: commands.Bot):
    await bot.add_cog(CoreListenersCog(bot))
    # print("CoreListenersCog yüklendi.") İsteğe bağlı olarak açılabilir. 