import os
import json
import traceback
from logging import getLogger, getLevelName, INFO

import tiktoken
import requests

import boto3
from linebot import LineBotApi
from linebot.models import TextSendMessage

from conf import system_prompt
import db_utils

use_local_db = False # localのdynamoDBに接続

OPENAI_APIKEY = os.environ['OPENAI_APIKEY']
DO_LINE_REPLY = bool(int(os.environ['DO_LINE_REPLY']))
record_limit = int(os.environ['RECORD_FETCH_NUM'])
line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])

logger = getLogger(__name__)
level_name = os.environ.get('LOG_LEVEL')
level = getLevelName(level_name)
if not isinstance(level, int):
    level = INFO # デフォルト
logger.setLevel(level)

if use_local_db:
    DYNAMODB_ENDPOINT = os.environ['DYNAMODB_ENDPOINT']
    AWS_ACCESS_ID = os.environ['AWS_ACCESS_ID']
    AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
    dynamodb = boto3.resource('dynamodb',
                                endpoint_url=DYNAMODB_ENDPOINT,
                                region_name='ap-northeast-1',
                                aws_access_key_id='',
                                aws_secret_access_key='')
else:
    dynamodb = boto3.resource('dynamodb')

table = dynamodb.Table('lineChatWithOry_logTable')


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
    logger.info(f'cahtGPT APIへリクエスト実行')
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_data = response.json()
    logger.debug(f'response_data: {response_data}')

    if response_data.get('error'):
        logger.critical(f'chatGPT API error: {response_data}')
        ans_message = 'ちょっと調子がわるいオリ...。ごめんなさいだけどもしばらく休ませてオリ...。'
    else:
        ans_message = response_data['choices'][0]['message']['content'].strip()
    
    message_log.append({'role':'assistant','content':ans_message})

    return ans_message, message_log


def create_message_log(system_prompt:list,message_text:str,line_user_id:str):
    """ chatGPTの文脈推定を行うため、過去のログを取得して、APIに渡すmessagesを作成する """

    records = db_utils.query(table,line_user_id,record_limit)
    logger.debug(f'records: {records}')
    ex_messages = [record['ChatContent'] for record in records['Items']]
    message_log = ex_messages[::-1] + [{'role':'user','content':message_text}]

    last_system_index = None
    reset_message_index = None
    reset_message = 'オブリビエイト'
    for i,ex_message in enumerate(message_log):
        a = type(ex_message)
        if ex_message['role'] == 'system':
            last_system_index = i
        elif ex_message['content'] == reset_message:
            reset_message_index = i
    
    if reset_message_index is not None:
        message_log = system_prompt + message_log[reset_message_index:]

    if last_system_index is None:
        message_log = system_prompt + message_log
        last_system_index = 0


    logger.debug(f'message_log: {message_log}')

    # 4096トークンでエラーになるので、cahtGPTからの回答分のマージンをつくる
    token_num = num_tokens_from_messages(message_log)
    logger.debug(f'現在のtoken数: {token_num}')
    if token_num >= 3072:
        while True:
            if len(message_log) == last_system_index+1 or token_num < 3072:
                break
            message_log.pop(last_system_index+1) # system以降を削除
            token_num = num_tokens_from_messages(message_log)
            logger.debug(f'log削除実行\n現在のtoken数: {token_num}')
            

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
        logger.debug(f'event: {event}')
        # LINEからメッセージを受信
        if event['events'][0]['type'] == 'message':
            if event['events'][0]['message']['type'] == 'text':
                
                reply_token = event['events'][0]['replyToken'] # リプライ用トークン
                message_text = event['events'][0]['message']['text'] # 受信メッセージ   
                line_user_id = event['events'][0]['source']['userId'] # 受信メッセージ   
                
                if message_text == 'オブリビエイト':
                    db_utils.put(table,line_user_id,chat_content={'role':'user','content':message_text})
                    ans_message = 'ﾊｯ...!!'
                    message_log = system_prompt + [{'role':'assistant','content':ans_message}]
                    db_utils.put(table,line_user_id,chat_content=message_log[-1])
                else:
                    message_log = create_message_log(system_prompt,message_text,line_user_id)
                    db_utils.put(table,line_user_id,chat_content=message_log[-1]) # ユーザのメッセージを追加
                    logger.debug(f'message_log: {message_log}')
                    ans_message,message_log = ask(message_log)
                    db_utils.put(table,line_user_id,chat_content=message_log[-1]) # chatGPTのメッセージを追加
                
                if DO_LINE_REPLY:
                    logger.info(f'LINE レスポンス実行')
                    # ローカル開発に実行する場合はログ等からLINEのreply_tokenを取得してペイロードに埋め込むこと
                    line_bot_api.reply_message(reply_token, TextSendMessage(text=ans_message)) 
    
    # エラーが起きた場合
    except Exception as e:
        logger.critical(f'error: {e}')
        traceback.print_exc() # TODO logging
        return {'statusCode': 500, 'body': json.dumps('Exception occurred.')}
    
    return {'statusCode': 200, 'body': json.dumps('Reply ended normally.')}
