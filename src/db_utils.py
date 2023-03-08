import datetime
import boto3
from boto3.dynamodb.conditions import Key
from cryptography.fernet import Fernet
import hashlib
import os
import copy

AES_KEY = os.environ['AES_KEY']
fernet = Fernet(AES_KEY)

def query(table,line_user_id,record_limit=20):
    hashed_id = hashlib.md5(line_user_id.encode("utf-8")).hexdigest()
    records = table.query(
        KeyConditionExpression=Key('LineUserID').eq(hashed_id),
        ScanIndexForward=False, # DESC
        Limit=record_limit
    )

    for record in records['Items']:
        record['ChatContent']['content'] = fernet.decrypt(record['ChatContent']['content']).decode('utf-8')
    
    return records
    
def put(table,line_user_id,chat_content):
    chat_content_crypted = copy.deepcopy(chat_content)
    chat_content_crypted['content'] = fernet.encrypt(chat_content_crypted['content'].encode('utf-8')).decode('utf-8')
    item = {
        'LineUserID': hashlib.md5(line_user_id.encode("utf-8")).hexdigest(),
        'Timestamp': int(datetime.datetime.now().timestamp() * 1000),
        'ChatContent': chat_content_crypted
    }

    table.put_item(Item=item)
