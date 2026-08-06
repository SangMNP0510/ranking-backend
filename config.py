import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, db

# URL Realtime Database của bạn
DATABASE_URL = os.getenv("DATABASE_URL", "https://ai-learning-app-40f76-default-rtdb.firebaseio.com/")

if not firebase_admin._apps:
    # 1. Kiểm tra xem có biến môi trường FIREBASE_CONFIG trên Render không
    firebase_json_env = os.getenv("FIREBASE_CONFIG")
    
    if firebase_json_env:
        # Nếu chạy trên Render
        cred_dict = json.loads(firebase_json_env)
        cred = credentials.Certificate(cred_dict)
    else:
        # Nếu chạy local bên dưới máy
        CRED_PATH = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
        cred = credentials.Certificate(CRED_PATH)
        
    firebase_admin.initialize_app(cred, {
        'databaseURL': DATABASE_URL
    })

db_firestore = firestore.client()
db_realtime = db.reference()