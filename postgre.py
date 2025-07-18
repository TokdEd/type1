import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os 
load_dotenv()
# 設定資料庫連線字串（根據你的情況調整）
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")  # 如果沒設密碼可留空，否則填入
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")

# 建立連線引擎
engine = create_engine(f'postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')

# 讀取 CSV 檔案
df = pd.read_csv('data/data_new.csv')

# 修正時間與日期欄位格式
df['date'] = pd.to_datetime(df['date']).dt.date
df['time'] = pd.to_datetime(df['time'], format='%H:%M').dt.time

# 匯入資料至 PostgreSQL 的 people_flow 資料表
df.to_sql('people_flow', engine, if_exists='append', index=False)

print("appended")