import psycopg2
import os
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 連接到 Supabase
try:
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )
    
    cur = conn.cursor()
    
    print("成功連接到 Supabase！")
    
    # 建立 people_flow 資料表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS people_flow (
        id SERIAL PRIMARY KEY,
        location TEXT NOT NULL,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        date DATE,
        time TIME,
        person_count INTEGER
    );
    """
    
    cur.execute(create_table_sql)
    conn.commit()
    
    print("people_flow 資料表建立成功！")
    
    # 檢查資料表結構
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'people_flow'
        ORDER BY ordinal_position;
    """)
    
    columns = cur.fetchall()
    print("\n資料表結構：")
    for column in columns:
        print(f"  {column[0]}: {column[1]}")
    
    # 檢查資料筆數
    cur.execute("SELECT COUNT(*) FROM people_flow;")
    count = cur.fetchone()[0]
    print(f"\n目前資料筆數: {count}")
    
    cur.close()
    conn.close()
    
    print("\n資料庫初始化完成！")
    
except Exception as e:
    print(f"錯誤: {e}") 