# START OF UPDATED CODE (Step 3: API Gateway Integration)
import json
import boto3
import os
import datetime
import time

# 初始化 Boto3 clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-west-2')
s3_client = boto3.client('s3')
ts_query_client = boto3.client('timestream-query', region_name='us-west-2')

# --- Timestream/S3 設定 ---
DATABASE_NAME = "PeopleCountDB"
TABLE_NAME = "RoomData"
TARGET_S3_BUCKET = '<aws-weillington>' # 請確認已替換

# --- Timestream 結果格式化函數 (與之前相同) ---
def format_query_results(query_result):
    data_summary_lines = []
    if 'Rows' in query_result:
        for row in query_result['Rows']:
            if len(row.get('Data', [])) >= 3:
                raw_time = row['Data'][0].get('ScalarValue', 'N/A')
                room = row['Data'][1].get('ScalarValue', 'N/A')
                count = row['Data'][2].get('ScalarValue', 'N/A')
                try:
                    dt_object = datetime.datetime.strptime(raw_time.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    formatted_time = dt_object.strftime('%Y-%m-%d %H:%M')
                except ValueError:
                    formatted_time = raw_time
                data_summary_lines.append(f"- {formatted_time}, Room {room}: {count} 人")
            else:
                 print(f"Skipping row with unexpected data structure: {row}")
    if not data_summary_lines:
        return "在指定時間範圍內沒有查詢到使用數據。"
    return "\n".join(data_summary_lines)

def lambda_handler(event, context):
    """
    Lambda 主處理函數 (API Gateway 觸發)：
    1. 從 event 解析 user_question
    2. 查詢 Timestream 獲取數據
    3. 建構 Prompt
    4. 呼叫 Bedrock
    5. 將 Bedrock 回答包裝後回傳
    """
    print("Lambda function started via API Gateway.")
    print(f"Received event: {json.dumps(event)}") # 印出收到的 event 方便除錯

    # --- 1. 從 event 解析 user_question ---
    user_question = "請總結使用情況並提供建議。" # 預設問題
    try:
        # HTTP API payload v2.0， body 是字串，需要 parse
        if 'body' in event and event['body']:
            request_body = json.loads(event['body'])
            if 'user_question' in request_body:
                user_question = request_body['user_question']
        else:
             print("Warning: No body found in event or body is empty. Using default question.")

    except json.JSONDecodeError:
        print("Error: Could not decode JSON from event body. Using default question.")
    except Exception as e:
        print(f"Error parsing user_question from event: {e}. Using default question.")

    print(f"Processing user question: {user_question}")


    # --- 2. 查詢 Timestream 獲取數據 ---
    # (查詢過去 7 天數據)
    query_string = f"""
        SELECT time, Room, measure_value::bigint
        FROM "{DATABASE_NAME}"."{TABLE_NAME}"
        WHERE measure_name = 'PeopleCount'
          AND time BETWEEN ago(7d) AND now()
        ORDER BY time ASC
    """
    print(f"Executing Timestream query: {query_string}")
    data_summary_string = "查詢數據時發生錯誤。"
    try:
        all_rows = []
        next_token = None
        while True:
            query_params = {'QueryString': query_string}
            if next_token:
                query_params['NextToken'] = next_token
            page = ts_query_client.query(**query_params)
            all_rows.extend(page.get('Rows', []))
            next_token = page.get('NextToken')
            if not next_token: break
            else: time.sleep(0.1)

        print(f"Timestream query returned {len(all_rows)} rows.")
        query_result_for_formatting = {'Rows': all_rows}
        data_summary_string = format_query_results(query_result_for_formatting)
        print("Formatted data summary string for prompt:")
        # print(data_summary_string) # Debug: 印出完整數據

    except Exception as e:
        print(f"Error querying Timestream: {e}")
        # 查詢失敗，也要告知 Bedrock
        data_summary_string = f"查詢使用數據時發生錯誤：{e}"


    # --- 3. 建構 Prompt ---
    model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
    if "查詢數據時發生錯誤" in data_summary_string or "沒有查詢到使用數據" in data_summary_string:
         prompt = f"""Human: 無法獲取會議室使用數據，或是在指定的時間範圍內沒有數據 (錯誤訊息或提示：{data_summary_string})。請基於這個情況，回答使用者的問題："{user_question}"。如果問題與數據相關，請說明缺乏數據。請用繁體中文回答。

Assistant:"""
    else:
         prompt = f"""Human: 這裡有一份會議室過去一段時間每小時的使用人數數據：
{data_summary_string}

現在請根據這些數據，回答以下問題：
{user_question}

請用繁體中文回答。

Assistant:"""
    print("Prompt constructed for Bedrock.")

    # --- 4. 呼叫 Bedrock ---
    generated_text = f"處理請求時發生錯誤，無法呼叫 Bedrock。" # 預設錯誤回答
    try:
        print(f"Invoking Bedrock model: {model_id} in us-west-2")
        request_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31", "max_tokens": 1500,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            "temperature": 0.7, "top_p": 0.9
        })
        response = bedrock_runtime.invoke_model(
            body=request_body, modelId=model_id, accept='application/json', contentType='application/json'
        )
        response_body = json.loads(response['body'].read())
        if response_body.get('content') and isinstance(response_body['content'], list) and len(response_body['content']) > 0:
             generated_text = response_body['content'][0]['text']
             print(f"Successfully generated response from Bedrock.")
        else:
             print(f"Unexpected Bedrock response format: {response_body}")
             generated_text = "從 Bedrock 收到非預期的回應格式。"
             raise ValueError("Could not extract generated text from Bedrock response.")

    except Exception as e:
        print(f"Error invoking Bedrock model in us-west-2: {e}")
        generated_text = f"呼叫 AI 模型時發生錯誤：{e}"


    # --- (可選) 將結果存到 S3 ---
    # 您可以決定是否仍然需要將每次問答的結果存檔
    try:
        now_dt = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        target_s3_key = f'qa-logs/qa-{now_dt}.txt' # 換個資料夾存檔
        log_content = f"User Question:\n{user_question}\n\nData Summary Used:\n{data_summary_string}\n\nBedrock Response:\n{generated_text}"
        s3_client.put_object(
            Bucket=TARGET_S3_BUCKET, Key=target_s_key,
            Body=log_content.encode('utf-8'), ContentType='text/plain; charset=utf-8'
        )
        print(f"Successfully saved QA log to S3: {target_s_key}")
    except Exception as e:
        print(f"Warning: Failed to save QA log to S3: {e}")


    # --- 5. 將 Bedrock 回答包裝後回傳 ---
    print("Lambda function finished. Returning response to API Gateway.")
    return {
        'statusCode': 200, # 無論 Bedrock 是否成功，只要 Lambda 沒崩潰就回 200，讓前端處理回答內容
        'headers': {
            # CORS Headers - 允許來自任何來源的簡單請求，方便前端測試
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET' # 允許的方法
        },
        'body': json.dumps({
            'answer': generated_text # 將 Bedrock 的回答放在 'answer' 欄位
        })
    }
# END OF UPDATED CODE (Step 3: API Gateway Integration)