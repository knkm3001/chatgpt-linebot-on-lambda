import datetime
import boto3
from boto3.dynamodb.conditions import Key

def query(table,line_user_id,record_limit=20):
    res = table.query(
        KeyConditionExpression=Key('LineUserID').eq(line_user_id),
        ScanIndexForward=False, # DESC
        Limit=record_limit
    )
    return res
    
def put(table,line_user_id,chat_content):
    item = {
        'LineUserID': line_user_id,
        'Timestamp': int(datetime.datetime.now().timestamp() * 1000),
        'ChatContent': chat_content
    }
    table.put_item(Item=item)