from flask import Flask, request, jsonify, send_from_directory
import requests
from flask_cors import CORS
import os
from dotenv import load_dotenv
import psycopg2
from datetime import datetime, timedelta
import math

# 強制重新載入
load_dotenv(override=True)
app = Flask(__name__)
CORS(app)

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
"""""
print("AZURE_OPENAI_ENDPOINT:", repr(os.getenv("AZURE_OPENAI_ENDPOINT")))
print("AZURE_OPENAI_KEY:", repr(os.getenv("AZURE_OPENAI_KEY")))
print("AZURE_MAPS_KEY:", repr(os.getenv("AZURE_MAPS_KEY")))
"""""
# PostgreSQL 連線設定
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)
print("連線成功！")
def round_time_to_half_hour(time_str):
    # 輸入 "14:17"，輸出 "14:00:00" 或 "14:30:00"
    h, m = map(int, time_str.split(':'))
    if m < 30:
        m = 0
    else:
        m = 30
    return f'{h:02d}:{m:02d}:00'

@app.route('/api/ask', methods=['POST'])
def ask():
    data = request.json
    prompt = data.get('prompt', '')
    locations = data.get('locations', [])  # 前端直接傳來所有地名
    current_location = data.get('current_location', {})
    current_time = data.get('current_time', '')
    custom_prompt = data.get('custom_prompt', '')  # 新增：接收客製化提示詞
    chat_history = data.get('chat_history', [])  # 新增：接收對話歷史

    rounded_time = round_time_to_half_hour(current_time)
    print("查詢時段:", rounded_time)
    print("對話歷史長度:", len(chat_history))

    cur = conn.cursor()
    
    # 如果有使用者位置，篩選最近的 10 個地點
    filtered_locations = locations
    if current_location and 'lat' in current_location and 'lon' in current_location:
        user_lat = current_location['lat']
        user_lon = current_location['lon']
        
        # 取得所有地點的座標資料
        cur.execute("""
            SELECT DISTINCT location, latitude, longitude
            FROM people_flow
            WHERE location = ANY(%s)
        """, (locations,))
        location_coords = cur.fetchall()
        
        # 計算距離並排序
        locations_with_distance = []
        for location, lat, lon in location_coords:
            if lat is not None and lon is not None:
                # 計算歐氏距離：sqrt((x1-x2)^2 + (y1-y2)^2)
                distance = math.sqrt((user_lat - lat)**2 + (user_lon - lon)**2)
                locations_with_distance.append((location, distance))
        
        # 按距離排序，只取前 10 個
        locations_with_distance.sort(key=lambda x: x[1])
        filtered_locations = [loc[0] for loc in locations_with_distance[:10]]
        
        print(f"使用者位置: ({user_lat}, {user_lon})")
        print(f"篩選後地點 (前10近): {filtered_locations}")
    
    historic_data = {}
    for loc in filtered_locations:
        cur.execute("""
            SELECT date, person_count
            FROM people_flow
            WHERE location = %s AND time = %s
            ORDER BY date DESC
            LIMIT 7
        """, (loc, rounded_time))
        rows = cur.fetchall()
        historic_data[loc] = [{"date": str(row[0]), "person_count": row[1]} for row in rows]
    cur.close()
    print("查詢到的歷史人流資料:", historic_data)

    # 組合 prompt 給 AI
    ai_prompt = f"""使用者目前位置：{current_location}
目前時間：{current_time}（查詢歷史資料時段：{rounded_time}）
使用者需求：{prompt}
歷史人流資料（已篩選距離最近的地點）："""
    for loc in filtered_locations:
        ai_prompt += f"\n地點 {loc}："
        for record in historic_data[loc]:
            ai_prompt += f"{record['date']} {rounded_time} 人數：{record['person_count']}；"
    
    # 新增：如果有客製化提示詞，加入到 prompt 中
    if custom_prompt:
        ai_prompt += f"\n\n客製化要求：{custom_prompt}"
    
    ai_prompt += "根據目前位置、時間與歷史人流，判斷先去哪個地點較佳並說明原因。僅在使用者需求明確時提供建議；若不明確，先提問釐清。所有回應務必精簡直接，省略贅詞，只提供結論與原因或精簡提問。"

    print("送給AI的最終prompt：\n", ai_prompt)

    # 6. 呼叫 Azure OpenAI
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_KEY
    }
    
    # 修改系統提示詞，如果有客製化提示詞則整合進去
    system_content = """你是一個人潮雷達助手，能夠根據目前位置、時間與歷史人流資料，判斷先去哪個地點較佳並說明原因。

重要能力說明：
1. 你可以看到並參考之前的對話歷史，提供連續性的對話體驗
2. 當用戶詢問你是否能看到上下文或對話歷史時，請回答「是」
3. 你應該參考歷史對話來理解用戶的完整需求和偏好

語言理解重點：
- 當用戶說"他亮紅燈"時，"他"指的是你剛才推薦的地點，"亮紅燈"表示該地點人潮很多
- 當用戶使用"它"、"那裡"、"那個地方"等代詞時，通常指代之前討論的地點
- 根據地圖顏色：紅燈=人很多，黃燈=人中等，綠燈=人較少

回應原則：
- 僅在使用者需求明確時提供建議；若不明確，先提問釐清
- 所有回應務必精簡直接，省略贅詞，只提供結論與原因或精簡提問
- 主動參考之前的對話來提供更好的建議
- 理解代詞指代，提供連貫的對話體驗"""

    if custom_prompt:
        system_content += f"\n\n額外要求：{custom_prompt}"
    
    # 構建包含對話歷史的訊息陣列
    messages = [{"role": "system", "content": system_content}]
    
    # 添加對話歷史（如果有的話）
    if chat_history:
        print(f"添加 {len(chat_history)} 條對話歷史到上下文")
        
        # 更明確的上下文說明
        context_intro = {
            "role": "system", 
            "content": f"""以下是與用戶的歷史對話記錄（共 {len(chat_history)} 條），請仔細閱讀並記住：

重要提醒：
- 當用戶說"他亮紅燈"或類似詞語時，通常指的是你剛才推薦的地點目前人潮很多
- 用戶可能會用代詞（他、它、那裡）來指代之前討論的地點
- 請根據完整的對話脈絡來理解用戶的需求

歷史對話開始："""
        }
        messages.append(context_intro)
        messages.extend(chat_history)
        
        # 更明確的分隔說明
        context_separator = {
            "role": "system",
            "content": """歷史對話結束。

現在用戶有新的詢問，請結合上述歷史對話來理解：
- 如果用戶提到"他/它/那裡亮紅燈"，指的是之前推薦的地點現在人很多
- 如果用戶使用代詞，請聯繫上下文理解指的是什麼
- 提供連貫性的建議

當前新詢問："""
        }
        messages.append(context_separator)
    
    # 添加當前用戶訊息
    messages.append({"role": "user", "content": ai_prompt})
    
    payload = {
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 1.0
    }
    
    print("發送給AI的完整訊息陣列長度:", len(messages))
    
    r = requests.post(AZURE_OPENAI_ENDPOINT, headers=headers, json=payload)
    try:
        result = r.json()
        reply = result['choices'][0]['message']['content'] if 'choices' in result else 'AI 沒有回應'
    except Exception as e:
        reply = f'API 回傳錯誤: {str(e)}'
    return jsonify({"reply": reply})

def get_current_time_for_query():
    now = datetime.now()
    minute = now.minute
    
    # 計算距離當前小時0分和30分的時間差
    distance_to_zero = minute
    distance_to_thirty = abs(minute - 30)
    
    # 計算距離下一個小時0分的時間差（跨小時情況）
    distance_to_next_zero = 60 - minute
    
    # 選擇距離最近的時間點
    if distance_to_zero <= distance_to_thirty and distance_to_zero <= distance_to_next_zero:
        # 距離當前小時0分最近
        hour = now.hour
        minute = 0
    elif distance_to_thirty <= distance_to_next_zero:
        # 距離當前小時30分最近
        hour = now.hour
        minute = 30
    else:
        # 距離下一個小時0分最近
        if now.hour == 23:
            hour = 0
        else:
            hour = now.hour + 1
        minute = 0
    
    return f"{hour:02d}:{minute:02d}:00"

@app.route('/api/checkpoints')
def get_checkpoints():
    try:
        # 接收前端傳來的用戶位置參數
        user_lat = request.args.get('lat', type=float)
        user_lon = request.args.get('lon', type=float)
        # 接收時間參數，格式為 HH:MM:SS，預設為當前時間
        query_time = request.args.get('time', None)
        
        print(f"🔍 API調用 - 位置: {user_lat}, {user_lon}, 時間: {query_time}")
        
        cur = conn.cursor()
        
        # 如果沒有指定時間，使用當前時間邏輯
        if query_time is None:
            current_time = get_current_time_for_query()
        else:
            # 驗證時間格式並標準化
            try:
                # 確保時間格式為 HH:MM:SS
                if len(query_time.split(':')) == 2:  # HH:MM 格式
                    query_time += ':00'
                current_time = query_time
            except Exception as time_error:
                print(f"⚠️ 時間格式錯誤: {time_error}")
                current_time = get_current_time_for_query()
        
        print(f"查詢時間: {current_time}")
        
        # 計算5天前的日期
        five_days_ago = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        print(f"查詢日期範圍: {five_days_ago} 到今天")
        
        # 查詢每個地點的指定時間平均人流量和整體平均人流量（最近5天）
        sql_query = """
            SELECT 
                location,
                latitude,
                longitude,
                AVG(CASE WHEN time = %s THEN person_count END) as current_avg,
                AVG(person_count) as overall_avg,
                COUNT(CASE WHEN time = %s THEN 1 END) as current_data_count,
                COUNT(*) as overall_data_count
            FROM people_flow 
            WHERE date >= %s AND latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY location, latitude, longitude
            HAVING COUNT(CASE WHEN time = %s THEN 1 END) >= 1  -- 降低門檻，至少要有1筆資料
        """
        
        print("🔍 執行資料庫查詢...")
        cur.execute(sql_query, (current_time, current_time, five_days_ago, current_time))
        
        rows = cur.fetchall()
        print(f"查詢結果: {len(rows)} 個地點")
        cur.close()
        
        data = []
        for row in rows:
            location, lat, lon, current_avg, overall_avg, current_data_count, overall_data_count = row
            
            # 如果沒有當前時間的資料，跳過
            if current_avg is None:
                print(f"⚠️ {location} 沒有 {current_time} 的資料")
                continue
                
            # 計算對比值
            try:
                comparison_ratio = get_level_by_comparison(current_avg, overall_avg)
            except Exception as comp_error:
                print(f"⚠️ 計算對比值錯誤 {location}: {comp_error}")
                comparison_ratio = 0
            
            data.append({
                "id": len(data) + 1,
                "name": location,
                "lat": lat,
                "lon": lon,
                "person_count": int(current_avg),
                "level": "dynamic",  # 改為 dynamic 表示使用動態顏色
                "avg_count": int(current_avg),
                "overall_avg": int(overall_avg),
                "current_data_count": current_data_count,
                "overall_data_count": overall_data_count,
                "comparison_ratio": float(comparison_ratio),  # 轉換為 float 避免 Decimal 問題
                "distance": None,  # 預設距離為 None
                "query_time": current_time  # 回傳查詢時間
            })
        
        print(f"✅ 處理了 {len(data)} 個有效地點")
        
        # 如果有用戶位置，計算距離並篩選最近的10個地點
        if user_lat is not None and user_lon is not None:
            print(f"用戶位置: ({user_lat}, {user_lon})")
            
            # 計算每個地點與用戶的距離
            for item in data:
                if item['lat'] is not None and item['lon'] is not None:
                    # 計算歐氏距離：sqrt((x1-x2)^2 + (y1-y2)^2)
                    distance = math.sqrt((user_lat - item['lat'])**2 + (user_lon - item['lon'])**2)
                    item['distance'] = distance
            
            # 過濾掉沒有座標的地點，按距離排序，只取前10個
            data_with_coords = [item for item in data if item['distance'] is not None]
            data_with_coords.sort(key=lambda x: x['distance'])
            data = data_with_coords[:10]
            
            print(f"篩選後地點 (最近10個): {[item['name'] for item in data]}")
        else:
            print("沒有提供用戶位置，顯示所有地點")
        
        # 重新分配 ID
        for i, item in enumerate(data):
            item['id'] = i + 1
        
        print(f"✅ 回傳資料筆數: {len(data)}, 查詢時間: {current_time}")
        return jsonify(data)
        
    except Exception as e:
        print(f"❌ /api/checkpoints 錯誤: {e}")
        print(f"錯誤類型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.route('/api/azure-maps-key')
def get_azure_maps_key():
    return jsonify({"key": os.getenv("AZURE_MAPS_KEY")})

@app.route('/')
def index():
    return send_from_directory('.', 'map_test.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

def get_level_by_avg(avg_count):
    if avg_count >= 30:
        return 'high'    # 紅色
    elif avg_count >= 20:
        return 'mid'     # 黃色
    elif avg_count >= 10:
        return 'low'     # 綠色
    else:
        return 'very_low'  # 深綠色（可選）

def get_level_by_comparison(current_avg, overall_avg):
    """
    計算對比值，用於動態顏色調整
    回傳值範圍：-1 到 1
    -1: 當前遠低於整體平均
    0: 當前等於整體平均  
    1: 當前遠高於整體平均
    """
    if overall_avg == 0:
        return 0
    
    # 計算標準化對比值
    diff = current_avg - overall_avg
    # 使用整體平均作為標準化基準
    normalized_diff = diff / overall_avg
    
    # 限制在 -1 到 1 之間
    return max(-1, min(1, normalized_diff))

if __name__ == '__main__':
    app.run(port=5000,debug = True)






