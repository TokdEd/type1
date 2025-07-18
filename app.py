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

    rounded_time = round_time_to_half_hour(current_time)
    print("查詢時段:", rounded_time)

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
    system_content = "根據目前位置、時間與歷史人流，判斷先去哪個地點較佳並說明原因。僅在使用者需求明確時提供建議；若不明確，先提問釐清。所有回應務必精簡直接，省略贅詞，只提供結論與原因或精簡提問。"
    if custom_prompt:
        system_content += f" 額外要求：{custom_prompt}"
    
    payload = {
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": ai_prompt}
        ],
        "max_tokens": 1024,
        "temperature": 1.0
    }
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
    # 接收前端傳來的用戶位置參數
    user_lat = request.args.get('lat', type=float)
    user_lon = request.args.get('lon', type=float)
    # 接收時間參數，格式為 HH:MM:SS，預設為當前時間
    query_time = request.args.get('time', None)
    
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
        except:
            current_time = get_current_time_for_query()
    
    print(f"查詢時間: {current_time}")
    
    # 計算5天前的日期
    five_days_ago = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    
    # 查詢每個地點的指定時間平均人流量和整體平均人流量（最近5天）
    cur.execute("""
        SELECT 
            location,
            latitude,
            longitude,
            AVG(CASE WHEN time = %s THEN person_count END) as current_avg,
            AVG(person_count) as overall_avg,
            COUNT(CASE WHEN time = %s THEN 1 END) as current_data_count,
            COUNT(*) as overall_data_count
        FROM people_flow 
        WHERE date >= %s
        GROUP BY location, latitude, longitude
        HAVING COUNT(CASE WHEN time = %s THEN 1 END) >= 1  -- 降低門檻，至少要有1筆資料
    """, (current_time, current_time, five_days_ago, current_time))
    
    rows = cur.fetchall()
    cur.close()
    
    data = []
    for row in rows:
        location, lat, lon, current_avg, overall_avg, current_data_count, overall_data_count = row
        
        # 如果沒有當前時間的資料，跳過
        if current_avg is None:
            continue
            
        # 計算對比值
        comparison_ratio = get_level_by_comparison(current_avg, overall_avg)
        
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
    
    print(f"回傳資料筆數: {len(data)}, 查詢時間: {current_time}")
    return jsonify(data)

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






