# utils/helpers.py
# Bu dosya, botun farklı modülleri (Cog'lar) tarafından kullanılabilecek
# genel yardımcı fonksiyonları içerir.

import discord
from discord.ext import commands
import os
import logging # logging seviyeleri için
import asyncio
from datetime import timedelta, datetime, timezone # apply_timeout için datetime

# config ve constants modüllerini import etmemiz gerekecek
import config
import constants # BOT_ADI için eklendi

# PDF oluşturma için fpdf2
try:
    from fpdf import FPDF
    FPDF_FONT_AVAILABLE = os.path.exists(constants.DEJAVU_FONT_PATH) and os.path.exists(constants.DEJAVU_FONT_PATH_BOLD)
except ImportError:
    FPDF = None # fpdf2 yüklü değilse PDF oluşturma devre dışı kalır
    FPDF_FONT_AVAILABLE = False
    print("UYARI [helpers.py]: 'fpdf2' kütüphanesi bulunamadı. PDF kaydetme özelliği çalışmayacak.")


# --- Loglama Fonksiyonları ---
user_loggers = {} # Bu modül içinde logger'ları tutalım
# Ana konsol logger'ını al (resonai.py'de yapılandırılan)
main_logger = logging.getLogger() # Kök logger'ı al

def setup_user_logger(user_id: int, user_name: str, is_dm_log: bool = False): # is_dm_log parametresi eklendi
    """Belirtilen kullanıcı için loglama nesnesini ayarlar veya döndürür."""
    log_type_prefix = "dm_" if is_dm_log else "user_"
    logger_name = f"{log_type_prefix}{user_id}" # Logger isimlerinin çakışmaması için prefix ekleyelim

    if logger_name in user_loggers:
        return user_loggers[logger_name]

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False # Mesajların ana logger'a (konsola) gitmesini engelle

    if not logger.handlers:
        safe_user_name = "".join(c for c in user_name if c.isalnum() or c in (' ', '_')).rstrip()
        
        # Log dizinini belirle
        log_directory = constants.DM_LOGS_DIRECTORY if is_dm_log else constants.LOGS_DIRECTORY
        log_file_path = os.path.join(log_directory, f"{user_id}_{safe_user_name}.log")

        if not os.path.exists(log_directory):
            try:
                os.makedirs(log_directory)
                print(f"Bilgi [helpers.py]: Log dizini oluşturuldu: {log_directory}")
            except OSError as e:
                print(f"HATA [helpers.py]: Log dizini ({log_directory}) oluşturulamadı: {e}")
                return None
        try:
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            user_loggers[logger_name] = logger
        except Exception as e:
            print(f"HATA [helpers.py]: Kullanıcı ({user_id}) için {'DM' if is_dm_log else 'kanal'} logger handler eklenirken hata: {e}")
            return None
    return logger

def log_interaction(user_id: int, user_name: str, author_type: str, text: str, attachments: list = None,
                    log_to_console: bool = True, console_level=logging.INFO, console_message_override: str = None,
                    is_dm_log: bool = False): # is_dm_log parametresi eklendi
    """
    Kullanıcı etkileşimlerini ilgili kullanıcının log dosyasına ve isteğe bağlı olarak ana konsola kaydeder.
    is_dm_log True ise DM log klasörüne yazar.
    """
    # 1. Kullanıcı/DM Log Dosyasına Yazma
    # DM logları için user_id, DM'in diğer tarafındaki kullanıcı olmalı.
    # Eğer author_type "Bot" ise ve DM logu ise, user_id DM'in alıcısıdır.
    # Eğer author_type "Kullanıcı" ise ve DM logu ise, user_id DM'i gönderendir.
    target_user_id_for_dm_log = user_id # Varsayılan
    target_user_name_for_dm_log = user_name

    # Eğer bot DM gönderiyorsa, log dosyasının adı alıcının ID'siyle olmalı.
    # Bu, log_interaction çağrılırken user_id ve user_name'in doğru verilmesini gerektirir.
    # Örneğin, bot kullanıcıya DM atıyorsa, user_id=kullanıcının_id'si, user_name=kullanıcının_adı olmalı.

    user_file_logger = setup_user_logger(target_user_id_for_dm_log, target_user_name_for_dm_log, is_dm_log=is_dm_log)

    if user_file_logger:
        log_entry_user_file = f"[{author_type.upper()}] {text}"
        if attachments:
            safe_filenames = [att.filename.replace('\n', '_').replace('\r', '_') for att in attachments]
            attachments_info = f" [{len(attachments)} ek dosya: {', '.join(safe_filenames)}]"
            log_entry_user_file += attachments_info
        try:
            user_file_logger.info(log_entry_user_file)
        except Exception as e:
            log_type_str = "DM" if is_dm_log else "Kanal"
            print(f"HATA [helpers.py]: Kullanıcı {log_type_str} log dosyasına yazılırken hata (User ID: {target_user_id_for_dm_log}): {e}")
    else:
        log_type_str = "DM" if is_dm_log else "Kanal"
        print(f"UYARI [helpers.py]: Kullanıcı {target_user_name_for_dm_log} (ID: {target_user_id_for_dm_log}) için {log_type_str} logger alınamadı. Log yazılamadı.")

    # 2. Ana Konsol Loguna Yazma (İsteğe Bağlı ve DM logları için genellikle False olacak)
    if log_to_console:
        log_entry_console = ""
        if console_message_override:
            log_entry_console = console_message_override
        elif author_type.upper() == "BOT" and not is_dm_log: # DM'deki bot yanıtları konsola yazılmasın (çok fazla olabilir)
            log_entry_console = f"Bot yanıtı gönderildi -> Kullanıcı: {user_name} (ID: {user_id})"
        elif author_type.upper() == "BOT" and is_dm_log:
            # Botun DM yanıtlarını konsola yazmayalım, sadece kullanıcı DM loguna gitsin.
            # Bu blok boş kalabilir veya log_to_console False yapılır. Şimdilik böyle bırakalım.
            pass
        else: # Kullanıcı, Sistem vb.
            log_entry_console = f"[{author_type.upper()}] ({user_name}|{user_id}) {text}"
            if attachments:
                 log_entry_console += f" [{len(attachments)} ek dosya]"
        
        if log_entry_console: # Boş değilse logla
            try:
                main_logger.log(console_level, log_entry_console)
            except Exception as e:
                 print(f"HATA [helpers.py]: Ana konsol loguna yazılırken hata: {e}")

# --- Yetki Kontrol Fonksiyonu ---
def is_admin(member: discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    if not config.ADMIN_ROLE_IDS:
        return False
    return any(role.id in config.ADMIN_ROLE_IDS for role in member.roles)

# --- Timeout Uygulama Fonksiyonu ---
async def apply_timeout(bot: commands.Bot, member: discord.Member, duration_minutes: int, reason: str, channel: discord.TextChannel):
    if not isinstance(member, discord.Member):
        print(f"Timeout uygulanamadı: {member} bir sunucu üyesi değil.")
        return
    if member.is_timed_out():
        return

    if is_admin(member) or member.id == bot.user.id:
        print(f"Yönetici veya bot timeoutlanamaz: {member.display_name}")
        return

    try:
        duration = timedelta(minutes=duration_minutes)
        await member.timeout(duration, reason=reason)
        timeout_log_msg = f"{duration_minutes} dakika timeout uygulandı. Sebep: {reason}"
        console_log_msg = f"Kullanıcı {member.display_name} (ID: {member.id}) {duration_minutes}dk timeoutlandı. Sebep: {reason}"
        print(console_log_msg)
        log_interaction(member.id, member.name, "Sistem", timeout_log_msg, log_to_console=True, console_message_override=console_log_msg)
        if channel:
            await channel.send(f"{member.mention}, tekrarlanan '{reason}' nedeniyle {duration_minutes} dakika süreyle susturuldunuz.", delete_after=15)
    except discord.Forbidden:
        error_msg = f"Timeout uygulanamadı (izin yok). Sebep: {reason}"
        console_error_msg = f"HATA [helpers.py]: {member.display_name} kullanıcısına timeout uygulama izni yok."
        print(console_error_msg)
        log_interaction(member.id, member.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR, console_message_override=console_error_msg)
        if channel:
            await channel.send(f"'{member.display_name}' kullanıcısına timeout uygulanamadı (izin eksik).", delete_after=6)
    except discord.HTTPException as e:
        error_msg = f"Timeout uygulanırken HTTP hatası: {e}. Sebep: {reason}"
        console_error_msg = f"HATA [helpers.py]: Timeout uygulanırken HTTP hatası ({member.display_name}): {e}"
        print(console_error_msg)
        log_interaction(member.id, member.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR, console_message_override=console_error_msg)
    except Exception as e:
        error_msg = f"Timeout uygulanırken beklenmedik hata: {e}. Sebep: {reason}"
        console_error_msg = f"HATA [helpers.py]: Timeout uygulanırken beklenmedik hata ({member.display_name}): {e}"
        print(console_error_msg)
        log_interaction(member.id, member.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR, console_message_override=console_error_msg)


# --- Embed Oluşturma ve Gönderme Fonksiyonları ---
def create_channel_embed(bot: commands.Bot):
    bot_avatar_url = bot.user.display_avatar.url if bot.user else None
    description = constants.EMBED_DESCRIPTION_TEMPLATE.format(
        COMMAND_PREFIX=config.COMMAND_PREFIX,
        CHAT_INACTIVITY_THRESHOLD_MINUTES=constants.CHAT_INACTIVITY_THRESHOLD_MINUTES
    )
    field_yetenekler_value = constants.EMBED_FIELD_YETENEKLER_VALUE_TEMPLATE.format(
        COMMAND_PREFIX=config.COMMAND_PREFIX
    )
    field_kurallar_value = constants.EMBED_FIELD_KURALLAR_VALUE_TEMPLATE.format(
        CHAT_INACTIVITY_THRESHOLD_MINUTES=constants.CHAT_INACTIVITY_THRESHOLD_MINUTES
    )
    field_komutlar_value = constants.EMBED_FIELD_KOMUTLAR_VALUE_TEMPLATE.format(
        COMMAND_PREFIX=config.COMMAND_PREFIX
    )

    embed = discord.Embed(
        title=constants.EMBED_TITLE, # constants.py'de BOT_ADI kullanıyor
        description=description,
        color=discord.Color.blue()
    )
    if bot_avatar_url:
        embed.set_thumbnail(url=bot_avatar_url)

    embed.add_field(name=constants.EMBED_FIELD_YETENEKLER_NAME, value=field_yetenekler_value, inline=False)
    embed.add_field(name=constants.EMBED_FIELD_KURALLAR_NAME, value=field_kurallar_value, inline=False)
    embed.add_field(name=constants.EMBED_FIELD_KOMUTLAR_NAME, value=field_komutlar_value, inline=False)
    embed.set_footer(text=constants.EMBED_FOOTER_TEXT) # constants.py'de BOT_ADI kullanıyor
    return embed

async def send_and_pin_embed(bot: commands.Bot, channel: discord.TextChannel):
    try:
        old_pinned_id = bot.pinned_embed_message_id.get(channel.id)
        if old_pinned_id:
            try:
                old_msg = await channel.fetch_message(old_pinned_id)
                if old_msg:
                    if old_msg.pinned:
                        await old_msg.unpin(reason="Yeni açıklama mesajı sabitleniyor.")
                        print(f"Eski açıklama mesajının ({old_pinned_id}) sabitlemesi kaldırıldı: #{channel.name}")
                    await old_msg.delete()
                    print(f"Eski açıklama mesajı ({old_pinned_id}) silindi: #{channel.name}")
            except discord.NotFound:
                print(f"Eski sabitlenmiş mesaj bulunamadı (ID: {old_pinned_id}): #{channel.name}")
            except discord.Forbidden:
                print(f"Eski sabitlenmiş mesaj silinemedi/sabitlemesi kaldırılamadı (izin yok): #{channel.name}")
            except Exception as e:
                print(f"Eski sabitlenmiş mesaj işlenirken hata ({old_pinned_id}): {e}")
            finally:
                bot.pinned_embed_message_id.pop(channel.id, None)

        channel_embed_obj = create_channel_embed(bot)
        new_msg = await channel.send(embed=channel_embed_obj)
        print(f"Kanal açıklama embed'i gönderildi: #{channel.name}")

        await new_msg.pin(reason="Kanal açıklama mesajı.")
        bot.pinned_embed_message_id[channel.id] = new_msg.id
        print(f"Yeni açıklama mesajı sabitlendi (ID: {new_msg.id}): #{channel.name}")
        log_interaction(bot.user.id, bot.user.name, "Sistem", f"Açıklama mesajı gönderildi ve sabitlendi (ID: {new_msg.id}) Kanal: #{channel.name}", log_to_console=True)

    except discord.Forbidden:
        error_msg = f"'{channel.name}' kanalına mesaj gönderme veya sabitleme/silme izni yok."
        print(f"HATA [helpers.py]: {error_msg}")
        log_interaction(bot.user.id, bot.user.name, "Sistem", error_msg, log_to_console=False)
    except discord.HTTPException as e:
        error_msg = f"Embed gönderilirken/sabitlenirken/silinirken HTTP hatası ({channel.name}): {e}"
        print(f"HATA [helpers.py]: {error_msg}")
        log_interaction(bot.user.id, bot.user.name, "Sistem", error_msg, log_to_console=False)
    except Exception as e:
        error_msg = f"Embed gönderilirken/sabitlenirken/silinirken beklenmedik hata ({channel.name}): {e}"
        print(f"HATA [helpers.py]: {error_msg}")
        log_interaction(bot.user.id, bot.user.name, "Sistem", error_msg, log_to_console=False)

# --- Uzun Mesaj Bölme Fonksiyonu ---
async def send_long_message(bot: commands.Bot, target, text: str, chunk_size: int = 1950):
    if not text:
        return []
    sent_messages = []
    remaining_text = text.strip()
    original_message: discord.Message = target if isinstance(target, discord.Message) else None
    first_reply_id = None
    while remaining_text:
        chunk = ""
        if len(remaining_text) <= chunk_size:
            chunk = remaining_text
            remaining_text = ""
        else:
            split_at = -1
            possible_split = remaining_text.rfind('\n\n', 0, chunk_size)
            if possible_split != -1:
                split_at = possible_split + 2
            else:
                possible_split = remaining_text.rfind('\n', 0, chunk_size)
                if possible_split != -1:
                    split_at = possible_split + 1
                else:
                    search_area_start = max(0, chunk_size - 200)
                    for delimiter in ['. ', '! ', '? ']:
                        possible_split = remaining_text.rfind(delimiter, search_area_start, chunk_size)
                        if possible_split != -1:
                            split_at = max(split_at, possible_split + len(delimiter))
                    if split_at == -1:
                         for delimiter_char in ['.', '!', '?']:
                            possible_split = remaining_text.rfind(delimiter_char, search_area_start, chunk_size)
                            if possible_split != -1:
                                split_at = max(split_at, possible_split + 1)
                    if split_at == -1:
                        possible_split = remaining_text.rfind(' ', 0, chunk_size)
                        if possible_split != -1:
                            split_at = possible_split + 1
                        else:
                            split_at = chunk_size
            chunk = remaining_text[:split_at]
            remaining_text = remaining_text[split_at:].lstrip()
        if chunk.strip():
            sent_msg = None
            try:
                if original_message and not first_reply_id:
                    sent_msg = await original_message.reply(chunk)
                    first_reply_id = sent_msg.id
                elif isinstance(target, (discord.TextChannel, discord.Thread, discord.User, discord.Member)):
                    sent_msg = await target.send(chunk)
                elif original_message:
                    sent_msg = await original_message.channel.send(chunk)
                else:
                    print(f"HATA [helpers.py]: send_long_message için geçersiz hedef tipi: {type(target)}")
                    break
                if sent_msg:
                    sent_messages.append(sent_msg)
                if remaining_text:
                    await asyncio.sleep(0.6)
            except discord.HTTPException as e:
                error_msg = f"Mesaj parçası gönderilemedi (HTTP {e.status}): {e.text}"
                print(f"HATA [helpers.py]: {error_msg}")
                log_interaction(bot.user.id, bot.user.name, "Sistem", error_msg, log_to_console=False)
                break
            except Exception as e:
                error_msg = f"Mesaj parçası gönderilirken beklenmedik hata: {e}"
                print(f"HATA [helpers.py]: {error_msg}")
                log_interaction(bot.user.id, bot.user.name, "Sistem", error_msg, log_to_console=False)
                break
    if first_reply_id and len(sent_messages) > 1:
        follow_up_ids = [msg.id for msg in sent_messages[1:]]
        bot.split_message_map[first_reply_id] = follow_up_ids
    return sent_messages


# --- PDF Oluşturma Fonksiyonu ---
async def generate_and_send_pdf_transcript(bot: commands.Bot, message: discord.Message, conversation_history: list):
    command_user = message.author
    channel = message.channel
    feedback_msg = None
    pdf_file_path = f"temp_transcript_{channel.id}_{command_user.id}_{constants.BOT_ADI.lower()}.pdf"

    if not FPDF:
        await channel.send(f"{command_user.mention}, PDF oluşturma kütüphanesi sunucuda yüklü olmadığı için bu işlem yapılamıyor.", delete_after=10)
        return

    try:
        feedback_msg = await channel.send(f"{command_user.mention}, sohbet geçmişiniz taranıyor ve PDF oluşturuluyor...", delete_after=5)

        if not conversation_history:
            await channel.send(f"{command_user.mention}, sizinle ilgili kaydedilecek bir sohbet geçmişi bulunamadı.", delete_after=5)
            if feedback_msg: await feedback_msg.delete()
            return

        pdf = FPDF()
        pdf.add_page()

        if FPDF_FONT_AVAILABLE:
            try:
                pdf.add_font('DejaVu', '', constants.DEJAVU_FONT_PATH)
                pdf.add_font('DejaVu', 'B', constants.DEJAVU_FONT_PATH_BOLD)
                pdf.set_font('DejaVu', '', 10)
            except Exception as font_error:
                print(f"HATA [helpers.py]: DejaVu fontu eklenirken hata: {font_error}. Standart font kullanılacak.")
                pdf.set_font("Arial", size=10)
        else:
            pdf.set_font("Arial", size=10)

        safe_user_name_pdf = "".join(c for c in command_user.name if c.isalnum() or c in (' ', '_')).rstrip()
        safe_title = f"{constants.BOT_ADI} Sohbet Ozeti: {safe_user_name_pdf}"
        pdf.set_font(pdf.font_family, 'B', 14)
        try: pdf.cell(0, 10, safe_title, ln=1, align='C')
        except UnicodeEncodeError: pdf.cell(0, 10, safe_title.encode('latin-1', 'replace').decode('latin-1'), ln=1, align='C')

        pdf.set_font(pdf.font_family, '', 10)
        safe_channel_name = f"Kanal: {channel.name}"
        try: pdf.cell(0, 6, safe_channel_name, ln=1)
        except UnicodeEncodeError: pdf.cell(0, 6, safe_channel_name.encode('latin-1', 'replace').decode('latin-1'), ln=1)
        pdf.cell(0, 6, f"Tarih: {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}", ln=1)
        pdf.ln(10)

        for entry in conversation_history:
            pdf.set_font(pdf.font_family, 'B', 10)
            try:
                author_line = f"[{entry['timestamp']}] {entry['author']}:"
                pdf.write(5, author_line + "\n")
            except UnicodeEncodeError:
                pdf.write(5, author_line.encode('latin-1', 'replace').decode('latin-1') + "\n")
            except Exception as write_error:
                print(f"PDF yazar adı yazma hatası: {write_error}")
                pdf.write(5, "[HATA: Yazar Adı Yazılamadı]\n")

            pdf.set_font(pdf.font_family, '', 10)
            try:
                content_line = entry['content']
                pdf.multi_cell(0, 5, content_line)
            except UnicodeEncodeError:
                pdf.multi_cell(0, 5, content_line.encode('latin-1', 'replace').decode('latin-1'))
            except Exception as write_error:
                 print(f"PDF içerik yazma hatası: {write_error}")
                 pdf.multi_cell(0, 5, "[HATA: Mesaj İçeriği Yazılamadı]")
            pdf.ln(3)

        pdf.output(pdf_file_path)
        discord_file = discord.File(pdf_file_path, filename=f"sohbet_ozeti_{constants.BOT_ADI.lower()}_{safe_user_name_pdf}.pdf")
        dm_sent = False
        try:
            await command_user.send(f"Merhaba {command_user.mention}, '{channel.name}' kanalındaki sohbetimizin özeti ektedir:", file=discord_file)
            dm_sent = True
            log_interaction(command_user.id, command_user.name, "Sistem", "Sohbet özeti PDF olarak DM ile gönderildi.", log_to_console=True, is_dm_log=True) # is_dm_log eklendi
        except discord.Forbidden:
            await channel.send(f"{command_user.mention}, DM'leriniz kapalı olduğu için PDF özetini gönderemedim.", delete_after=7)
            log_interaction(command_user.id, command_user.name, "Sistem", "Sohbet özeti PDF gönderilemedi (DM kapalı).", log_to_console=True, console_level=logging.WARNING)
        except discord.HTTPException as e:
            await channel.send(f"{command_user.mention}, PDF gönderirken bir sorun oluştu (Hata: {e.status}).", delete_after=7)
            log_interaction(command_user.id, command_user.name, "Sistem", f"Sohbet özeti PDF gönderme hatası (HTTP {e.status}).", log_to_console=True, console_level=logging.ERROR)

        if dm_sent:
            await channel.send(f"{command_user.mention}, sohbet özeti PDF olarak özel mesaj (DM) ile gönderildi.", delete_after=5)
            try: await message.delete()
            except: pass

    except Exception as e:
        error_msg = f"PDF oluşturma/gönderme sırasında genel hata: {e}"
        print(f"HATA [helpers.py]: {error_msg}")
        log_interaction(command_user.id, command_user.name, "Sistem", error_msg, log_to_console=True, console_level=logging.ERROR)
        await channel.send(f"{command_user.mention}, PDF özeti oluşturulurken/gönderilirken beklenmedik bir hata oluştu.", delete_after=7)
    finally:
        if os.path.exists(pdf_file_path):
            try: os.remove(pdf_file_path)
            except OSError as e_remove: print(f"HATA [helpers.py]: Geçici PDF dosyası silinemedi: {e_remove}")
        if feedback_msg:
            try: await feedback_msg.delete()
            except: pass

print("utils/helpers.py yüklendi.")
