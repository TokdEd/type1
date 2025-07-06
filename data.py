import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta

# 定義五個地點與隨機座標（模擬在同一所校園內）
locations = {
    "籃球場": (25.0421, 121.5350),
    "K館": (25.0425, 121.5345),
    "福利社": (25.0419, 121.5348),
    "販賣機1": (25.0422, 121.5349),
    "販賣機2": (25.0418, 121.5346)
}

# 設定資料區間與時間粒度
start_date = datetime(2025, 7, 1)
days = 5
interval_minutes = 30
records = []

# 為每個地點生成資料
for day in range(days):
    date = start_date + timedelta(days=day)
    for loc, (lat, lon) in locations.items():
        time = datetime.combine(date, datetime.min.time())
        for i in range(48):  # 每天48筆資料（每30分鐘）
            time_str = time.strftime('%H:%M')
            # 用常態分布模擬人數（福利社/販賣機小波動，K館/籃球場大波動）
            if "販賣機" in loc:
                count = max(0, int(np.random.normal(5, 2)))
            elif loc == "福利社":
                count = max(0, int(np.random.normal(10, 3)))
            else:
                count = max(0, int(np.random.normal(25, 10)))

            records.append({
                "location": loc,
                "latitude": lat,
                "longitude": lon,
                "date": date.strftime('%Y-%m-%d'),
                "time": time_str,
                "person_count": count
            })

            time += timedelta(minutes=interval_minutes)

# 轉成 DataFrame
df = pd.DataFrame(records)
df.head()
csv_path = "data/data.csv"
df.to_csv(csv_path, index=False)