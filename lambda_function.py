# START OF UPDATED CODE for hackathonAIReportGenerator (Python - Fetch ALL measures)
import json
import boto3
import os
import datetime
import time
from collections import defaultdict # 用於聚合數據

# 初始化 Boto3 clients
REGION = os.environ.get('AWS_REGION', 'us-west-2')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=REGION)
s3_client = boto3.client('s3')
ts_query_client = boto3.client('timestream-query', region_name=REGION)

# --- 設定 ---
DATABASE_NAME = "PeopleCountDB"
TABLE_NAME = "RoomData2" # 確認使用 RoomData1
TARGET_S3_BUCKET = 'aws-weillington' # 請確認 S3 桶名稱

# --- 新的數據處理與格式化函數 ---
# --- 新的數據處理與格式化函數 (CORRECTED Python Syntax) ---
def process_and_format_all_data(all_rows, column_info):
    """
    處理 Timestream 返回的所有類型數據行，
    將其按圖片(Room)和時間(time)聚合，並格式化為字串給 Bedrock。
    """
    grouped_data = defaultdict(lambda: {"time_obj": None, "measures": {}})

    if not column_info or not all_rows:
        return "在指定時間範圍內沒有查詢到任何數據。"

    # 找出欄位索引
    time_idx, room_idx, measureNameIdx, bigintValueIdx, varcharValueIdx = -1, -1, -1, -1, -1
    for i, info in enumerate(column_info):
        name = info.get('Name')
        if name == 'time': time_idx = i
        elif name == 'Room': room_idx = i
        elif name == 'measure_name': measureNameIdx = i
        elif name == 'measure_value::bigint': bigintValueIdx = i
        elif name == 'measure_value::varchar': varcharValueIdx = i

    if time_idx == -1 or room_idx == -1 or measureNameIdx == -1:
        print("Warning: Could not find essential columns (time, Room, measure_name).")
        return "查詢結果格式錯誤，無法解析基本資訊。"

    # 遍歷所有行，進行聚合
    for row in all_rows:
        data = row.get('Data', [])
        # 確保行數據中有足夠的元素
        if len(data) > max(time_idx, room_idx, measureNameIdx, bigintValueIdx, varcharValueIdx):
            try:
                # *** 使用正確的 Python .get() 方法安全地獲取 ScalarValue ***
                # .get('ScalarValue') 會在鍵不存在時返回 None
                timestampStr = data[time_idx].get('ScalarValue')
                roomStr = data[room_idx].get('ScalarValue')
                measureNameStr = data[measureNameIdx].get('ScalarValue')
                bigintValueStr = data[bigintValueIdx].get('ScalarValue') # 返回 '123' 或 None
                varcharValueStr = data[varcharValueIdx].get('ScalarValue') # 返回 'abc' 或 None

                # 確保核心資訊存在才繼續處理
                if timestampStr and roomStr and measureNameStr:
                    group_key = (roomStr, timestampStr)

                    # 儲存 time object (只存一次)
                    if not grouped_data[group_key]["time_obj"]:
                         try:
                            grouped_data[group_key]["time_obj"] = datetime.datetime.strptime(timestampStr.split('.')[0], '%Y-%m-%d %H:%M:%S')
                         except ValueError:
                             print(f"Could not parse timestamp: {timestampStr}")
                             continue # 跳過此行

                    # 儲存度量值 (bigint 優先)
                    value = bigintValueStr if bigintValueStr is not None else varcharValueStr
                    # 確保 value 不是 None 才儲存 (或者您可以選擇儲存 None)
                    if value is not None:
                         grouped_data[group_key]["measures"][measureNameStr] = value
                    else:
                         # 如果 bigint 和 varchar 都是 Null，可以選擇記錄或忽略
                         print(f"Both bigint and varchar values are null for measure {measureNameStr} at {timestampStr}, room {roomStr}. Skipping measure storage.")


            except (IndexError, TypeError, AttributeError) as e:
                 # 捕捉可能的錯誤，例如 data[idx] 本身不存在或是 .get() 失敗 (雖然不太可能)
                 print(f"Error processing row structure: {row}, Error: {e}")
        else:
            print(f"Skipping row with insufficient data fields: {row}")

    # --- 格式化聚合後的數據 ---
    summary_lines = []
    # 按時間排序
    sorted_items = sorted(grouped_data.items(), key=lambda item: item[1]['time_obj'] if item[1]['time_obj'] else datetime.datetime.min)

    for key, data_dict in sorted_items:
        room, raw_time_key = key # key 是 (roomStr, timestampStr)
        time_obj = data_dict["time_obj"]
        measures = data_dict["measures"]

        if not time_obj: continue

        formatted_time = time_obj.strftime('%Y-%m-%d %H:%M:%S')
        summary_lines.append(f"\n--- 記錄點 ---")
        summary_lines.append(f"  時間: {formatted_time}")
        summary_lines.append(f"  圖片/房間: {room}")

        # 按照特定順序顯示度量，或全部顯示
        if 'PeopleCount' in measures:
            summary_lines.append(f"  人數 (PeopleCount): {measures['PeopleCount']}")
        if 'StackingDescription' in measures:
            description = str(measures['StackingDescription']).replace('\n', ' ').replace('\r', '')
            summary_lines.append(f"  描述 (StackingDescription): {description}")
        if 'Time' in measures:
             summary_lines.append(f"  時間度量值 (Time): {measures['Time']}")
        # 顯示其他未明確處理的度量
        for name, value in measures.items():
            if name not in ['PeopleCount', 'StackingDescription', 'Time']:
                summary_lines.append(f"  {name}: {value}")


    if not summary_lines:
        return "在指定時間範圍內沒有查詢到有效數據，或數據解析失敗。"

    return "\n".join(summary_lines)

# --- Lambda Handler (UPDATED QUERY and Prompt) ---
def lambda_handler(event, context):
    print("Lambda function started via API Gateway.")
    print(f"Received event: {json.dumps(event)}")

    # --- 1. 從 event 解析 user_question ---
    user_question = "請總結使用情況並提供建議。" # 預設問題
    try:
        if 'body' in event and event['body']:
            request_body = json.loads(event['body'])
            if 'user_question' in request_body:
                user_question = request_body['user_question']
    except Exception as e:
        print(f"Error parsing user_question from event: {e}. Using default question.")
    print(f"Processing user question: {user_question}")

    # --- 2. 查詢 Timestream 獲取數據 (UPDATED QUERY to fetch all measures) ---
    query_string = f"""
        SELECT time, Room, measure_name, "measure_value::bigint", "measure_value::varchar"
        FROM "{DATABASE_NAME}"."{TABLE_NAME}"
        WHERE time BETWEEN ago(7d) AND now() -- ** 移除了 measure_name 過濾 **
        ORDER BY Room, time ASC -- 按 Room 和 time 排序，方便後續聚合
    """
    print(f"Executing Timestream query: {query_string}")
    data_summary_string = "查詢數據時發生錯誤。"
    try:
        all_rows = []
        paginator = ts_query_client.get_paginator('query')
        # 需要先執行一次查詢來獲取 ColumnInfo
        initial_page = ts_query_client.query(QueryString=query_string, MaxRows=1)
        column_info = initial_page.get('ColumnInfo', [])

        if column_info:
            page_iterator = paginator.paginate(QueryString=query_string)
            for page in page_iterator:
                all_rows.extend(page.get('Rows',[]))

            print(f"Timestream query returned {len(all_rows)} total rows.")
            # 使用新的處理函數來聚合與格式化數據
            data_summary_string = process_and_format_all_data(all_rows, column_info)
            print("Formatted data summary string for prompt:")
            # print(data_summary_string) # Debug: 印出聚合後的摘要
        else:
            print("Warning: Timestream query did not return ColumnInfo.")
            data_summary_string = "查詢數據時未返回欄位資訊。"

    except Exception as e:
        print(f"Error querying or processing Timestream data: {e}")
        data_summary_string = f"查詢或處理使用數據時發生錯誤：{e}"

    # --- 3. 建構 Prompt (UPDATED Prompt Context) ---
    model_id = 'anthropic.claude-3-sonnet-20240229-v1:0' # 或其他模型
    # 根據是否有有效數據來調整 Prompt
    if "錯誤" in data_summary_string or "沒有查詢到" in data_summary_string:
         prompt = f"""Human: 無法獲取或解析會議室的詳細使用數據 (錯誤訊息或提示：{data_summary_string})。請基於這個情況，回答使用者的問題："{user_question}"。如果問題與數據相關，請說明缺乏數據。請用繁體中文回答。

Assistant:"""
    else:
         # 提供更豐富的上下文給 AI
         prompt = f"""Human: 這裡有一份數間會議室在過去一段時間內，不同時間點偵測到的詳細數據記錄。每個記錄點包含可能的度量（時間、人數、會議室狀態描述等）：
{data_summary_string}

請仔細分析以上所有提供的數據記錄，然後根據這些數據回答以下問題：
{user_question}

在回答時，請綜合考慮人數(PeopleCount)和其他可能的描述性資訊(StackingDescription)。回答不需要覆述已經提過的觀察結果，並請用繁體中文回答。

Assistant:"""
    print("Prompt constructed for Bedrock.")


    # --- 4. 呼叫 Bedrock (邏輯不變) ---
    generated_text = f"處理請求時發生錯誤，無法呼叫 Bedrock。"
    try:
        # (省略了 Bedrock 呼叫的 try-except 區塊，與之前版本相同)
        # ... Bedrock invoke_model call ...
        print(f"Invoking Bedrock model: {model_id} in {REGION}")
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
        print(f"Error invoking Bedrock model in {REGION}: {e}")
        generated_text = f"呼叫 AI 模型時發生錯誤：{e}"


    # --- (可選) S3 存檔 (邏輯不變) ---
    try:
        # (省略了 S3 存檔的 try-except 區塊，與之前版本相同)
        now_dt = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        target_s3_key = f'qa-logs/qa-{now_dt}.txt'
        log_content = f"User Question:\n{user_question}\n\nData Summary Used:\n{data_summary_string}\n\nBedrock Response:\n{generated_text}"
        s3_client.put_object(
            Bucket=TARGET_S3_BUCKET, Key=target_s3_key,
            Body=log_content.encode('utf-8'), ContentType='text/plain; charset=utf-8'
        )
        print(f"Successfully saved QA log to S3: {target_s3_key}")
    except Exception as e:
        print(f"Warning: Failed to save QA log to S3: {e}")


    # --- 5. 回傳結果給 API Gateway (邏輯不變) ---
    print("Lambda function finished. Returning response to API Gateway.")
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps({
            'answer': generated_text
        })
    }
# END OF UPDATED CODE for hackathonAIReportGenerator (Python - Fetch ALL measures)