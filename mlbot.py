import asyncio,psutil,os
import re,random,time,hashlib,uuid,json
from datetime import datetime, timedelta
from sys import stderr, stdout
from threading import Timer

from pyrogram import Client
from pyrogram.enums import MessageMediaType,ChatType,ParseMode
from pyrogram.errors import FileReferenceExpired,FloodWait,AuthBytesInvalid
from pyrogram.types import InputMediaPhoto, InputMediaVideo, InputMediaAudio, InputMediaDocument, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ReplyParameters
from pyrogram.client import Cache
from pyrogram import filters
import mysql.connector
from mysql.connector import pooling
import uvloop
import math

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
uvloop.install()

api_id = 00000000
api_hash = "00000000000000000000000000000"
bot_token = "000000000:000000000000000000000000000"
admin = 112233333
app = Client("mlkauto", api_id=api_id, api_hash=api_hash,bot_token=bot_token, max_concurrent_transmissions = 1, sleep_threshold = 60)

app.message_cache = Cache(1000000)
dl_types = [MessageMediaType.PHOTO, MessageMediaType.VIDEO, MessageMediaType.AUDIO, MessageMediaType.DOCUMENT]
use_record = {}

dbconfig = {
    "host": "127.0.0.1",
    "user": "mlkauto",
    "password": "mlkauto",
    "database": "mlbot"
}

connection_pool = pooling.MySQLConnectionPool(pool_name="mypool",pool_size=5,**dbconfig)

processed_media_groups = {}
expiration_time = 1800
decode_users = {}
join_users = {}

ret_task_count = 0
stor_task_count = 0
stor_sem = asyncio.Semaphore(2)
ret_sem = asyncio.Semaphore(2)

# Function to periodically clean up expired entries
def cleanup_processed_media_groups():
    current_time = time.time()
    expired_keys = [key for key, timestamp in processed_media_groups.items() if current_time - timestamp > expiration_time]
    for key in expired_keys:
        del processed_media_groups[key]

# Function to clean expired join_users
def clean_expired_join_users():
    current_time = time.time()
    expired_keys = [key for key, timestamp in join_users.items() if current_time - timestamp > 900]
    for key in expired_keys:
        del join_users[key]

def decode_rate_con(uid, p = 0):
    if not uid in decode_users:
        decode_users[uid] = time.time()
    if p > 0:
        decode_users[uid] = decode_users[uid] + p
        return
    expired_keys = [key for key, timestamp in decode_users.items() if time.time() - timestamp > 180]
    for key in expired_keys:
        del decode_users[key]
    if (uid in decode_users):
        if(time.time() - decode_users[uid] < 0):
            return (decode_users[uid] - time.time())
    cooldown_time = max(8, 8 + 1.33 * min(4,ret_task_count) )
    decode_users[uid] = time.time() + cooldown_time
    return 0

def write_rec(mlk, mkey, skey, owner, desta, file_ids, mgroup_id = ""):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'INSERT INTO records (mlk, mkey, skey, owner, mgroup_id, desta, file_ids ) VALUES (%s, %s, %s, %s, %s, %s, %s)'
        cursor.execute(sql, (mlk, mkey, skey, owner, mgroup_id, desta, file_ids))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    
def write_rec_fileids(file_ids, mlk):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET file_ids = %s WHERE mlk = %s'
        cursor.execute(sql, (file_ids, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()   

def read_rec(mlk):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM records WHERE mlk = %s'
        cursor.execute(sql, (mlk,))
        result = cursor.fetchone()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    if result and len(result) > 0:
        sql = 'UPDATE records SET views = views + 1 WHERE mlk = %s'
        cursor.execute(sql, (mlk,))
        conn.commit()
        cursor.close()
        conn.close()
        return result
    else:
        cursor.close()
        conn.close()
        return False

def read_null_fileids():
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM records WHERE file_ids is NULL'
        cursor.execute(sql)
        result = cursor.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
        return result

def rotate_mkey(mlk):
    try:
        conn = connection_pool.get_connection()
        mkey = str(uuid.uuid4()).split("-")[-1][0:8]
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET mkey = %s WHERE mlk = %s'
        cursor.execute(sql, (mkey, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
        return mkey

def rotate_skey(mlk):
    try:
        conn = connection_pool.get_connection()
        skey = str(uuid.uuid4()).split("-")[-1][0:8]
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET skey = %s WHERE mlk = %s'
        cursor.execute(sql, (skey, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

def set_name(mlk, name):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET name = %s WHERE mlk = %s'
        cursor.execute(sql, (name, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

def search_names(owner, name):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM records WHERE owner = %s AND name like %s ORDER BY ID DESC LIMIT 12'
        cursor.execute(sql, (owner, '%' + name + '%'))
        result = cursor.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    if result and len(result) > 0:
        return result
    else:
        return False

def set_packid(mlkset, packid):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET pack_id = %s WHERE mlk = %s'
        for mlk in mlkset:
            cursor.execute(sql, (packid, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

def read_pack(packid):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM records WHERE pack_id = %s'
        cursor.execute(sql, (packid,))
        result = cursor.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    if result and len(result) > 0:
        return result
    else:
        return False

def top_views(owner):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM records WHERE owner = %s ORDER BY views DESC LIMIT 5'
        cursor.execute(sql, (owner,))
        result = cursor.fetchall()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()
    if result and len(result) > 0:
        return result
    else:
        return False

def set_expire(mlk, exp_time):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'UPDATE records SET exp = %s WHERE mlk = %s'
        cursor.execute(sql, (exp_time, mlk))
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

def write_joins(uid, files):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM join_list WHERE uid = %s'
        cursor.execute(sql, (uid, ))
        result = cursor.fetchone()
        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    if result:
        if time.time() - result["create_time"].timestamp() <= 900:
            files = json.loads(result["file_ids"]) + files
            create_time = result["create_time"]
        else:
            create_time = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
        if len(files) > 60:
            files = files[0:60]
        try:
            sql = 'UPDATE join_list SET file_ids = %s, create_time = %s WHERE uid = %s'
            cursor.execute(sql, (json.dumps(files), create_time, uid))
            conn.commit()
        except Exception as e:
            print(f"Error: {e}")
    else:
        try:
            sql = 'INSERT INTO join_list (uid, file_ids, create_time) VALUES (%s, %s, %s)'
            cursor.execute(sql, (uid, json.dumps(files), datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")))
            conn.commit()
        except Exception as e:
            print(f"Error: {e}")
    cursor.close()
    conn.close()
    return len(files)

def read_joins(uid, delete = False):
    try:
        conn = connection_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        sql = 'SELECT * FROM join_list WHERE uid = %s'
        cursor.execute(sql, (uid,))
        result = cursor.fetchone()
        conn.commit()
        if delete:
            sql = 'DELETE FROM join_list WHERE uid = %s'
            cursor.execute(sql, (uid,))
            conn.commit()
    except Exception as e:
        print(f"Error: {e}")
    cursor.close()
    conn.close()
    if result and len(result) > 0:
        return json.loads(result["file_ids"])
    else:
        return False

def mediatotype(obj):
    if obj == MessageMediaType.PHOTO:
        return "photo"
    if obj == MessageMediaType.VIDEO:
        return "video"
    if obj == MessageMediaType.AUDIO:
        return "audio"
    if obj == MessageMediaType.DOCUMENT:
        return "document"
    return False

def size_to_str(size):
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
    
def duration_to_str(duration):
    if duration < 60:
        return f"{round(duration,1)}秒"
    elif duration < 3600:
        return f"{duration / 60:.2f}分钟"
    else:
        return f"{duration / 3600:.2f}小时"

async def media_to_link(mlk, mkey, skey, chat_id, msg_id, owner, mgroup_id, stor_sem, retry = 0):
    async with stor_sem:
        global stor_task_count
        files = await read_media([msg_id], chat_id)
        pcount = 0
        vcount = 0
        dcount = 0
        acount = 0
        dura = 0
        size = 0
        summary = ""
        for file in files:
            if (file["type"] == "photo"):
                pcount += 1
            if (file["type"] == "video"):
                vcount += 1
                dura += file["duration"]
            if (file["type"] == "document"):
                dcount += 1
            if (file["type"] == "audio"):
                acount += 1
            size += file["size"]
        summary += str(pcount)+"p" if pcount > 0 else ""
        summary += str(vcount)+"v" if vcount > 0 else ""
        summary += str(dcount)+"d" if dcount > 0 else ""
        summary += str(acount)+"a" if acount > 0 else " "
        summary += duration_to_str(dura)+" " if dura > 0 else " "
        summary += size_to_str(size) if size > 0 else ""
        write_rec(mlk, mkey, skey, owner, 0, json.dumps(files), mgroup_id)
        keyout = '<b>主分享KEY点击复制</b>: `https://t.me/mlkautobot?start=' + mlk + '-' + mkey + '  ' + summary + "`" + '\n<b>一次性KEY点击复制</b>: `https://t.me/mlkautobot?start=' + mlk + '-' + skey + '`' + '\n\n主分享KEY可重复使用，一次性KEY在获取一次后会失效，如果你是资源上传者，可以向机器人发送主分享KEY来获取最新可用的一次性KEY\n\n🔽链接默认*不过期*，如需限时有效下方可设置'
        acts = InlineKeyboardMarkup([[
            InlineKeyboardButton("1H过期", callback_data=mlk + "?exp=1H"),
            InlineKeyboardButton("3H过期", callback_data=mlk + "?exp=3H"),
            InlineKeyboardButton("24H过期", callback_data=mlk + "?exp=24H"),
            InlineKeyboardButton("不过期", callback_data=mlk + "?exp=NULL"),
        ]])
        try:
            await app.send_message(chat_id, text = keyout, reply_parameters = ReplyParameters(message_id = msg_id, chat_id = chat_id), reply_markup = acts)
        except Exception as e:
            print(e)
        finally:
            await asyncio.sleep(random.randint(10,35) / 10)
            stor_task_count -=1 if stor_task_count > 0 else 0

async def media_prep(chat_id, msg_id, owner, msg_dt, mgroup_id = ""):
    mlk = hashlib.sha3_256()
    prep_key = str(chat_id) + str(msg_id) + str(owner) + str(msg_dt) + str(uuid.uuid4())
    mlk.update(prep_key.encode())
    mlk = mlk.hexdigest()[0:48]
    mkey = str(uuid.uuid4()).split("-")[-1][0:8]
    skey = str(uuid.uuid4()).split("-")[-1][0:8]
    copy_task = []
    task = asyncio.create_task(media_to_link(mlk, mkey, skey, chat_id, msg_id, owner, mgroup_id, stor_sem))
    copy_task.append(task)
    global stor_task_count
    if stor_task_count >= 5:
        try:
            await app.send_message(chat_id, text =  "正在排队处理中，请稍等几秒，不要重复点击")
        except Exception as e:
            print(e)
    stor_task_count += 1
    await asyncio.gather(*copy_task)

async def link_to_media(chat_id, msg_id, data_set, mgroup_id, ret_sem):
    async with ret_sem:
        files = json.loads(data_set['file_ids'])
        reply_obj = ReplyParameters(message_id = msg_id, chat_id = chat_id)
        if len(files) == 0:
            return
        if (mgroup_id):
            file_list = []
            for file in files:
                if file["type"] == "photo":
                    file_list.append(InputMediaPhoto(file["file_id"]))
                if file["type"] == "video":
                    file_list.append(InputMediaVideo(file["file_id"], file["thumb"]))
                if file["type"] == "audio":
                    file_list.append(InputMediaAudio(file["file_id"]))
                if file["type"] == "document":
                    file_list.append(InputMediaDocument(file["file_id"]))
            try:
                #await app.copy_media_group(chat_id, from_chat_id = groups[0], message_id = desta, reply_to_message_id = msg_id)
                await app.send_media_group(chat_id, file_list, reply_parameters = reply_obj)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                #await app.copy_media_group(chat_id, from_chat_id = groups[0], message_id = desta, reply_to_message_id = msg_id)
            except Exception as e:
                print(e)
        else:
            file_list = files[0]
            try:
                #await app.copy_message(chat_id, from_chat_id = groups[0], message_id = desta)
                if file_list["type"] == "photo":
                    await app.send_photo(chat_id, file_list["file_id"], reply_parameters = reply_obj)
                if file_list["type"] == "video":
                    await app.send_video(chat_id, file_list["file_id"], reply_parameters = reply_obj, thumb = file_list["thumb"])
                if file_list["type"] == "audio":
                    await app.send_audio(chat_id, file_list["file_id"], reply_parameters = reply_obj)
                if file_list["type"] == "document":
                    await app.send_document(chat_id, file_list["file_id"], reply_parameters = reply_obj)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                #await app.copy_message(chat_id, from_chat_id = groups[0], message_id = desta)
            except Exception as e:
                print(e)
        await asyncio.sleep(1 + random.randint(28,35) / 10)
        global ret_task_count
        ret_task_count -= 1 if ret_task_count > 0 else 0

async def link_prep(chat_id, msg_id, from_id, result, join_op = 0):
    join_list = []
    global ret_task_count
    for m in result:
        mkey = m[0:48]
        rkey = m[49:65]
        data_set = read_rec(mkey)
        ret_task = []
        if data_set:
            if data_set['exp'] and time.time() > data_set['exp'].timestamp():
                try:
                    await app.send_message(chat_id, text = "资源已过期")
                except Exception:
                    pass
                return
            #desta = data_set['desta']
            mgroup_id = data_set['mgroup_id']
            if rkey == data_set["mkey"]:
                if join_op:
                    for ids in json.loads(data_set["file_ids"]):
                        join_list.append(ids)
                    continue
                #return media and current skey
                if data_set['pack_id']:
                    full_set = read_pack(data_set['pack_id'])
                    try:
                        await app.send_message(chat_id, text =  "该媒体属于文件夹 `" + data_set['pack_id'] + '` ，正在返回全部' + str(len(full_set)) + '组媒体\n\n文件夹取回操作优先级较低，请耐心等待')
                    except Exception:
                        return
                    pack_list = []
                    for set in full_set:
                        task = asyncio.create_task(link_to_media(chat_id, msg_id, set, set['mgroup_id'], ret_sem))
                        await asyncio.sleep(0.5 + 1.33 * ret_task_count + 1.5 * len(full_set))
                        ret_task_count += 1
                        ret_task.append(task)
                    await asyncio.gather(*ret_task)
                    return
                task = asyncio.create_task(link_to_media(chat_id, msg_id, data_set, mgroup_id, ret_sem))
                ret_task.append(task)
                if ret_task_count >= 5:
                    try:
                        await app.send_message(chat_id, text =  "正在排队处理中，请稍等几秒，不要重复点击")
                    except Exception:
                        return
                ret_task_count += 1
                await asyncio.gather(*ret_task)
                if from_id == data_set['owner']:
                    #return skey
                    skey_disp = '本资源当前一次性KEY: `https://t.me/mlkautobot?start=' + data_set['mlk'] + '-' + data_set['skey'] + '`'
                    try:
                        await app.send_message(chat_id, text = skey_disp, reply_parameters = ReplyParameters(message_id = msg_id, chat_id = chat_id))
                    except Exception:
                        return
                continue
            if rkey == data_set["skey"]:
                #return media and rotate skey
                rotate_skey(mkey)
                task = asyncio.create_task(link_to_media(chat_id, msg_id, data_set, mgroup_id, ret_sem))
                ret_task.append(task)
                if ret_task_count >= 5:
                    try:
                        await app.send_message(chat_id, text =  "正在排队处理中，请稍等几秒，不要重复点击")
                    except Exception:
                        return
                ret_task_count += 1
                await asyncio.gather(*ret_task)
                try:
                    await app.send_message(chat_id, text = "当前使用的是一次性KEY，该KEY已自动销毁，无法再用")
                except Exception:
                    return
                continue
            if rkey != data_set["mkey"] and rkey != data_set["skey"]:
                try:
                    await app.send_message(chat_id, text = "资源索引有效，但密钥不正确，一分钟后可以再试", reply_parameters = ReplyParameters(message_id = msg_id, chat_id = chat_id))
                except Exception:
                    return
            decode_rate_con(from_id, p = 48)
    return join_list

async def read_media(ids, chat_id = groups[0]):
    media_cl = []
    if not ids:
        return
    for i in ids:
        try:
            msg = await app.get_messages(chat_id, i)
        except FloodWait as e:
            print(e)
            await asyncio.sleep(e.value + 3)
        except Exception as e:
            print(e)
            await asyncio.sleep(1)
            msg = await app.get_messages(chat_id, i)
        #print(msg)
        if msg.media_group_id:
            msgs = await app.get_media_group(chat_id, i)
            for ix in msgs:
                type = mediatotype(ix.media)
                if type:
                    media_cl.append({"type": type, "file_id": getattr(ix, type).file_id, "size": getattr(ix, type).file_size, "thumb": ix.video.thumbs[0].file_id if (type == "video" and ix.video.thumbs) else "", "duration": ix.video.duration if type == "video" else ""})
        else:
                type = mediatotype(msg.media)
                if type:
                    media_cl.append({"type": type, "file_id": getattr(msg, type).file_id, "size": getattr(msg, type).file_size, "thumb": msg.video.thumbs[0].file_id if (type == "video" and msg.video.thumbs) else "", "duration": msg.video.duration if type == "video" else ""})
    return media_cl

async def join_process(file_list, chat_id, hint = False):
    if len(file_list) <= 10:
        if len(file_list) == 1:
            if type(file_list[0]) == InputMediaPhoto:
                msg = await app.send_photo(chat_id, file_list[0].media)
            if type(file_list[0]) == InputMediaVideo:
                msg = await app.send_video(chat_id, file_list[0].media, thumb = file_list[0].thumb)
            if type(file_list[0]) == InputMediaAudio:
                msg = await app.send_audio(chat_id, file_list[0].media)
            if type(file_list[0]) == InputMediaDocument:
                msg = await app.send_document(chat_id, file_list[0].media)
            await media_prep(chat_id, msg.id, 0, msg.date)
            return
        else:
            try:
                msg = await app.send_media_group(chat_id, file_list)
                await media_prep(chat_id, msg[0].id, 0, msg[0].date, str(msg[0].media_group_id))
            except Exception as e:
                print(e)
                await app.send_message(chat_id, text = "暂不支持文档和图片进行组包")
            finally:
                return
    else:
        if not hint:
            try:
                await app.send_message(chat_id, text = "媒体总数超过10个，将以10个一组返回，请耐心等待")
            except Exception:
                return
        try:
            msg = await app.send_media_group(chat_id, file_list[0:10])
        except Exception as e:
            print(e)
            return
        await asyncio.sleep(1.2)
        await media_prep(chat_id, msg[0].id, 0, msg[0].date, str(msg[0].media_group_id))
        await asyncio.sleep(2 + random.randint(15,45) / 10)
        return await join_process(file_list[10:], chat_id, hint = True)

async def pre_command(message):
    in_text = message.text
    result = re.findall(r'\w{48}-\w{8}', in_text)
    msg_id = message.id
    chat_id = message.chat.id
    if (message.from_user and message.from_user.id):
        from_id = message.from_user.id
    else:
        from_id = 0
    if result and len(result) > 0:
        if decode_rate_con(from_id):
            cdt = math.ceil(decode_rate_con(from_id))
            try:
                if cdt < 20 and ret_task_count <= 4:
                    try:
                        await app.send_message(chat_id = message.chat.id, text = "资源将在" + str(cdt) + "秒后返回，请勿重复点击")
                    except Exception:
                        return
                    decode_rate_con(from_id, 8)
                    await asyncio.sleep(cdt + ret_task_count * 0.33)
                else:
                    subbot_btn = InlineKeyboardMarkup([[
                        InlineKeyboardButton("发给副BOT处理",url = "https://t.me/mlk3autobot?start=" + result[0])
                    ]])
                    if len(result) == 1:
                        try:
                            await app.send_message(chat_id = message.chat.id, text = "每" + str(cdt) + "秒最多提交一次解析请求，请稍后再试", reply_markup = subbot_btn)
                        except Exception:
                            return
                    else:
                        try:
                            await app.send_message(chat_id = message.chat.id, text = "每" + str(cdt) + "秒最多提交一次解析请求，请稍后再试")
                        except Exception:
                            return
                    return
            except Exception  as e:
                print(e)
        if len(result) > 3:
            #return warning info
            try:
                await app.send_message(chat_id = message.chat.id, text = "一次最多解析三个KEY，超出部分会被忽略")
            except Exception:
                return
            result = result[0:3]
        if in_text.find("主分享KEY") >= 0 and in_text.find("一次性KEY") >= 0:
            result = result[0:1]
        #send to decode func
        await link_prep(chat_id, msg_id, from_id, result)

@app.on_message(filters.command("start") & filters.private)
async def cmd_main(client, message):
    if (message.command and len(message.command) == 2):
        await pre_command(message)
        return
    from_user = message.from_user.id
    welcome_text = '''
我是一个资源存储机器人，能够帮你把媒体资源转换为代码链接，便于分享和转发
直接向我发送媒体开始使用，或者发送 /help 查看帮助
'''
    try:
        await app.send_message(from_user, welcome_text)
    except Exception:
        return

@app.on_message(filters.command("help") & filters.private)
async def cmd_main(client, message):
    from_user = message.from_user.id
    help_message = '''
向我发送媒体或媒体组，你将得到两个代码链接：<u>主分享KEY</u>和<u>一次性KEY</u>
链接格式均为：<pre>[48位资源索引]-[8位密钥]</pre> 主分享KEY和一次性KEY的资源索引相同，但密钥不同

🔖 一次性KEY在被获取后，其密钥会自动销毁，即仅能获取一次，主分享KEY可以重复被获取
如果你是资源上传者，可以向机器人发送主分享KEY来获取最新的一次性KEY
为避免爆破攻击，当资源索引正确但密钥错误时系统会给出提示，并进入一分钟的冷却时间

📒 资源上传者可以向任意一条带资源链接的消息回复 <pre>/name 资源名称</pre> 来对资源命名，该名称只有上传者可见，用于资源搜索。资源名称中切勿包含空格

🔎 资源上传者可以使用 <pre>/s 关键词</pre> 来搜索自己上传的、有主动命名过的资源，[举例] 关键词'数字'可以匹配'阿拉伯数字'，'大写数字捌'等，搜索结果最多返回最近12条，搜索冷却时间为12秒

🔑 对于同一用户，链接转媒体的冷却时间为12秒，每条消息最多提交三个链接进行解析，超出部分会被忽略

📦如需将多个媒体组包成一个，可以使用 <pre>/joina</pre> 命令来操作。发送该命令后可以多次发送最多60个媒体，完成时点击“已发完”即可。举例：你分三次向机器人发送了2+1+3个媒体，使用组包功能可以将6个媒体集合成一条消息。TG允许一条消息包含最多10个媒体，如果组包后超过10个，会以每10个一组返回。

🧰如需将多个资源归总到一个文件夹，可以使用 `/pack` 命令来操作。资源上传者向任意一条含KEY的消息回复 <pre> /pack </pre>，会得到一个随机生成的文件夹ID（例如114514），向其他含KEY的消息回复 <pre> /pack 114514 </pre> 可以将这条资源也加入到 114514 文件夹中。

取回资源时，只需要发送文件夹内任意一条KEY，都能够获取到这个文件夹内全部的资源。
单个文件夹最多支持添加6个KEY

⛓️‍💥已经发出去的主KEY如需停止分享，上传者可以用 <pre> /lock </pre> 来回复带KEY的消息，或者向机器人发送 <pre> /lock 主分享链接 </pre> 更换主KEY。更换后会收到新的分享主KEY，曾经发出的主KEY无法再获取，但已获取过的资源不会被撤回。
'''
    try:
        await app.send_message(from_user, help_message)
    except Exception:
        return

@app.on_message(filters.command("joina") & filters.private)
async def pre_join(client, message):
    uid = message.from_user.id if message.from_user.id else 0
    if uid == 0:
        return
    clean_expired_join_users()
    if uid not in join_users:
        join_users[uid] = time.time()
        try:
            await app.send_message(uid, text = "*请在15分钟内发送完所有需要组包的媒体*\n注意[图片photo、视频video]和[文档file/document]不能混合组包")
        except Exception as e:
            print(f"Error: {e}")
            return

@app.on_message(filters.command("join") & filters.private)
async def join_media(client, message):
    if decode_rate_con(message.from_user.id):
        try:
            await app.send_message(chat_id = message.chat.id, text = "每30秒最多提交一次媒体组包请求，请稍后再试")
        except Exception:
            return
        return
    chat_id = message.chat.id
    join_text = message.text
    result = re.findall(r'\w{48}-\w{8}', join_text)
    if not result:
        return
    if len(result) < 2 or len(result) > 20:
        try:
            await app.send_message(chat_id = message.chat.id, text = "媒体组包功能需要2-20个分享链接，不可小于2或大于20")
        except Exception:
            return
    files = await link_prep(chat_id, 0, 0, result, join_op=1)
    if not files:
        return
    #print(files)
    file_list = []
    for file in files:
        if file["type"] == "video":
            file_list.append(InputMediaVideo(file["file_id"], file["thumb"]))
        if file["type"] == "photo":
            file_list.append(InputMediaPhoto(file["file_id"]))
        if file["type"] == "audio":
            file_list.append(InputMediaAudio(file["file_id"]))
        if file["type"] == "document":
            file_list.append(InputMediaDocument(file["file_id"]))
    decode_rate_con(message.from_user.id, p = 18)
    await join_process(file_list, chat_id)
    #await app.send_media_group(chat_id, file_list)

@app.on_message(filters.command("s") & filters.private)
async def cmd_main(client, message):
    if (message.text.find(" ") > 0):
        search_word = message.text.split(" ")[-1]
        if decode_rate_con(message.from_user.id):
            try:
                await app.send_message(chat_id = message.chat.id, text = "每12秒最多提交一次搜索请求，请稍后再试")
            except Exception:
                return
        data = search_names(message.from_user.id, search_word[0:32])
        if data:
            search_rr = '<b>搜索结果</b>：\n'
            n = 1
            for w in data:
                search_rr += str(n) + '.' + str(w['name']) + ': `https://t.me/mlkautobot?start=' + w['mlk'] + '-' + w['mkey'] + '`\n'
                n += 1
            try:
                await app.send_message(chat_id = message.chat.id, text = search_rr)
            except Exception:
                return
        else:
            try:
                await app.send_message(chat_id = message.chat.id, text = "搜索无结果")
            except Exception:
                return

@app.on_message(filters.media_group & filters.private & ~filters.reply & ~filters.sticker)
async def media_maing(client, message):
    cleanup_processed_media_groups()
    if (message.from_user and message.from_user.id):
        owner = message.from_user.id
    else:
        owner = 0
    msg_id = message.id
    chat_id = message.chat.id
    mgroup_id = str(message.media_group_id)
    msg_dt = message.date
    if mgroup_id in processed_media_groups:
        return
    #send to storage func
    processed_media_groups[mgroup_id] = time.time()
    #copy and return the message
    try:
        await app.copy_media_group(owner, chat_id, msg_id)
    except Exception as e:
        print(e)
        return
    if owner in join_users:
        files = await read_media([msg_id], chat_id)
        if files and len(files) > 0:
            join_length = write_joins(owner, files)
        if join_length >= 50:
            content = "请注意单次组包最多60个媒体，当前已暂存" + str(join_length) + "个，超出60个的部分会被忽略"
        else:
            content = "当前已暂存" + str(join_length) + "个媒体，可继续发送或点击完成"
        act = InlineKeyboardMarkup([[
            InlineKeyboardButton("已传完，开始组包", callback_data=str(owner)+"?join=DONE")
        ]])
        try:
            await app.send_message(chat_id, text = content, reply_markup = act)
        except Exception as e:
            print(e)
        finally:
            return
    await media_prep(chat_id, msg_id, owner, msg_dt, mgroup_id)

@app.on_message( (filters.audio | filters.document | filters.photo | filters.video) & filters.private & ~filters.reply)
async def media_mains(client, message):
    if (message.media_group_id):
        return
    if (message.from_user and message.from_user.id):
        owner = message.from_user.id
    else:
        owner = 0
    msg_id = message.id
    chat_id = message.chat.id
    msg_dt = message.date
    try:
        await app.copy_message(owner, chat_id, msg_id)
    except Exception as e:
        print(e)
        return
    if owner in join_users:
        files = await read_media([msg_id], chat_id)
        if files and len(files) > 0:
            join_length = write_joins(owner, files)
        if join_length >= 50:
            content = "请注意单次组包最多60个媒体，当前已暂存" + str(join_length) + "个，超出60个的部分会被忽略"
        else:
            content = "当前已暂存" + str(join_length) + "个媒体，可继续发送或点击完成"
        act = InlineKeyboardMarkup([[
            InlineKeyboardButton("已传完，开始组包", callback_data=str(owner)+"?join=DONE")
        ]])
        try:
            await app.send_message(chat_id, text = content, reply_markup = act)
        except Exception as e:
            print(e)
        finally:
            return
    #send to storage func
    await media_prep(chat_id, msg_id, owner, msg_dt)

@app.on_message(filters.reply & filters.private & filters.command("name"))
async def reply_main(client, message):
    msg_id = message.id
    chat_id = message.chat.id
    content = message.reply_to_message.text
    result = re.search(r'\w{48}-\w{8}', content)
    result = result.group(0)
    cdt = math.ceil(decode_rate_con(message.from_user.id))
    if cdt:
        try:
            await app.send_message(chat_id = message.chat.id, text = "每12秒最多提交一次命名请求，请稍后再试")
        except Exception:
            return     
    if (message.text.find(" ") > 0):
        new_name = message.text.split(" ")[-1]
        if len(result):
            data_set = read_rec(result[0:48])
            if (data_set and data_set['owner'] == message.from_user.id):
                try:
                    set_name(result[0:48], new_name[0:32])
                    await app.send_message(chat_id, text = "命名成功", reply_to_message_id = message.id)
                except Exception as e:
                    await app.send_message(chat_id, text = "命名失败，请勿使用特殊符号", reply_to_message_id = msg_id)
                finally:
                    return
            else:
                await app.send_message(chat_id, text = "你不是资源上传者，无权进行命名操作", reply_to_message_id = msg_id)
            return

@app.on_message(filters.reply & filters.private & filters.command("pack"))
async def add_to_pack(client, message):
    msg_id = message.id
    chat_id = message.chat.id
    content = message.reply_to_message.text
    mlk = []
    try:
        mlk.append(re.search(r'\w{48}-\w{8}', content).group(0)[0:48])
    except Exception:
        await app.send_message(chat_id = message.chat.id, text = "操作错误，请用 /pack 回复媒体消息")
        return
    if (message.from_user and message.from_user.id):
        owner = message.from_user.id
    else:
        owner = 0
    cdt = math.ceil(decode_rate_con(message.from_user.id))
    if cdt:
        try:
            await app.send_message(chat_id = message.chat.id, text = "每12秒最多提交一次文件夹请求，请稍后再试")
        except Exception:
            return
    data_set = read_rec(mlk[0][0:48])
    if (not data_set or not data_set['owner'] == owner):
        try:
            await app.send_message(chat_id, text = "你不是资源上传者，无权设定文件夹", reply_to_message_id = msg_id)
            return
        except Exception:
            return
    if (message.text == "/pack"):
        packid = hashlib.shake_128()
        pre_id = str(chat_id) + str(msg_id) + str(owner) + str(uuid.uuid4()) + str(time.time())
        packid.update(pre_id.encode())
        packid = packid.hexdigest(6)
        try:
            set_packid(mlk,packid)
            await app.send_message(chat_id, text = "资源成功添加到文件夹: `" + packid + "`\n请注意资源只能归属于一个文件夹，重复添加会覆盖之前的记录\n\n<点击上方代码可直接复制文件夹ID>", reply_to_message_id = message.id)
        except Exception:
            pass
        finally:
            return
    if (message.text.find(" ") > 0):
        request_packid = message.text.split(" ")[-1]
        pack_test = read_pack(request_packid)
        if pack_test:
            if len(pack_test) <= 5:
                try:
                    set_packid(mlk,request_packid)
                    await app.send_message(chat_id, text = "资源成功添加到文件夹: `" + request_packid + "`\n请注意资源只能归属于一个文件夹，重复添加会覆盖之前的记录\n\n<点击上方代码可直接复制文件夹ID>", reply_to_message_id = message.id)
                except Exception:
                    return
            else:
                try:
                    await app.send_message(chat_id, text = "单个文件夹最多支持添加6个KEY", reply_to_message_id = msg_id)
                except Exception:
                    return
        else:
            try:
                await app.send_message(chat_id, text = "文件夹ID不支持自行设置，请先将任意资源添加到文件夹来获取一个文件夹ID", reply_to_message_id = msg_id)
            except Exception:
                return

@app.on_message(filters.private & filters.command("top"))
async def top_rank(client, message):
    msg_id = message.id
    chat_id = message.chat.id
    if (message.from_user and message.from_user.id):
        owner = message.from_user.id
    else:
        return
    cdt = math.ceil(decode_rate_con(message.from_user.id))
    if cdt:
        try:
            await app.send_message(chat_id = message.chat.id, text = "每12秒最多提交一次取回排行请求，请稍后再试")
        except Exception:
            return
    view_data = top_views(owner)
    if not view_data:
        return
    result = ""
    for rec in view_data:
        result += "[" + str(rec['id']) + "](https://t.me/mlkautobot?start=" + rec['mlk'] + "-" + rec['mkey'] + ")  > 取回次数:" + str(rec['views']) + "\n"
    result = "以下是当前帐号取回最多的资源（最多显示5条）：\n\n" + result + "\n\n命名、添加文件夹等操作也会增加取回次数，计数可能多于实际取回次数"
    try:
        await app.send_message(chat_id, result, reply_to_message_id = msg_id)
    except Exception:
        return

@app.on_message(filters.private & filters.command("lock"))
async def top_rank(client, message):
    msg_id = message.id
    chat_id = message.chat.id
    if (message.from_user and message.from_user.id):
        owner = message.from_user.id
    else:
        return
    cdt = math.ceil(decode_rate_con(message.from_user.id))
    if cdt:
        try:
            await app.send_message(chat_id = message.chat.id, text = "每12秒最多提交一次换KEY请求，请稍后再试")
        except Exception:
            return
    if (message.reply_to_message):
        result = re.search(r'\w{48}-\w{8}', message.reply_to_message.text)
        result = result.group(0) if result else ""
    else:
        if (message.text.find(" ") > 0):
            result = message.text.split(" ")[-1]
            result = re.search(r'\w{48}-\w{8}', result)
            result = result.group(0) if result else ""
        else:
            return
    if not len(result):
        return
    data_set = read_rec(result[0:48])
    if (data_set and data_set['owner'] != owner):
        try:
            await app.send_message(chat_id, text = "你不是资源上传者，无权更换主KEY", reply_to_message_id = msg_id)
        except Exception:
            return
    try:
        new_key = rotate_mkey(result[0:48])
        await app.send_message(chat_id, text = "主KEY更换成功: `https://t.me/mlkautobot?start=" + result[0:48] + "-" + new_key + "`", reply_to_message_id = msg_id)
    except Exception:
        return

@app.on_callback_query()
async def queue_ans(client, callback_query):
    if not callback_query.data.split("?")[0] or not callback_query.data.split("?")[1]:
        return
    cmd = callback_query.data.split("?")[1].split("=")[0]
    op = callback_query.data.split("?")[1].split("=")[-1]
    chat_id = callback_query.message.chat.id
    owner = callback_query.from_user.id
    if len(callback_query.data.split("?")[0]) == 48:
        try:
            mlk = callback_query.data.split("?")[0]
        except Exception:
            return
        data_set = read_rec(mlk)
        if data_set['owner'] != owner:
            try:
                await app.send_message(chat_id, text = "你不是资源上传者，无权操作")
            except Exception:
                return
        if cmd == "exp":
            cdt = math.ceil(decode_rate_con(callback_query.message.from_user.id))
            if cdt:
                try:
                    await app.send_message(chat_id, text = "每12秒最多提交一次请求，请稍后再试")
                except Exception:
                    return
            if op == "1H":
                exp = datetime.now() + timedelta(hours=1)
            if op == "3H":
                exp = datetime.now() + timedelta(hours=3)
            if op == "24H":
                exp = datetime.now() + timedelta(days=1)
            if op == "NULL":
                exp = datetime.now() + timedelta(weeks=300)
            exp = datetime.strftime(exp, "%Y-%m-%d %H:%M:%S")
            try:
                set_expire(mlk, exp)
                await app.send_message(chat_id, text = "过期时间已设定为：" + exp)
                await app.send_message(chat_id, text = "点击可直接复制：`https://t.me/mlkautobot?start=" + mlk + "-" + data_set['mkey'] + '  限时分享：' + exp + "`")
                return
            except Exception:
                return
    if cmd == "join":
        if op == "DONE":
            if owner in join_users:
                del join_users[owner]
            files = read_joins(owner, delete = True)
            if files:
                file_list = []
                for file in files:
                    if file["type"] == "video":
                        file_list.append(InputMediaVideo(file["file_id"], file["thumb"]))
                    if file["type"] == "photo":
                        file_list.append(InputMediaPhoto(file["file_id"]))
                    if file["type"] == "audio":
                        file_list.append(InputMediaAudio(file["file_id"]))
                    if file["type"] == "document":
                        file_list.append(InputMediaDocument(file["file_id"]))
                await join_process(file_list, chat_id)
            return

@app.on_message(filters.command("status"))
async def stat_report(client, message):
    if message.from_user.id and message.from_user.id == admin:
        content = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S") + " stat report:\n"
        content += "memory_usage: " + str(round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024,2)) + " MB\n"
        content += "processed_media_groups: " + str(len(processed_media_groups)) + "\n"
        content += "decode_users: " + str(len(decode_users)) + "\n"
        content += "ret_task_count: " + str(ret_task_count) + "\n"
        content += "stor_task_count: " + str(stor_task_count) + "\n"
        content += "join_users: " + str(len(join_users)) + "\n"
    await app.send_message(message.chat.id, text = content)

@app.on_message(filters.private & filters.command("ckfileids"))
async def check_fileids(client, message):
    data_set = read_null_fileids()
    if data_set:
        for file in data_set:
            fileids = await read_media([file['desta']], groups[0])
            write_rec_fileids(json.dumps(fileids), file['mlk'])
            await asyncio.sleep(4)

@app.on_message(filters.text & filters.private)
async def ret_main(client, message):
    await pre_command(message)
app.run()