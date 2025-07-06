import pandas as pd
import matplotlib.pyplot as plt
import os

# 設定中文字體
plt.rc('font', family='Heiti TC')

# 讀資料
df = pd.read_csv('data/data.csv')
df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
df['time_only'] = pd.to_datetime(df['time'], format='%H:%M').dt.time

# 取得使用者輸入時間
target_time_input = input("請輸入欲分析的時段（例如 20:00）：").strip()
target_time = pd.to_datetime(target_time_input, format="%H:%M").time()

# 1. 各地點每日 target_time 的人數
df_target = df[df['time_only'] == target_time]
avg_target_per_location = df_target.groupby(['location', 'date'])['person_count'].mean().reset_index()
avg_target = avg_target_per_location.groupby('location')['person_count'].mean()

# 2. 各地點每日的平均人數（全天）
daily_avg = df.groupby(['location', 'date'])['person_count'].mean().reset_index()
overall_avg = daily_avg.groupby('location')['person_count'].mean()

# 3. 合併兩組資料
comparison_df = pd.DataFrame({
    f'{target_time_input} 平均人數': avg_target,
    '每日平均人數': overall_avg
}).dropna().sort_values(by=f'{target_time_input} 平均人數', ascending=False)

# 4. 畫圖：分組柱狀圖
plt.figure(figsize=(12, 6))
bar_width = 0.35
index = range(len(comparison_df))

plt.bar(index, comparison_df[f'{target_time_input} 平均人數'], width=bar_width, label=f'每日 {target_time_input} 平均')
plt.bar([i + bar_width for i in index], comparison_df['每日平均人數'], width=bar_width, label='每日全時段平均')

plt.xlabel('地點', fontsize=12)
plt.ylabel('人數', fontsize=12)
plt.title(f'各地點：每日 {target_time_input} 人數 vs 每日平均人數', fontsize=16)
plt.xticks([i + bar_width / 2 for i in index], comparison_df.index, rotation=45)
plt.legend()
plt.tight_layout()

# 5. 儲存圖片
output_dir = 'output_plots'
os.makedirs(output_dir, exist_ok=True)
filename = f'{output_dir}/地點_每日{target_time_input.replace(":", "")}vs平均人數.png'
plt.savefig(filename)
plt.close()
print(f"✅ 已儲存圖表：{filename}")