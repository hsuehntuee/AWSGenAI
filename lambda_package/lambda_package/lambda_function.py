import boto3
import time
from datetime import datetime
from botocore.client import Config

kvs_client = boto3.client('kinesisvideo')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    stream_name = "bbbbb"
    bucket_name = "aws-weillington"
    
    try:
        # 獲取端點（需指定 API 名稱）
        endpoint_response = kvs_client.get_data_endpoint(
            StreamName=stream_name,
            APIName="GET_MEDIA"
        )
        endpoint_url = endpoint_response['DataEndpoint']
        
        # 初始化 KVS Archived Media 客戶端（關鍵修正）
        archive_client = boto3.client(
            'kinesisvideo',
            endpoint_url=endpoint_url,
            config=Config(signature_version='s3v4')
        )
        
        # 時間範圍設定
        end_time = datetime.utcnow()
        start_time = datetime.utcfromtimestamp(end_time.timestamp() - 10)
        
        # 調用 get_media（注意駝峰式命名）
        media_response = archive_client.get_media(
            StreamName=stream_name,
            StartSelector={
                'StartSelectorType': 'PRODUCER_TIMESTAMP',
                'Timestamp': start_time
            }
        )
        
        # 讀取並存儲到 S3
        media_data = media_response['Payload'].read()
        s3_key = f"kvs-recordings/{stream_name}-{int(time.time())}.mkv"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=media_data
        )
        
        return {'statusCode': 200, 'body': f"s3://{bucket_name}/{s3_key}"}
        
    except Exception as e:
        print(f"❌ 錯誤：{str(e)}")
        return {'statusCode': 500, 'body': str(e)}