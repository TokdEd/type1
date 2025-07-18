import psycopg2
import csv
import os
from dotenv import load_dotenv
from datetime import datetime

# 載入環境變數
load_dotenv()

def import_csv_to_db(csv_file_path):
    """
    匯入 CSV 資料到 people_flow 資料表
    CSV 格式：種類,名稱,經度,緯度,日期,時間,排隊人數
    資料表格式：location, longitude, latitude, date, time, person_count
    """
    
    # 連接到資料庫
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        cur = conn.cursor()
        print("成功連接到資料庫！")
        
        # 讀取 CSV 檔案
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            
            # 跳過標題行（如果有的話）
            first_row = next(csv_reader, None)
            if first_row and '種類' in first_row[0]:
                print("跳過標題行")
            else:
                # 如果第一行是資料，重新定位到檔案開始
                file.seek(0)
                csv_reader = csv.reader(file)
            
            inserted_count = 0
            error_count = 0
            
            for row_num, row in enumerate(csv_reader, start=1):
                try:
                    if len(row) < 7:
                        print(f"第 {row_num} 行資料不完整，跳過：{row}")
                        error_count += 1
                        continue
                    
                    # 解析資料（跳過第一欄種類）
                    category = row[0]       # 種類（不使用）
                    location = row[1]       # 名稱
                    longitude = float(row[2])  # 經度
                    latitude = float(row[3])   # 緯度
                    date_str = row[4]       # 日期
                    time_str = row[5]       # 時間
                    person_count = int(row[6])  # 排隊人數
                    
                    # 轉換日期格式：2025/07/13 -> 2025-07-13
                    date_obj = datetime.strptime(date_str, '%Y/%m/%d').date()
                    
                    # 轉換時間格式：07:30 -> 07:30:00
                    if len(time_str) == 5:  # HH:MM
                        time_str += ':00'   # HH:MM:SS
                    
                    # 插入資料庫
                    insert_sql = """
                    INSERT INTO people_flow (location, latitude, longitude, date, time, person_count)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    
                    cur.execute(insert_sql, (
                        location, 
                        latitude, 
                        longitude, 
                        date_obj, 
                        time_str, 
                        person_count
                    ))
                    
                    inserted_count += 1
                    
                    if inserted_count % 100 == 0:
                        print(f"已插入 {inserted_count} 筆資料...")
                        
                except ValueError as e:
                    print(f"第 {row_num} 行資料格式錯誤：{e}")
                    print(f"資料內容：{row}")
                    error_count += 1
                    continue
                except Exception as e:
                    print(f"第 {row_num} 行插入失敗：{e}")
                    print(f"資料內容：{row}")
                    error_count += 1
                    continue
        
        # 提交所有變更
        conn.commit()
        
        print(f"\n=== 匯入完成 ===")
        print(f"成功插入：{inserted_count} 筆")
        print(f"錯誤筆數：{error_count} 筆")
        
        # 檢查資料庫總筆數
        cur.execute("SELECT COUNT(*) FROM people_flow")
        total_count = cur.fetchone()[0]
        print(f"資料庫總筆數：{total_count} 筆")
        
        # 顯示最新插入的幾筆資料
        cur.execute("""
            SELECT location, latitude, longitude, date, time, person_count 
            FROM people_flow 
            ORDER BY id DESC 
            LIMIT 5
        """)
        latest_rows = cur.fetchall()
        
        print(f"\n最新 5 筆資料：")
        for row in latest_rows:
            print(f"  {row[0]} | {row[1]}, {row[2]} | {row[3]} {row[4]} | {row[5]}人")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"資料庫連線或匯入錯誤：{e}")

def create_sample_csv():
    """建立範例 CSV 檔案供測試"""
    sample_data = [
        "種類,名稱,經度,緯度,日期,時間,排隊人數",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,07:30,0",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,08:00,17",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,08:30,10",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,09:00,24",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,09:30,21",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,10:00,7",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,10:30,0",
        "餐廳,餓了,120.214728,22.9939,2025/07/13,11:00,8"
    ]
    
    with open('sample_data.csv', 'w', encoding='utf-8') as f:
        f.write('\n'.join(sample_data))
    
    print("已建立範例檔案：sample_data.csv")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法：")
        print("  python import_data.py <CSV檔案路徑>")
        print("  python import_data.py sample    # 建立範例檔案")
        print("\nCSV 格式：種類,名稱,經度,緯度,日期,時間,排隊人數")
        sys.exit(1)
    
    if sys.argv[1] == "sample":
        create_sample_csv()
    else:
        csv_file = sys.argv[1]
        if os.path.exists(csv_file):
            import_csv_to_db(csv_file)
        else:
            print(f"檔案不存在：{csv_file}") 