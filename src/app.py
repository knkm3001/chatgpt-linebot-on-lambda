import os
import json
import traceback
from typing import Tuple

import tiktoken
import requests

import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage

from conf import system_prompt
import db_utils

line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
OPENAI_APIKEY = os.environ['OPENAI_APIKEY']

AWS_ACCESS_ID = os.environ['AWS_ACCESS_ID']
AWS_ACCESS_KEY = os.environ['AWS_ACCESS_KEY']
DYNAMODB_ENDPOINT = os.environ['DYNAMODB_ENDPOINT']

dynamodb = boto3.resource('dynamodb',
                            endpoint_url=DYNAMODB_ENDPOINT,
                            region_name='ap-northeast-1',
                            aws_access_key_id=AWS_ACCESS_ID,
                            aws_secret_access_key=AWS_ACCESS_KEY)
table = dynamodb.Table('lineChatWithOry_logTable')

record_limit = 20

def ask(message_log:list = []):
    """ ChatGPTに対話のコンテキストと質問を渡して回答を取得する """

    url = 'https://api.openai.com/v1/chat/completions'
    data = {
            "model": "gpt-3.5-turbo",
            "messages": message_log,
            "max_tokens": 1024,
            "temperature": 0.75
        }
    headers = {
	        'Content-Type': 'application/json',
	        'Authorization': 'Bearer ' + OPENAI_APIKEY
        }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_data = response.json()
    # ChatGPTからの回答を取得する
    #print('response_datar',response_data)
    ans_message = response_data['choices'][0]['message']['content'].strip()
    message_log.append({'role':'assistant','content':ans_message})

    return ans_message, message_log


def create_message_log(system_prompt:list,message_text:str,line_user_id:str):
    """ chatGPTの文脈推定を行うため、過去のログを取得して、APIに渡すmessagesを作成する """

    records = db_utils.query(table,line_user_id)
    ex_message = [record['ChatContent'] for record in records['Items']]
    message_log = ex_message + [{'role':'user','content':message_text}]

    # system なければ先頭に追加
    is_exists_system_prompt = [log for log in message_log if log['role']=='system']
    if len(is_exists_system_prompt)==0:
        message_log = system_prompt + message_log

    #print('message_log:',message_log)
    last_system_index = 0
    for i,ex_message in enumerate(message_log):
        if ex_message['role'] == 'system':
            last_system_index = i

    # 4096トークンでエラーになるので、cahtGPTからの回答分のマージンをつくる
    token_num = num_tokens_from_messages(message_log)
    print('現在のtoken数:',token_num)
    if token_num >= 3072:
        while True:
            if len(message_log) == last_system_index+1 or token_num < 3072:
                break
            message_log.pop(last_system_index+1) # system以降を削除
            token_num = num_tokens_from_messages(message_log)
            print('log削除実行\n現在のtoken数:',token_num)

    return message_log


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    if model == "gpt-3.5-turbo-0301":  # note: future models may deviate from this
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += len(encoding.encode(value))
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always required and always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not presently implemented for model {model}.
    See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")



def lambda_handler(event, context):
    """ 
    aws lambda 本体 

    開発時はline APIの部分をコメントアウト
    """

    try:
        print(event)
        # LINEからメッセージを受信
        if event['events'][0]['type'] == 'message':
            if event['events'][0]['message']['type'] == 'text':
                
                reply_token = event['events'][0]['replyToken'] # リプライ用トークン
                message_text = event['events'][0]['message']['text'] # 受信メッセージ   
                line_user_id = event['events'][0]['source']['userId'] # 受信メッセージ   
                
                message_log = create_message_log(system_prompt,message_text,line_user_id)

                db_utils.put(table,line_user_id,chat_content=message_log[-1]) # ユーザのメッセージを追加
                ans_message,message_log = ask(message_log)
                db_utils.put(table,line_user_id,chat_content=message_log[-1]) # chatGPTのメッセージを追加
                # 開発時は下記をコメントアウト
                line_bot_api.reply_message(reply_token, TextSendMessage(text=ans_message))
    
    # エラーが起きた場合
    except Exception as e:
        print(e)
        traceback.print_exc()
        return {'statusCode': 500, 'body': json.dumps('Exception occurred.')}
    
    return {'statusCode': 200, 'body': json.dumps('Reply ended normally.')}
