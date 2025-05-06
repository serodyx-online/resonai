# cogs/user_commands_cog.py
# Bu Cog, genel kullanıcı komutlarını (!yardim, !kaydet, !temizle) içerir.

import discord
from discord.ext import commands
from datetime import datetime, timezone, timedelta # !temizle için
import asyncio # !temizle için
import logging # logging seviyeleri için

# Yerel modüller
import config
import constants
from utils import helpers # PDF oluşturma, uzun mesaj gönderme vb. için
from utils import persistence # !temizle komutunda veri kaydetmek için

class UserCommandsCog(commands.Cog, name="Kullanıcı Komutları"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='yardim', aliases=['help', 'yardım'], help="Bot ve komutları hakkında yardım bilgilerini DM ile gönderir.")
    async def yardim_command(self, ctx: commands.Context):
        command_user = ctx.author
        channel = ctx.channel
        print(f"'{command_user.name}' tarafından '{config.COMMAND_PREFIX}yardim' komutu algılandı: #{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Kullanıcı", f"{config.COMMAND_PREFIX}yardim komutu kullanıldı.", log_to_console=True)

        formatted_yardim_mesaji = constants.YARDIM_MESAJI_TEMPLATE.format(
            COMMAND_PREFIX=config.COMMAND_PREFIX,
            CHAT_INACTIVITY_THRESHOLD_MINUTES=constants.CHAT_INACTIVITY_THRESHOLD_MINUTES
        )

        try:
            await command_user.send(formatted_yardim_mesaji)
            print(f"Yardım mesajı DM olarak gönderildi: {command_user.name}")
            # Botun gönderdiği DM'yi logla
            helpers.log_interaction(
                user_id=command_user.id, # DM'in gönderildiği kullanıcı
                user_name=command_user.name,
                author_type="Bot DM", # Gönderen bot olduğu için
                text=f"Yardım mesajı gönderildi. (İçerik: ...{formatted_yardim_mesaji[:100]}...)", # İçeriğin bir kısmını logla
                log_to_console=False, # Konsola zaten bilgi yazıldı
                is_dm_log=True
            )
            try:
                await channel.send(f"{command_user.mention}, yardım bilgileri özel mesaj (DM) olarak gönderildi.", delete_after=7)
            except discord.HTTPException as send_error:
                print(f"HATA [UserCommandsCog]: Yardım onayı gönderilemedi: {send_error}")
        except discord.Forbidden:
            error_msg = f"Kullanıcıya DM gönderilemiyor (DM'leri kapalı olabilir): {command_user.name}"
            print(f"HATA [UserCommandsCog]: {error_msg}")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.WARNING)
            await channel.send(
                f"{command_user.mention}, DM'lerin kapalı olduğu için yardım mesajını gönderemedim. "
                f"Lütfen DM ayarlarını kontrol et veya komut listesi için kanal açıklamasını oku.",
                delete_after=10
            )
        except discord.HTTPException as e:
            error_msg = f"Yardım DM'i gönderilemedi (HTTP {e.status}): {e.text}"
            print(f"HATA [UserCommandsCog]: {error_msg}")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
            await channel.send(f"{command_user.mention}, yardım mesajı gönderilirken bir sorun oluştu (Hata: {e.status}).", delete_after=7)
        except Exception as e:
            error_msg = f"Yardım mesajı gönderilirken beklenmedik hata: {e}"
            print(f"HATA [UserCommandsCog]: {error_msg}")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
            await channel.send(f"{command_user.mention}, yardım mesajı gönderilirken beklenmedik bir hata oluştu.", delete_after=7)

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            print(f"HATA [UserCommandsCog]: '{channel.name}' kanalında {config.COMMAND_PREFIX}yardim komutunu silme izni yok.")
        except discord.NotFound: pass
        except Exception as e:
            print(f"HATA [UserCommandsCog]: {config.COMMAND_PREFIX}yardim komutu silinirken hata: {e}")

    @commands.command(name='kaydet', help="Sizinle olan sohbet geçmişini DM olarak PDF formatında gönderir.")
    async def kaydet_command(self, ctx: commands.Context):
        command_user = ctx.author
        channel = ctx.channel
        print(f"'{command_user.name}' tarafından '{config.COMMAND_PREFIX}kaydet' komutu algılandı: #{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Kullanıcı", f"{config.COMMAND_PREFIX}kaydet komutu kullanıldı.", log_to_console=True)

        if config.ALLOWED_CHANNEL_IDS and channel.id not in config.ALLOWED_CHANNEL_IDS:
            await channel.send(f"{command_user.mention}, bu komutu sadece botun aktif olduğu özel kanallarda kullanabilirsiniz.", delete_after=7)
            try: await ctx.message.delete();
            except: pass
            return

        chat_key = (channel.id, command_user.id)
        user_channel_history_data = self.bot.active_chats_data.get(chat_key, {}).get('history', [])

        if not user_channel_history_data:
            await channel.send(f"{command_user.mention}, seninle bu kanalda kaydedilecek bir sohbet geçmişi bulunamadı.", delete_after=7)
            try: await ctx.message.delete()
            except: pass
            return

        # PDF oluşturma ve gönderme işlemini helpers modülüne devret
        # helpers.generate_and_send_pdf_transcript içinde DM loglaması zaten yapılıyor (is_dm_log=True ile)
        await helpers.generate_and_send_pdf_transcript(self.bot, ctx.message, user_channel_history_data)


    @commands.command(name='temizle', help="Sizinle olan son 14 günlük mesajları siler ve sohbet geçmişinizi bot hafızasından temizler.")
    async def temizle_command(self, ctx: commands.Context):
        command_user = ctx.author
        channel = ctx.channel
        guild = ctx.guild
        bot_member = guild.me

        print(f"'{command_user.name}' tarafından '{config.COMMAND_PREFIX}temizle' komutu algılandı: #{channel.name}")
        helpers.log_interaction(command_user.id, command_user.name, "Kullanıcı", f"{config.COMMAND_PREFIX}temizle komutu kullanıldı.", log_to_console=True)

        if config.ALLOWED_CHANNEL_IDS and channel.id not in config.ALLOWED_CHANNEL_IDS:
            await channel.send(f"{command_user.mention}, bu komutu sadece botun aktif olduğu özel kanallarda kullanabilirsiniz.", delete_after=7)
            try: await ctx.message.delete()
            except: pass
            return

        if not channel.permissions_for(bot_member).manage_messages:
            await channel.send(f"{command_user.mention}, üzgünüm ama bu kanalda mesajları silme iznim yok.", delete_after=7)
            print(f"HATA [UserCommandsCog]: !temizle - Mesajları Yönet izni yok: #{channel.name}")
            try: await ctx.message.delete()
            except: pass
            return

        feedback_msg = await channel.send(f"{command_user.mention}, seninle olan mesajlarımız kanaldan ve hafızamdan siliniyor...", delete_after=5)
        user_chat_key = (channel.id, command_user.id)

        if user_chat_key in self.bot.active_chat_sessions:
            try:
                del self.bot.active_chat_sessions[user_chat_key]
                print(f"Kullanıcı {command_user.name} için sohbet oturumu (Gemini) hafızadan temizlendi.")
                helpers.log_interaction(command_user.id, command_user.name, "Sistem", "Kullanıcının Gemini sohbet oturumu hafızadan temizlendi.", log_to_console=True)
            except KeyError: pass
            except Exception as e:
                print(f"HATA [UserCommandsCog]: Kullanıcı Gemini oturumu temizlenirken hata: {e}")

        data_cleaned_from_persistence = False
        if user_chat_key in self.bot.active_chats_data:
            try:
                del self.bot.active_chats_data[user_chat_key]
                persistence.save_chat_data(self.bot.active_chats_data)
                data_cleaned_from_persistence = True
                print(f"Kullanıcı {command_user.name} için kayıtlı sohbet verisi (active_chats_data) temizlendi.")
                helpers.log_interaction(command_user.id, command_user.name, "Sistem", "Kullanıcının kayıtlı sohbet verisi temizlendi.", log_to_console=True)
            except KeyError: pass
            except Exception as e:
                print(f"HATA [UserCommandsCog]: Kullanıcı kayıtlı sohbet verisi temizlenirken hata: {e}")

        messages_to_delete_ids = set()
        fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
        deleted_message_count = 0

        try:
            async for msg in channel.history(limit=300):
                if msg.created_at <= fourteen_days_ago:
                    continue
                is_user_message = msg.author.id == command_user.id
                is_bot_reply_to_user = (
                    msg.author.id == self.bot.user.id and
                    msg.reference and msg.reference.resolved and
                    isinstance(msg.reference.resolved, discord.Message) and
                    msg.reference.resolved.author.id == command_user.id
                )
                is_bot_follow_up = False
                if msg.author.id == self.bot.user.id:
                    for original_id, follow_ids in self.bot.split_message_map.items():
                        if msg.id in follow_ids:
                            try:
                                original_reply = await channel.fetch_message(original_id)
                                if original_reply.reference and original_reply.reference.resolved and \
                                   original_reply.reference.resolved.author.id == command_user.id:
                                    is_bot_follow_up = True
                                    break
                            except: pass
                if is_user_message or is_bot_reply_to_user or is_bot_follow_up:
                    messages_to_delete_ids.add(msg.id)

            keys_to_pop_from_split_map = []
            for original_msg_id, follow_up_ids_list in self.bot.split_message_map.items():
                try:
                    if original_msg_id in messages_to_delete_ids:
                         messages_to_delete_ids.update(follow_up_ids_list)
                         keys_to_pop_from_split_map.append(original_msg_id)
                except Exception as e_split_map:
                    print(f"HATA [UserCommandsCog]: !temizle split_message_map işlenirken: {e_split_map}")

            for key_to_pop in keys_to_pop_from_split_map:
                self.bot.split_message_map.pop(key_to_pop, None)

            final_messages_to_delete_objs = []
            for msg_id in messages_to_delete_ids:
                try:
                    msg_obj = await channel.fetch_message(msg_id)
                    if msg_obj.created_at > fourteen_days_ago:
                        final_messages_to_delete_objs.append(msg_obj)
                except discord.NotFound: continue
                except discord.Forbidden:
                    print(f"HATA [UserCommandsCog]: !temizle - Mesaj ({msg_id}) fetch edilemedi (izin yok).")
                    continue
                except Exception as e_fetch:
                    print(f"HATA [UserCommandsCog]: !temizle - Mesaj ({msg_id}) fetch edilirken: {e_fetch}")
                    continue

            if ctx.message.created_at > fourteen_days_ago:
                if ctx.message not in final_messages_to_delete_objs:
                    final_messages_to_delete_objs.append(ctx.message)
            else:
                try: await ctx.message.delete()
                except: pass

            if not final_messages_to_delete_objs:
                result_message = f"{command_user.mention}, son 14 gün içinde sana ait veya sana yanıt olarak gönderilmiş silinebilecek mesaj bulunamadı."
                if data_cleaned_from_persistence:
                    result_message += " Ancak sohbet geçmişin hafızamdan temizlendi."
                await channel.send(result_message, delete_after=7)
                print("!temizle: Silinecek geçerli mesaj bulunamadı.")
                try: await feedback_msg.delete()
                except: pass
                return

            chunk_size = 100
            for i in range(0, len(final_messages_to_delete_objs), chunk_size):
                chunk = final_messages_to_delete_objs[i:i + chunk_size]
                if not chunk: continue
                try:
                    if len(chunk) == 1:
                        await chunk[0].delete()
                    else:
                        await channel.delete_messages(chunk)
                    deleted_message_count += len(chunk)
                    if len(final_messages_to_delete_objs) > chunk_size and (i + chunk_size) < len(final_messages_to_delete_objs):
                        await asyncio.sleep(1.1)
                except discord.Forbidden:
                    await channel.send(f"{command_user.mention}, mesajları silme iznim yok veya işlem sırasında sorun oluştu.", delete_after=7)
                    break
                except discord.HTTPException as e_http:
                    if e_http.status != 404:
                        await channel.send(f"{command_user.mention}, bazı mesajlar silinirken bir sorun oluştu (Hata Kodu: {e_http.status}).", delete_after=7)
                except Exception as e_del_chunk:
                    await channel.send(f"{command_user.mention}, mesajlar silinirken beklenmedik bir hata oluştu.", delete_after=7)
                    print(f"HATA [UserCommandsCog]: !temizle chunk silme hatası: {e_del_chunk}")
                    break

            actual_deleted_user_bot_messages = deleted_message_count - (1 if ctx.message in final_messages_to_delete_objs and ctx.message.created_at > fourteen_days_ago else 0)
            if actual_deleted_user_bot_messages >= 0:
                final_feedback_text = f"{command_user.mention}, seninle olan sohbetimizde {actual_deleted_user_bot_messages} mesaj başarıyla silindi."
            else:
                final_feedback_text = f"{command_user.mention}, temizleme işlemi tamamlandı."

            if data_cleaned_from_persistence:
                final_feedback_text += " Sohbet geçmişin de hafızamdan temizlendi."
            else:
                final_feedback_text += " Ancak temizlenecek bir sohbet geçmişi hafızamda bulunamadı."

            await channel.send(final_feedback_text, delete_after=7)
            print(f"!temizle işlemi tamamlandı. {actual_deleted_user_bot_messages} mesaj silindi.")
            helpers.log_interaction(command_user.id, command_user.name, "Sistem", f"{config.COMMAND_PREFIX}temizle komutu ile {actual_deleted_user_bot_messages} mesaj silindi ve hafıza temizlendi.", log_to_console=True)

        except discord.Forbidden as e_forbidden_history:
            await channel.send(f"{command_user.mention}, mesaj geçmişini okuma iznim yok.", delete_after=7)
            print(f"HATA [UserCommandsCog]: !temizle - Mesaj geçmişini okuma izni yok: {e_forbidden_history}")
        except Exception as e_general:
            await channel.send(f"{command_user.mention}, mesajlar temizlenirken beklenmedik bir hata oluştu.", delete_after=7)
            print(f"HATA [UserCommandsCog]: !temizle genel hata: {e_general}")
        finally:
            try: await feedback_msg.delete()
            except: pass


async def setup(bot: commands.Bot):
    await bot.add_cog(UserCommandsCog(bot))
    # print(f"'{UserCommandsCog.__name__}' yüklendi.") Log kalabalığını önlemek için kapatıldı.