import psycopg2
import csv
import os
from dotenv import load_dotenv
from datetime import datetime

# 載入環境變數
load_dotenv()

def import_location_csv_to_db(csv_file_path):
    """
    匯入 CSV 檔案到 people_flow 資料表
    支援多種 CSV 格式變化：
    
    經緯度欄位順序：
    1. location,longitude,latitude,date,time,person_count (經度在前)
    2. location,latitude,longitude,date,time,person_count (緯度在前)
    
    時間格式：
    - HH:MM (如: 08:30) - 自動轉換為 HH:MM:SS
    - HH:MM:SS (如: 08:30:00) - 直接使用
    
    日期格式：
    - YYYY/MM/DD (如: 2025/07/13) - 自動轉換為 YYYY-MM-DD
    - YYYY-MM-DD (如: 2025-07-13) - 直接使用
    
    編碼支援：
    - UTF-8 with BOM
    - UTF-8 without BOM
    
    資料表格式：location, latitude, longitude, date, time, person_count
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
        
        # 讀取 CSV 檔案，先檢查檔頭格式
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:  # 使用 utf-8-sig 處理 BOM
            # 讀取第一行檢查欄位順序
            first_line = file.readline().strip()
            print(f"CSV 檔頭：{first_line}")
            
            # 重新定位到檔案開頭
            file.seek(0)
            
            csv_reader = csv.DictReader(file)
            
            # 檢查欄位順序
            fieldnames = csv_reader.fieldnames
            print(f"偵測到的欄位：{fieldnames}")
            
            # 判斷經緯度欄位順序
            if 'longitude' in fieldnames and 'latitude' in fieldnames:
                # 檢查經度和緯度在欄位中的位置
                lon_index = fieldnames.index('longitude')
                lat_index = fieldnames.index('latitude')
                
                if lon_index < lat_index:
                    print("偵測格式：經度在前，緯度在後 (longitude,latitude)")
                    coord_format = "lon_first"
                else:
                    print("偵測格式：緯度在前，經度在後 (latitude,longitude)")
                    coord_format = "lat_first"
            else:
                raise ValueError("CSV 檔案缺少必要的經緯度欄位")
            
            inserted_count = 0
            error_count = 0
            
            for row_num, row in enumerate(csv_reader, start=2):  # 從第2行開始（第1行是標題）
                try:
                    # 直接使用欄位名稱讀取資料
                    location = row['location'].strip()
                    
                    # 根據偵測的格式正確讀取經緯度
                    if coord_format == "lon_first":
                        # longitude,latitude 格式
                        longitude = float(row['longitude'])
                        latitude = float(row['latitude'])
                    else:
                        # latitude,longitude 格式
                        latitude = float(row['latitude'])
                        longitude = float(row['longitude'])
                    
                    date_str = row['date'].strip()
                    time_str = row['time'].strip()
                    person_count = int(row['person_count'])
                    
                    # 日期格式檢查和轉換
                    if '/' in date_str:
                        # 如果是 2025/07/13 格式，轉換為 2025-07-13
                        date_obj = datetime.strptime(date_str, '%Y/%m/%d').date()
                    else:
                        # 如果已經是 2025-07-13 格式
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    
                    # 時間格式檢查和標準化
                    if ':' not in time_str:
                        raise ValueError(f"時間格式錯誤，缺少冒號：{time_str}")
                    
                    time_parts = time_str.split(':')
                    if len(time_parts) == 2:  # HH:MM 格式
                        # 驗證時間格式
                        hour, minute = int(time_parts[0]), int(time_parts[1])
                        if 0 <= hour <= 23 and 0 <= minute <= 59:
                            time_str = f"{hour:02d}:{minute:02d}:00"  # 轉為 HH:MM:SS
                        else:
                            raise ValueError(f"時間數值超出範圍：{time_str}")
                    elif len(time_parts) == 3:  # HH:MM:SS 格式
                        # 驗證時間格式
                        hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
                        if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                            time_str = f"{hour:02d}:{minute:02d}:{second:02d}"  # 標準化格式
                        else:
                            raise ValueError(f"時間數值超出範圍：{time_str}")
                    else:
                        raise ValueError(f"時間格式錯誤，不支援的格式：{time_str}")
                    
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
                        
                except KeyError as e:
                    print(f"第 {row_num} 行缺少必要欄位 {e}：{row}")
                    error_count += 1
                    continue
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
            print(f"  {row[0]} | 緯度:{row[1]}, 經度:{row[2]} | {row[3]} {row[4]} | {row[5]}人")
        
        # 顯示地點統計
        cur.execute("""
            SELECT location, COUNT(*) as count
            FROM people_flow 
            WHERE id > (SELECT MAX(id) - %s FROM people_flow)
            GROUP BY location 
            ORDER BY count DESC
        """, (inserted_count,))
        location_stats = cur.fetchall()
        
        print(f"\n本次匯入的地點統計：")
        for location, count in location_stats:
            print(f"  {location}: {count} 筆")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"資料庫連線或匯入錯誤：{e}")

def preview_csv(csv_file_path, lines=5):
    """預覽 CSV 檔案內容"""
    print(f"預覽 CSV 檔案內容（前 {lines} 行）：")
    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:  # 使用 utf-8-sig 處理 BOM
            for i, line in enumerate(file):
                if i >= lines:
                    break
                print(f"  {i+1}: {line.strip()}")
    except Exception as e:
        print(f"無法讀取檔案：{e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法：")
        print("  python import_location_data.py <CSV檔案路徑>")
        print("  python import_location_data.py preview <CSV檔案路徑>  # 預覽檔案")
        print("\nCSV 格式：location,longitude,latitude,date,time,person_count")
        sys.exit(1)
    
    if sys.argv[1] == "preview" and len(sys.argv) > 2:
        preview_csv(sys.argv[2])
    else:
        csv_file = sys.argv[1]
        if os.path.exists(csv_file):
            # 先預覽檔案
            preview_csv(csv_file, 3)
            print()
            
            # 確認匯入
            confirm = input("確認要匯入這個檔案嗎？(y/N): ")
            if confirm.lower() in ['y', 'yes']:
                import_location_csv_to_db(csv_file)
            else:
                print("取消匯入")
        else:
            print(f"檔案不存在：{csv_file}") 