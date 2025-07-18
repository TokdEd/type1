# type1
## preview project 
### add .env file 
fill this :
```
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_KEY
AZURE_MAPS_KEY
DB_USER
DB_PASS
DB_HOST
DB_PORT
DB_NAME
```
### launch ur owned postgre DB
### insert the exp data 
```
pip install requirements.txt 
python init_db.py
python postgre.py
```
### launch backend service 
```
gunicorn --bind 127.0.0.1:8000 app:app --reload
```
### preview 
127.0.0.1:8000