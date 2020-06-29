import json
import sqlite3

import requests
import pandas as pd
import schedule
import time
import datetime

ch_id = ''  #channel

def chat_post(user_id, name, id, status, date, url):
    post_url = 'https://slack.com/api/chat.postMessage'
    token = ''

    blocks = [
        {
            "type": "divider"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "<@"+user_id+">さん\n*3日以上過ぎていますよ*\n\n*" + name + "*\n\nID : " + str(id) + "\nMEMO : " + status + "\n登録日　 : " + date
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
        'token': token,
        'channel': ch_id,
        'as_user': 'true',
        'blocks': json.dumps(blocks)
    }

    res = requests.post(post_url, data=payload)
    print(res.json())
    return res


def job():
    print("バッチ処理開始")
    con = sqlite3.connect("../tank.db", check_same_thread=False, isolation_level=None)
    cur = con.cursor()
    cur.execute("SELECT * FROM food_master WHERE delete_flag = 0")
    df = pd.DataFrame(cur.fetchall())
    for index, row in df.iterrows():
        print(index)
        id = df.iat[index, 0]
        user_id = df.iat[index, 1]
        name = df.iat[index, 2]
        status = df.iat[index, 3]
        date = df.iat[index, 4]
        url = df.iat[index, 6]
        date_list = date.split('-')
        after = datetime.date(int(date_list[0]), int(date_list[1]), int(date_list[2]))  # strからdateに変換

        now = datetime.date.today()  # 今日の日付

        answer = (now - after)  # 今日ー登録した日 timedelta型
        day = answer.days  # timedeltaからintに変換
        print(day)

        if day > 3:
            print("a")
            #chat_post_men(user_id)
            chat_post(user_id, name, id, status, date, url)
            print(chat_post)


schedule.every(0.5).minutes.do(job)
while True:
    schedule.run_pending()
    time.sleep(1)
