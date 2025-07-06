import pandas as pd
import matplotlib.pyplot as plt
import os
import matplotlib.font_manager as fm

# 設定中文字體（macOS）
plt.rc('font', family='Heiti TC')  # 可換成 'PingFang TC'、'Arial Unicode MS'

# 讀入資料
data_path = 'data/data.csv'
df = pd.read_csv(data_path)

# 建立 datetime 欄位
df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
df['time_only'] = pd.to_datetime(df['time'], format='%H:%M').dt.time  # 僅取時間部分

# 確保輸出資料夾存在
output_dir = 'output_plots'
os.makedirs(output_dir, exist_ok=True)

# ✅ 每日人潮圖
for date, date_df in df.groupby('date'):
    plt.figure(figsize=(12, 6))
    for location, group in date_df.groupby('location'):
        group = group.sort_values(by='datetime')
        plt.plot(group['time'], group['person_count'], marker='o', label=location)
    
    plt.title(f'{date} 各地點人潮變化', fontsize=16)
    plt.xlabel('時間', fontsize=12)
    plt.ylabel('人數', fontsize=12)
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    filename = f'{output_dir}/{date}_人潮變化圖.png'
    plt.savefig(filename)
    plt.close()
    print(f"✅ 已儲存圖表：{filename}")

# ✅ 每個地點的「時間平均」人潮圖
plt.figure(figsize=(12, 6))

# 計算：每個地點、每個時間（例如 14:00）的人數平均值
avg_df = df.groupby(['location', 'time_only'])['person_count'].mean().reset_index()

# 將時間轉為字串作為 x 軸
avg_df['time_str'] = avg_df['time_only'].apply(lambda t: t.strftime('%H:%M'))

# 畫圖：每個地點一條線
for location, group in avg_df.groupby('location'):
    plt.plot(group['time_str'], group['person_count'], marker='o', label=location)

plt.title('每個地點的平均人潮變化圖（依時間）', fontsize=16)
plt.xlabel('時間', fontsize=12)
plt.ylabel('平均人數', fontsize=12)
plt.xticks(rotation=45)
plt.legend()
plt.grid(True)
plt.tight_layout()

# 儲存圖檔
avg_plot_path = f'{output_dir}/每個地點_平均人潮變化圖.png'
plt.savefig(avg_plot_path)
plt.close()
print(f"✅ 已儲存平均人潮變化圖：{avg_plot_path}")