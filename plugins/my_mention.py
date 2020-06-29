# coding: utf-8
import json
import re
import sqlite3
import dropbox
import requests
import codecs
import pandas as pd
import schedule
import time
import datetime
from slackbot.bot import respond_to  # @botname: で反応するデコーダ
from slackbot.bot import listen_to  # チャネル内発言で反応するデコーダ
from slackbot.bot import default_reply  # 該当する応答がない場合に反応するデコーダ

# @respond_to('string')     bot宛のメッセージ
#                           stringは正規表現が可能 「r'string'」
# @listen_to('string')      チャンネル内のbot宛以外の投稿
#                           @botname: では反応しないことに注意
#                           他の人へのメンションでは反応する
#                           正規表現可能
# @default_reply()          DEFAULT_REPLY と同じ働き
#                           正規表現を指定すると、他のデコーダにヒットせず、
#                           正規表現にマッチするときに反応
#                           ・・・なのだが、正規表現を指定するとエラーになる？

# message.reply('string')   @発言者名: string でメッセージを送信
# message.send('string')    string を送信
# message.react('icon_emoji')  発言者のメッセージにリアクション(スタンプ)する
#                               文字列中に':'はいらない
# con = sqlite3.connect(":memory:")


dropbox_token = ''
slack_token = ""
con = sqlite3.connect("tank.db", check_same_thread=False, isolation_level=None)
cur = con.cursor()
cur.execute(
    '''CREATE TABLE IF NOT EXISTS food_master (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id varchar(100),name varchar(100) NOT NULL,
    status varchar(100),date date,delete_flag int(2),url varchar(10000))''')
cur.execute(
    "INSERT INTO food_master(user_id, name, status, date, url, delete_flag) VALUES ('user_1', 'バナナ', '2本', '2020-06-23', 'image_url', 0)\n,"
    "('user_1','チョコ','食べかけ','2020-05-30','image_url',0)")
cur.execute("SELECT * FROM food_master")
print("初期状態" + str(cur.fetchall()))


def user_info_get(user_id):
    payload = {
        'token': slack_token,
        'user': user_id
    }
    user_info = 'https://slack.com/api/users.info'
    res = requests.get(user_info, params=payload)
    real_name = res.json()["user"]["real_name"]
    return real_name


def chat_post(message, user_id, name, id, status, date, url):
    post_url = 'https://slack.com/api/chat.postMessage'
    channel = message.body["channel"]
    real_name = user_info_get(user_id)  # user_idからuser_nameを表示する
    blocks = [
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*" + name + "*\n\nID : " + str(
                    id) + "\nMEMO : " + status + "\n登録者 : " + real_name + "\n登録日 : " + date
            },
            "accessory": {
                "type": "image",
                "image_url": url,
                "alt_text": "pic"
            }
        },
        {
            "type": "divider"
        }
    ]

    payload = {
        'token': slack_token,
        'channel': channel,
        'as_user': 'true',
        'blocks': json.dumps(blocks)
    }

    res = requests.post(post_url, data=payload)
    print(res.json())
    print(res.json()["ok"])
    if str(res.json()["ok"]) == "False":
        print("ぴえん")
        raise ValueError("error!")

    return res


default_url = 'image_url'


@listen_to(r'^登録\s(.*)$')
@respond_to(r'^登録\s(.*)$')
def add(message, text):
    try:
        message.react('+1')  # リアクション 相手にスタンプをつける
        text_list = re.split('\s+', text)
        if len(text_list) == 1:
            name = text_list[0]
            status = ""
        elif len(text_list) == 2:
            name = text_list[0]
            status = text_list[1]
        else:
            raise ValueError("error!")
        date = datetime.date.today()  # 今日の日付
        user_id = message.body['user']
        if 'files' in message.body:
            url = message.body['files'][0]['url_private']
            timestamp = message.body['files'][0]['timestamp']
            title = message.body['files'][0]['title']
            path = './images/' + str(timestamp) + user_id + title
            rst = requests.get(url, headers={'Authorization': 'Bearer %s' % slack_token}, stream=True)
            with open(path, 'wb') as f:
                f.write(rst.content)
            f.close()

            # ファイルをDropboxにアップロード
            dropbox_path = '/images/' + str(timestamp) + user_id + title
            dbx = dropbox.Dropbox(dropbox_token)
            f = open(path, 'rb')
            dbx.files_upload(f.read(), dropbox_path)
            f.close()

            # 共有リンク作成
            setting = dropbox.sharing.SharedLinkSettings(
                requested_visibility=dropbox.sharing.RequestedVisibility.public)
            link = dbx.sharing_create_shared_link_with_settings(path=dropbox_path, settings=setting)

            # 共有リンク取得
            links = dbx.sharing_list_shared_links(path=dropbox_path, direct_only=True).links
            if links is not None:
                for link in links:
                    url = link.url
                    print(url)
                    url = url.replace('www.dropbox', 'dl.dropboxusercontent').replace('?dl=0', '')
                    print("aaaaa" + url)
        else:
            url = default_url

        cur.execute("INSERT INTO food_master(user_id, name, status, date, url, delete_flag) VALUES (?,?,?,?,?,0)",
                    [user_id, name, status, date, url])
        cur.execute("SELECT * FROM food_master ")
        cur.execute("SELECT LAST_INSERT_ROWID()")
        df = pd.DataFrame(cur.fetchall())
        id = df.iat[0, 0]

        print(df)

        # message.reply("【登録完了】")
        chat_post(message, user_id, name, id, status, str(date), url)

    except ValueError:
        message.reply("\n"
                      "お疲れ様です!\n"
                      "以下を入力してください\n"
                      "\n"
                      "登録　商品名　MEMO(任意)\n"
                      "変更　ID　MEMO(変更後)\n"
                      "削除　ID\n"
                      "表示　ID\n"
                      "全て表示\n"
                      "\n"
                      "※項目ごとにスペースを空けてください\n"
                      "※数字は半角で打ってください\n"
                      "※IDは登録後に付与されます\n"
                      "\n"
                      "冷蔵庫の保管期間は３日間です\n"
                      "登録から３日までに削除していない場合はこちらから通知します")


@listen_to(r'^削除\s(\d+)$')
@respond_to(r'^削除\s(\d+)$')
def delete(message, id):
    message.react('+1')  # リアクション 相手にスタンプをつける
    # user_id = message.body['user']
    cur.execute("select * from food_master where rowid = last_insert_rowid()")
    df = pd.DataFrame(cur.fetchall())
    print(df)
    last_id = df.iat[0, 0]
    id = int(id)
    last_id = int(last_id)
    if id <= last_id:
        cur.execute("UPDATE food_master SET delete_flag = ? WHERE id = ?", [1, id])
        cur.execute("SELECT * FROM food_master WHERE id = ?", [id])
        df = pd.DataFrame(cur.fetchall())
        print(df)
        id = df.iat[0, 0]
        user_id = df.iat[0, 1]
        name = df.iat[0, 2]
        status = df.iat[0, 3]
        date = df.iat[0, 4]
        url = df.iat[0, 6]
        message.reply("【削除完了】")
        chat_post(message, user_id, name, id, status, date, url)
        print(chat_post)
        print(df)
    else:
        message.reply("\n指定のIDは存在しません")


@listen_to(r'^表示\s(\d+)$')
@respond_to(r'^表示\s(\d+)$')
def one(message, id):
    message.react('+1')  # リアクション 相手にスタンプをつける
    cur.execute("select * from food_master where rowid = last_insert_rowid()")
    df = pd.DataFrame(cur.fetchall())
    print(df)
    last_id = df.iat[0, 0]
    id = int(id)
    last_id = int(last_id)
    if id <= last_id:
        cur.execute("SELECT * FROM food_master WHERE id = ?", [id])
        df = pd.DataFrame(cur.fetchall())
        print(df)
        id = df.iat[0, 0]
        user_id = df.iat[0, 1]
        name = df.iat[0, 2]
        status = df.iat[0, 3]
        date = df.iat[0, 4]
        delete_flag = df.iat[0, 5]
        url = df.iat[0, 6]

        if delete_flag == 0:
            message.reply("【表示完了】")
            chat_post(message, user_id, name, id, status, date, url)
            print(chat_post)
        else:
            message.reply("\n指定のIDはすでに削除されています")
    else:
        message.reply("\n指定のIDは存在しません")


@listen_to(r'^全て表示$')
@respond_to(r'^全て表示$')
def all(message):
    message.react('+1')  # リアクション 相手にスタンプをつける
    cur.execute("SELECT * FROM food_master WHERE delete_flag = 0")
    df = pd.DataFrame(cur.fetchall())
    print(df)
    message.reply("【全て表示】")
    for index, row in df.iterrows():
        print(index)
        id = df.iat[index, 0]
        user_id = df.iat[index, 1]
        name = df.iat[index, 2]
        status = df.iat[index, 3]
        date = df.iat[index, 4]
        url = df.iat[index, 6]

        chat_post(message, user_id, name, id, status, date, url)
        print(chat_post)


@listen_to(r'^変更\s(\d+)\s(.*)$')
@respond_to(r'^変更\s(\d+)\s(.*)$')
def delete(message, id, status):
    message.react('+1')  # リアクション 相手にスタンプをつける
    cur.execute("select * from food_master where rowid = last_insert_rowid()")
    df = pd.DataFrame(cur.fetchall())
    print(df)
    last_id = df.iat[0, 0]
    id = int(id)
    last_id = int(last_id)
    if id <= last_id:
        cur.execute("UPDATE food_master SET status = ? WHERE id = ?", [status, id])
        cur.execute("SELECT * FROM food_master WHERE id = ?", [id])
        df = pd.DataFrame(cur.fetchall())
        print(df)
        id = df.iat[0, 0]
        user_id = df.iat[0, 1]
        name = df.iat[0, 2]
        status = df.iat[0, 3]
        date = df.iat[0, 4]
        delete_flag = df.iat[0, 5]
        url = df.iat[0, 6]

        if delete_flag == 0:
            message.reply("【変更完了】")
            chat_post(message, user_id, name, id, status, date, url)
            print(chat_post)
        else:
            message.reply("\n指定のIDはすでに削除されています")
    else:
        message.reply("\n指定のIDは存在しません")
