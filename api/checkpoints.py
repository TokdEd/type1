import psycopg2
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)

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

def get_level_by_comparison(current_avg, overall_avg):
    """
    根據當前平均人流量與整體平均人流量的比較決定顏色
    """
    diff = current_avg - overall_avg
    
    if diff >= 0:
        return 'high'    # 紅色：當前 ≥ 整體平均
    elif abs(diff) <= 5:
        return 'mid'     # 黃色：當前 ≈ 整體平均（±5人）
    else:
        return 'low'     # 綠色：當前 < 整體平均

# 連線設定
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT")
)

@app.route('/api/checkpoints')
def get_checkpoints():
    cur = conn.cursor()
    
    # 使用新的時間計算邏輯
    current_time = get_current_time_for_query()
    print(f"查詢時間: {current_time}")
    
    # 計算5天前的日期
    five_days_ago = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    
    # 查詢每個地點的當前時間平均人流量和整體平均人流量（最近5天）
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
        HAVING COUNT(CASE WHEN time = %s THEN 1 END) >= 3  -- 當前時間至少要有3筆資料
    """, (current_time, current_time, five_days_ago, current_time))
    
    rows = cur.fetchall()
    cur.close()
    
    data = []
    for row in rows:
        location, lat, lon, current_avg, overall_avg, current_data_count, overall_data_count = row
        
        # 如果沒有當前時間的資料，跳過
        if current_avg is None:
            continue
            
        # 根據相對比較決定顏色
        level = get_level_by_comparison(current_avg, overall_avg)
        
        data.append({
            "id": len(data) + 1,
            "name": location,
            "lat": lat,
            "lon": lon,
            "person_count": int(current_avg),
            "level": level,
            "avg_count": int(current_avg),
            "overall_avg": int(overall_avg),
            "current_data_count": current_data_count,
            "overall_data_count": overall_data_count
        })
    
    print(f"回傳資料: {data}")  # Debug 輸出
    return jsonify(data)

if __name__ == '__main__':
    app.run(port=5000)