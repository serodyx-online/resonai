# cogs/admin_commands_cog.py
# Bu Cog, yönetici komutlarını (!embedaciklama, !temizlechat, !sifirla, !cl) içerir.

import discord
from discord.ext import commands
import asyncio # !temizlechat ve !cl için
from datetime import datetime, timezone, timedelta # !cl için
import logging # logging seviyeleri için

# Yerel modüller
import config
import constants
from utils import helpers # is_admin, send_and_pin_embed vb. için
from utils import persistence # !cl komutunda veri kaydetmek için

class AdminCommandsCog(commands.Cog, name="Yönetici Komutları"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Yetki Kontrolü için Decorator (İsteğe Bağlı) ---
    # Veya her komut içinde helpers.is_admin(ctx.author) kontrolü yapılabilir.
    # commands.check kullanmak daha temiz olabilir.
    async def cog_check(self, ctx: commands.Context):
        # Bu Cog'daki tüm komutlar için genel bir kontrol.
        # DM'den gelen komutları engelle (yönetici komutları sunucuda çalışmalı)
        if ctx.guild is None:
            # await ctx.send("Yönetici komutları sadece sunucu kanallarında kullanılabilir.", delete_after=5)
            return False # DM'den ise komut çalışmaz

        if not helpers.is_admin(ctx.author):
            await ctx.send(f"{ctx.author.mention}, bu komutu kullanmak için yönetici yetkiniz bulunmuyor.", delete_after=7)
            try: await ctx.message.delete()
            except: pass
            return False
        return True # Yetkili ise komut çalışır


    @commands.command(name='embedaciklama', help="Kanal açıklama embed'ini gönderir/günceller ve sabitler.")
    @commands.guild_only() # Sadece sunucuda çalışır
    async def embedaciklama_command(self, ctx: commands.Context):
        """
        Mevcut kanala botun ana açıklama embed'ini gönderir,
        varsa eski embed'i siler/sabitlemesini kaldırır ve yenisini sabitler.
        utils.helpers.send_and_pin_embed fonksiyonunu kullanır.
        """
        channel = ctx.channel
        command_user = ctx.author
        print(f"Yönetici '{command_user.name}' tarafından '{config.COMMAND_PREFIX}embedaciklama' komutu kullanıldı: #{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"'{channel.name}' kanalı için {config.COMMAND_PREFIX}embedaciklama komutu kullanıldı.", log_to_console=True)

        # İzin verilen kanallarda mı kontrolü
        if config.ALLOWED_CHANNEL_IDS and channel.id not in config.ALLOWED_CHANNEL_IDS:
            allowed_channels_mentions = [f"<#{ch_id}>" for ch_id in config.ALLOWED_CHANNEL_IDS]
            await channel.send(f"{command_user.mention}, bu komutu sadece botun dinlediği özel kanallarda ({', '.join(allowed_channels_mentions)}) kullanabilirsiniz.", delete_after=10)
            try: await ctx.message.delete()
            except: pass
            return

        # helpers.py'deki fonksiyonu çağır. Bu fonksiyon bot nesnesini ve channel'ı alır.
        # self.bot.pinned_embed_message_id'yi günceller.
        await helpers.send_and_pin_embed(self.bot, channel)
        # helpers.send_and_pin_embed başarılıysa mesaj göndermesine gerek yok, kendi logluyor.
        # Başarısız olursa da kendi logluyor.

        # Komut mesajını sil
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            print(f"HATA [AdminCommandsCog]: '{channel.name}' kanalında {config.COMMAND_PREFIX}embedaciklama komutunu silme izni yok.")
        except discord.NotFound: pass
        except Exception as e:
            print(f"HATA [AdminCommandsCog]: {config.COMMAND_PREFIX}embedaciklama komutu silinirken hata: {e}")


    @commands.command(name='temizlechat', aliases=['clearchat', 'purgechannel'], help="Kanaldaki sabitlenmemiş tüm mesajları siler.")
    @commands.guild_only()
    async def temizlechat_command(self, ctx: commands.Context):
        """
        Komutun kullanıldığı kanaldaki tüm mesajları siler,
        ancak sabitlenmiş mesajları ve botun son durum mesajını korur.
        """
        channel = ctx.channel
        command_user = ctx.author
        print(f"Yönetici '{command_user.name}' tarafından '{config.COMMAND_PREFIX}temizlechat' komutu algılandı: #{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"'{channel.name}' kanalı için {config.COMMAND_PREFIX}temizlechat komutu kullanıldı.", log_to_console=True)

        if config.ALLOWED_CHANNEL_IDS and channel.id not in config.ALLOWED_CHANNEL_IDS:
            allowed_channels_mentions = [f"<#{ch_id}>" for ch_id in config.ALLOWED_CHANNEL_IDS]
            await channel.send(f"{command_user.mention}, bu komutu sadece botun dinlediği özel kanallarda ({', '.join(allowed_channels_mentions)}) kullanabilirsiniz.", delete_after=10)
            try: await ctx.message.delete()
            except: pass
            return

        confirm_msg_content = (
            f"{command_user.mention}, **DİKKAT!** Bu kanaldaki "
            f"**sabitlenmiş mesajlar ve botun son durum mesajı hariç** tüm mesajları silmek üzeresiniz. "
            f"Emin misiniz? Onaylamak için 15 saniye içinde `evet` yazın."
        )
        confirm_msg = await channel.send(confirm_msg_content)

        def check_confirmation(m: discord.Message):
            return m.author.id == command_user.id and m.channel.id == channel.id and m.content.lower() == 'evet'

        processing_msg = None # processing_msg'yi başta None olarak tanımla
        try:
            confirmation = await self.bot.wait_for('message', timeout=15.0, check=check_confirmation)
            try:
                await confirm_msg.delete()
                await confirmation.delete()
            except discord.NotFound: pass # Zaten silinmişse sorun yok
            except Exception as e_del_confirm: print(f"Hata: Onay mesajları silinirken: {e_del_confirm}")


            print(f"'{command_user.name}' tarafından {config.COMMAND_PREFIX}temizlechat onaylandı.")
            helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"{config.COMMAND_PREFIX}temizlechat komutu onaylandı.", log_to_console=True)
            processing_msg = await channel.send("Mesajlar siliniyor, lütfen bekleyin...")

            # Silinmeyecek mesaj ID'lerini belirle
            excluded_message_ids = set() # Adını değiştirelim
            try:
                pinned_messages = await channel.pins()
                excluded_message_ids.update(p.id for p in pinned_messages)
            except discord.Forbidden:
                print(f"UYARI [{self.qualified_name}]: Sabitlenmiş mesajları okuma izni yok: #{channel.name}")
            except Exception as e_pins:
                print(f"HATA [{self.qualified_name}]: Sabitlenmiş mesajlar alınırken hata: {e_pins}")


            # Ana açıklama embed'i
            main_embed_id = self.bot.pinned_embed_message_id.get(channel.id)
            if main_embed_id:
                excluded_message_ids.add(main_embed_id)

            # Son durum mesajı
            latest_status_msg_id = self.bot.latest_status_messages.get(channel.id)
            if latest_status_msg_id:
                excluded_message_ids.add(latest_status_msg_id)

            # Komut mesajı ve işlem mesajını da ekle
            excluded_message_ids.add(ctx.message.id)
            if processing_msg:
                excluded_message_ids.add(processing_msg.id)

            print(f"Silinmeyecek Mesaj ID'leri ({config.COMMAND_PREFIX}temizlechat): {excluded_message_ids}")

            deleted_messages = await channel.purge(limit=None, check=lambda m: m.id not in excluded_message_ids)

            if processing_msg: # İşlem mesajını silmeyi dene
                try: await processing_msg.delete()
                except discord.NotFound: pass
                except Exception as e_del_proc: print(f"Hata: İşlem mesajı silinirken: {e_del_proc}")

            result_msg_content = (
                f"İşlem tamamlandı! Sabitlenmiş mesajlar ve bot durum mesajı hariç "
                f"**{len(deleted_messages)}** adet mesaj silindi."
            )
            await channel.send(result_msg_content, delete_after=7)
            print(f"{config.COMMAND_PREFIX}temizlechat tamamlandı. {len(deleted_messages)} mesaj silindi.")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizlechat tamamlandı. {len(deleted_messages)} mesaj silindi.", log_to_console=True)

        except asyncio.TimeoutError:
            try: await confirm_msg.edit(content="Onay zaman aşımına uğradı. İşlem iptal edildi.", delete_after=7)
            except discord.NotFound: pass
            print(f"{config.COMMAND_PREFIX}temizlechat işlemi zaman aşımı nedeniyle iptal edildi.")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizlechat işlemi zaman aşımı nedeniyle iptal edildi.", log_to_console=True)
        except discord.Forbidden:
            print(f"HATA [AdminCommandsCog]: '{channel.name}' kanalında mesaj silme (purge) izni yok.")
            await channel.send(f"{command_user.mention}, mesajları toplu silme iznim yok gibi görünüyor.", delete_after=7)
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizlechat hatası: Mesajları Yönet izni yok.", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        except discord.HTTPException as e:
            print(f"HATA [AdminCommandsCog]: Toplu silme sırasında hata (HTTP {e.status}): {e.text}")
            if e.status != 404:
                await channel.send(f"{command_user.mention}, mesajlar silinirken bir sorun oluştu (Hata: {e.status}).", delete_after=7)
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizlechat hatası: HTTP {e.status} - {e.text}", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        except Exception as e:
            print(f"HATA [AdminCommandsCog]: {config.COMMAND_PREFIX}temizlechat sırasında beklenmedik hata: {e}")
            await channel.send(f"{command_user.mention}, mesajlar silinirken beklenmedik bir hata oluştu.", delete_after=7)
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizlechat hatası: {e}", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        finally:
            # Komut mesajını silmeyi dene (eğer purge ile silinmediyse)
            try: await ctx.message.delete()
            except discord.NotFound: pass
            except Exception as e_del_cmd: print(f"Hata: Komut mesajı silinirken (!temizlechat): {e_del_cmd}")


    @commands.command(name='sifirla', aliases=['resetviolations'], help="Belirtilen kullanıcının küfür veya konu dışı ihlal sayacını sıfırlar.")
    @commands.guild_only()
    async def sifirla_command(self, ctx: commands.Context, target_user: discord.Member, counter_type: str):
        """
        Belirtilen kullanıcının küfür veya konu dışı ihlal sayacını sıfırlar.
        Kullanım: !sifirla <@kullanıcı/ID> <küfür/konu>
        """
        command_user = ctx.author
        channel = ctx.channel
        counter_type_lower = counter_type.lower()
        valid_counter_types = {'küfür', 'kufur', 'profanity', 'konu', 'konudisi', 'offtopic', 'off-topic'}

        print(f"Yönetici '{command_user.name}' tarafından '{config.COMMAND_PREFIX}sifirla' komutu kullanıldı: {target_user.name} için {counter_type_lower}")
        helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"{target_user.name} (ID: {target_user.id}) için {config.COMMAND_PREFIX}sifirla ({counter_type_lower}) komutu kullanıldı.", log_to_console=True)

        if counter_type_lower not in valid_counter_types:
            await channel.send(f"{command_user.mention}, geçersiz seçenek tipi. 'küfür' veya 'konu' kullanın.", delete_after=7)
            try: await ctx.message.delete()
            except: pass
            return

        target_user_id = target_user.id
        if target_user_id not in self.bot.user_violations:
            self.bot.user_violations[target_user_id] = {'profanity_count': 0, 'off_topic_count': 0, 'last_warning_type': None}
            await channel.send(f"{command_user.mention}, {target_user.mention} kullanıcısının zaten kayıtlı ihlali bulunmuyor (yeni kayıt oluşturuldu).", delete_after=7)
            try: await ctx.message.delete()
            except: pass
            return

        reset_success = False
        reset_type_display = ""

        if counter_type_lower in ['küfür', 'kufur', 'profanity']:
            reset_type_display = "küfür"
            if self.bot.user_violations[target_user_id].get('profanity_count', 0) > 0:
                self.bot.user_violations[target_user_id]['profanity_count'] = 0
                self.bot.user_violations[target_user_id]['last_warning_type'] = None # Timeout sonrası tekrar uyarı alabilmesi için
                reset_success = True
            else:
                await channel.send(f"{command_user.mention}, {target_user.mention} kullanıcısının zaten sıfır küfür ihlali var.", delete_after=7)
        elif counter_type_lower in ['konu', 'konudisi', 'offtopic', 'off-topic']:
            reset_type_display = "konu dışı"
            if self.bot.user_violations[target_user_id].get('off_topic_count', 0) > 0:
                self.bot.user_violations[target_user_id]['off_topic_count'] = 0
                self.bot.user_violations[target_user_id]['last_warning_type'] = None
                reset_success = True
            else:
                await channel.send(f"{command_user.mention}, {target_user.mention} kullanıcısının zaten sıfır konu dışı ihlali var.", delete_after=7)

        if reset_success:
            await channel.send(f"{command_user.mention}, {target_user.mention} kullanıcısının **{reset_type_display}** ihlal sayacı başarıyla sıfırlandı.", delete_after=7)
            print(f"Yönetici {command_user.name}, {target_user.name} kullanıcısının {reset_type_display} sayacını sıfırladı.")
            helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"{target_user.name} (ID: {target_user.id}) kullanıcısının {reset_type_display} sayacı sıfırlandı.", log_to_console=True)
        try: await ctx.message.delete()
        except: pass

    @sifirla_command.error
    async def sifirla_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{ctx.author.mention}, komut kullanımı: `{config.COMMAND_PREFIX}sifirla <@kullanıcı/ID> <küfür/konu>`", delete_after=7)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(f"{ctx.author.mention}, belirtilen kullanıcı ('{error.argument}') sunucuda bulunamadı.", delete_after=7)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"{ctx.author.mention}, geçersiz argüman. Kullanıcıyı etiketleyin veya ID'sini girin.", delete_after=7)
        # Cog check hatasını burada yakalamaya gerek yok, cog_check kendi mesajını gönderiyor.
        # elif isinstance(error, commands.CheckFailure):
        #     pass
        else:
            await ctx.send(f"{ctx.author.mention}, `{config.COMMAND_PREFIX}sifirla` komutunda bir hata oluştu: {error}", delete_after=7)
            print(f"HATA [AdminCommandsCog]: {config.COMMAND_PREFIX}sifirla komut hatası: {error}")
        try: await ctx.message.delete()
        except: pass


    @commands.command(name='cl', help="Belirtilen kullanıcının veya herkesin sohbet geçmişini ve mesajlarını temizler.")
    @commands.guild_only()
    async def cl_command(self, ctx: commands.Context, target_arg: str):
        """
        Yönetici komutu. Belirtilen kullanıcının botla olan sohbet geçmişini ve
        ilgili mesajlarını (son 14 gün) kanaldan siler.
        'herkes' argümanı ile kanaldaki tüm kullanıcıların botla olan geçmişi ve
        tüm mesajlar (sabitlenmişler ve bot durum mesajı hariç) silinir.
        """
        command_user = ctx.author
        channel = ctx.channel
        guild = ctx.guild
        bot_member = guild.me
        target_arg_lower = target_arg.lower()

        print(f"Yönetici '{command_user.name}' tarafından '{config.COMMAND_PREFIX}cl' komutu kullanıldı: Hedef='{target_arg_lower}', Kanal=#{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Yönetici", f"'{channel.name}' kanalı için {config.COMMAND_PREFIX}cl komutu kullanıldı: {target_arg_lower}", log_to_console=True)

        if config.ALLOWED_CHANNEL_IDS and channel.id not in config.ALLOWED_CHANNEL_IDS:
            allowed_channels_mentions = [f"<#{ch_id}>" for ch_id in config.ALLOWED_CHANNEL_IDS]
            await channel.send(f"{command_user.mention}, bu komutu sadece botun dinlediği özel kanallarda ({', '.join(allowed_channels_mentions)}) kullanabilirsiniz.", delete_after=10)
            try: await ctx.message.delete()
            except: pass
            return

        clear_all_users = (target_arg_lower == 'herkes')
        target_member_to_clear: discord.Member = None

        if not clear_all_users:
            try:
                target_member_to_clear = await commands.MemberConverter().convert(ctx, target_arg)
            except commands.MemberNotFound:
                await channel.send(f"{command_user.mention}, belirtilen kullanıcı ('{target_arg}') sunucuda bulunamadı.", delete_after=7)
                try: await ctx.message.delete()
                except: pass
                return

        confirm_text = ""
        if clear_all_users:
            confirm_text = (
                f"{command_user.mention}, **DİKKAT!** Bu kanaldaki **tüm kullanıcıların** botla olan sohbet geçmişi hafızası temizlenecek "
                f"**VE** kanaldaki **sabitlenmiş mesajlar ve botun son durum mesajı hariç tüm mesajlar** silinecek. "
                f"Emin misiniz? Onaylamak için 15 saniye içinde `evet` yazın."
            )
        else:
            confirm_text = (
                f"{command_user.mention}, **DİKKAT!** {target_member_to_clear.mention} kullanıcısının bu kanaldaki botla olan sohbet geçmişi hafızası temizlenecek "
                f"**VE** bu kullanıcıya ait/yanıt olan mesajlar (son 14 gün) silinecek. "
                f"Emin misiniz? Onaylamak için 15 saniye içinde `evet` yazın."
            )

        confirm_msg = await channel.send(confirm_text)
        def check_confirmation(m: discord.Message):
            return m.author.id == command_user.id and m.channel.id == channel.id and m.content.lower() == 'evet'

        processing_msg = None # processing_msg'yi başta None olarak tanımla
        try:
            confirmation = await self.bot.wait_for('message', timeout=15.0, check=check_confirmation)
            try:
                await confirm_msg.delete()
                await confirmation.delete()
            except discord.NotFound: pass
            except Exception as e_del_confirm: print(f"Hata: Onay mesajları silinirken: {e_del_confirm}")


            processing_msg = await channel.send("Geçmiş temizleniyor ve mesajlar siliniyor, lütfen bekleyin...")
            log_target_name = "Herkes" if clear_all_users else target_member_to_clear.name

            # 1. Hafızayı Temizle
            deleted_session_count = 0
            deleted_data_count = 0
            if clear_all_users:
                keys_to_remove_sessions = [key for key in self.bot.active_chat_sessions if key[0] == channel.id]
                for key in keys_to_remove_sessions:
                    try: del self.bot.active_chat_sessions[key]; deleted_session_count += 1
                    except KeyError: pass
                keys_to_remove_data = [key for key in self.bot.active_chats_data if key[0] == channel.id]
                for key in keys_to_remove_data:
                    try: del self.bot.active_chats_data[key]; deleted_data_count += 1
                    except KeyError: pass
            else:
                target_chat_key = (channel.id, target_member_to_clear.id)
                if target_chat_key in self.bot.active_chat_sessions:
                    try: del self.bot.active_chat_sessions[target_chat_key]; deleted_session_count = 1
                    except KeyError: pass
                if target_chat_key in self.bot.active_chats_data:
                    try: del self.bot.active_chats_data[target_chat_key]; deleted_data_count = 1
                    except KeyError: pass

            if deleted_data_count > 0 : # Sadece değişiklik varsa kaydet
                persistence.save_chat_data(self.bot.active_chats_data)
                print(f"Hafıza temizlendi ({log_target_name}). Data: {deleted_data_count}")
            if deleted_session_count > 0:
                 print(f"Aktif oturumlar temizlendi ({log_target_name}). Sessions: {deleted_session_count}")
            if deleted_data_count == 0 and deleted_session_count == 0:
                print(f"Temizlenecek hafıza verisi bulunamadı ({log_target_name}).")

            # 2. Mesajları Sil
            deleted_message_count = 0
            if not channel.permissions_for(bot_member).manage_messages:
                if processing_msg: await processing_msg.edit(content=f"{command_user.mention}, hafıza temizlendi ancak mesajları silme iznim yok.")
                else: await channel.send(f"{command_user.mention}, hafıza temizlendi ancak mesajları silme iznim yok.", delete_after=7)
                helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl hatası ({log_target_name}): Mesajları Yönet izni yok.", log_to_console=True, console_level=logging.ERROR)
            else:
                if clear_all_users:
                    excluded_message_ids = set()
                    try:
                        pinned_messages = await channel.pins()
                        excluded_message_ids.update(p.id for p in pinned_messages)
                    except discord.Forbidden: print(f"UYARI [{self.qualified_name}]: Sabitlenmiş mesajları okuma izni yok: #{channel.name}")
                    except Exception as e_pins: print(f"HATA [{self.qualified_name}]: Sabitlenmiş mesajlar alınırken hata: {e_pins}")

                    main_embed_id = self.bot.pinned_embed_message_id.get(channel.id)
                    if main_embed_id: excluded_message_ids.add(main_embed_id)
                    latest_status_msg_id = self.bot.latest_status_messages.get(channel.id)
                    if latest_status_msg_id: excluded_message_ids.add(latest_status_msg_id)

                    # Komut mesajını ve işlem mesajını da ekle
                    excluded_message_ids.add(ctx.message.id)
                    if processing_msg: excluded_message_ids.add(processing_msg.id)

                    print(f"Silinmeyecek Mesaj ID'leri (!cl herkes): {excluded_message_ids}")
                    deleted_messages_objs = await channel.purge(limit=None, check=lambda m: m.id not in excluded_message_ids)
                    deleted_message_count = len(deleted_messages_objs)
                else: # Belirli kullanıcı için
                    messages_to_delete_objs = []
                    fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
                    async for msg_hist in channel.history(limit=500):
                        if msg_hist.created_at <= fourteen_days_ago: continue
                        # Sabitlenmiş ana embed ve son durum mesajını koru
                        if msg_hist.id == self.bot.pinned_embed_message_id.get(channel.id) or \
                           msg_hist.id == self.bot.latest_status_messages.get(channel.id):
                            continue
                        # Komut mesajını ve işlem mesajını koru
                        if msg_hist.id == ctx.message.id or (processing_msg and msg_hist.id == processing_msg.id):
                            continue

                        is_target_user_msg = msg_hist.author.id == target_member_to_clear.id
                        is_bot_reply_to_target = (
                            msg_hist.author.id == self.bot.user.id and
                            msg_hist.reference and msg_hist.reference.resolved and
                            isinstance(msg_hist.reference.resolved, discord.Message) and
                            msg_hist.reference.resolved.author.id == target_member_to_clear.id
                        )
                        is_bot_follow_up_to_target = False
                        if msg_hist.author.id == self.bot.user.id:
                            for original_id, follow_ids in self.bot.split_message_map.items():
                                if msg_hist.id in follow_ids:
                                    try:
                                        original_reply = await channel.fetch_message(original_id)
                                        if original_reply.reference and original_reply.reference.resolved and \
                                           original_reply.reference.resolved.author.id == target_member_to_clear.id:
                                            is_bot_follow_up_to_target = True; break
                                    except: pass
                        if is_target_user_msg or is_bot_reply_to_target or is_bot_follow_up_to_target:
                            messages_to_delete_objs.append(msg_hist)

                    if messages_to_delete_objs:
                        chunk_size = 100
                        for i in range(0, len(messages_to_delete_objs), chunk_size):
                            chunk = messages_to_delete_objs[i:i + chunk_size]
                            if not chunk: continue
                            try:
                                if len(chunk) == 1: await chunk[0].delete()
                                else: await channel.delete_messages(chunk)
                                deleted_message_count += len(chunk)
                                if len(messages_to_delete_objs) > chunk_size and (i + chunk_size) < len(messages_to_delete_objs):
                                    await asyncio.sleep(1.1)
                            except discord.HTTPException as http_e:
                                if http_e.status != 404: print(f"HATA [AdminCommandsCog !cl]: Mesaj silme (HTTP {http_e.status}): {http_e.text}")
                            except Exception as del_e: print(f"HATA [AdminCommandsCog !cl]: Mesaj silme (beklenmedik): {del_e}")

                # İşlem mesajını silmeyi dene
                if processing_msg:
                    try: await processing_msg.delete()
                    except discord.NotFound: pass
                    except Exception as e_del_proc: print(f"Hata: İşlem mesajı silinirken (!cl): {e_del_proc}")

                final_feedback_text = f"{command_user.mention}, {log_target_name} için işlem tamamlandı. "
                if deleted_data_count > 0 or deleted_session_count > 0:
                    final_feedback_text += "Sohbet geçmişi hafızadan temizlendi. "
                if deleted_message_count > 0:
                    final_feedback_text += f"İlgili **{deleted_message_count}** mesaj silindi."
                elif channel.permissions_for(bot_member).manage_messages: # İzin var ama mesaj silinmediyse
                    final_feedback_text += "Silinecek ilgili mesaj bulunamadı."

                await channel.send(final_feedback_text.strip(), delete_after=7)
                helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({log_target_name}) tamamlandı. Hafıza: {deleted_data_count+deleted_session_count}, Mesajlar: {deleted_message_count}", log_to_console=True)

        except asyncio.TimeoutError:
            try: await confirm_msg.edit(content="Onay zaman aşımına uğradı. İşlem iptal edildi.", delete_after=7)
            except discord.NotFound: pass
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({target_arg_lower}) işlemi zaman aşımı nedeniyle iptal edildi.", log_to_console=True)
        except discord.Forbidden as e_forbidden:
            await channel.send(f"{command_user.mention}, işlem sırasında bir izin hatası oluştu: {e_forbidden}", delete_after=7)
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({target_arg_lower}) hatası: İzin yok - {e_forbidden}", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        except discord.HTTPException as e_http:
            # 404 hatasını burada yakalayıp görmezden gel
            if e_http.status == 404:
                 print(f"Bilgi [AdminCommandsCog !cl]: İşlem sırasında 404 hatası alındı (muhtemelen zaten silinmiş mesaj), görmezden geliniyor.")
                 helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({target_arg_lower}) sırasında 404 hatası alındı.", log_to_console=True, console_level=logging.WARNING)
                 # İşlem mesajını silmeyi dene
                 if processing_msg:
                     try: await processing_msg.delete()
                     except discord.NotFound: pass
                     except Exception as e_del_proc: print(f"Hata: İşlem mesajı silinirken (404 sonrası): {e_del_proc}")
                 # Kullanıcıya genel bir başarı mesajı gönderilebilir
                 await channel.send(f"{command_user.mention}, {log_target_name} için temizleme işlemi tamamlandı.", delete_after=7)

            else:
                await channel.send(f"{command_user.mention}, işlem sırasında bir Discord API hatası oluştu (Hata: {e_http.status}).", delete_after=7)
                helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({target_arg_lower}) hatası: HTTP {e_http.status} - {e_http.text}", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        except Exception as e_general:
            await channel.send(f"{command_user.mention}, işlem sırasında beklenmedik bir hata oluştu: {e_general}", delete_after=7)
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"!cl ({target_arg_lower}) hatası: {e_general}", log_to_console=True, console_level=logging.ERROR)
            try: await confirm_msg.delete()
            except discord.NotFound: pass
        finally:
            # Komut mesajını silmeyi dene (eğer purge ile silinmediyse)
            try: await ctx.message.delete()
            except discord.NotFound: pass
            except Exception as e_del_cmd: print(f"Hata: Komut mesajı silinirken (!cl finally): {e_del_cmd}")

    @cl_command.error
    async def cl_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"{ctx.author.mention}, komut kullanımı: `{config.COMMAND_PREFIX}cl <@kullanıcı/ID/herkes>`", delete_after=7)
        elif isinstance(error, commands.BadArgument): # MemberNotFound yerine BadArgument daha genel olabilir
             await ctx.send(f"{ctx.author.mention}, geçersiz argüman. Kullanıcıyı etiketleyin, ID'sini girin veya 'herkes' yazın.", delete_after=7)
        # Cog check hatasını burada yakalamaya gerek yok, cog_check kendi mesajını gönderiyor.
        # elif isinstance(error, commands.CheckFailure):
        #     pass
        else:
            await ctx.send(f"{ctx.author.mention}, `{config.COMMAND_PREFIX}cl` komutunda bir hata oluştu: {error}", delete_after=7)
            print(f"HATA [AdminCommandsCog]: {config.COMMAND_PREFIX}cl komut hatası: {error}")
        try: await ctx.message.delete()
        except: pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommandsCog(bot))
    # print("AdminCommandsCog başarıyla yüklendi ve ayarlandı.") # Kaldırıldı

