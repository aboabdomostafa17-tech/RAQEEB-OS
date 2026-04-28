import face_recognition
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import os
import requests
import pygame
import threading
import time

# --- الإعدادات ---
BOT_TOKEN = "8768459849:AAE1T_z3JHFIi8CD3AzwFNr_1fPps6usS8g"
CHAT_ID = "6558822537"
KNOWN_FACES_DIR = "known_face"
ALARM_FILE = "alarm.mp3"
EXCEL_FILE = "attendance.xlsx"

pygame.mixer.init()
if os.path.exists(ALARM_FILE):
    pygame.mixer.music.load(ALARM_FILE)

# متغيرات تتبع الحالة
active_now = {}  
last_alarm_time = 0

# --- دالة الإنذار وتليجرام ---
def trigger_alarm_async(frame, name):
    global last_alarm_time
    current_time = time.time()
    if current_time - last_alarm_time > 30:
        last_alarm_time = current_time
        def play_sound():
            try: pygame.mixer.music.play()
            except: pass
        threading.Thread(target=play_sound).start()
        
        _, img_encoded = cv2.imencode('.jpg', frame)
        files = {'photo': ('intruder.jpg', img_encoded.tobytes())}
        msg = f"⚠️ تحذير أمني: رصد {name}!\nالوقت: {datetime.now().strftime('%H:%M:%S')}"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto?chat_id={CHAT_ID}&caption={msg}", files=files)

# --- دالة تسجيل الإكسيل ---
def log_to_excel(name, status):
    try:
        data = {'Name': [name], 'Status': [status], 'Time': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]}
        df_new = pd.DataFrame(data)
        if os.path.exists(EXCEL_FILE):
            df_old = pd.read_excel(EXCEL_FILE)
            df_final = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df_final = df_new
        df_final.to_excel(EXCEL_FILE, index=False)
        print(f"✅ تم تسجيل {status}: {name}")
    except PermissionError:
        print("⚠️ خطأ: اقفل ملف الإكسيل عشان البرنامج يقدر يسجل البيانات!")

# --- تحميل الصور المعروفة ---
known_encodings = []
known_names = []
print("⏳ جاري تحميل صور الوجوه...")
for file in os.listdir(KNOWN_FACES_DIR):
    if file.endswith((".jpg", ".png")):
        img = face_recognition.load_image_file(f"{KNOWN_FACES_DIR}/{file}")
        encs = face_recognition.face_encodings(img)
        if len(encs) > 0:
            known_encodings.append(encs[0])
            known_names.append(os.path.splitext(file)[0])
print(f"🚀 النظام جاهز الآن.")

# --- التشغيل الرئيسي ---
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if not ret: break
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    
    current_names = []
    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
        name = "Unknown"
        if True in matches:
            name = known_names[matches.index(True)]
        
        current_names.append(name)
        
        if name == "Unknown":
            trigger_alarm_async(frame, "شخص غريب")
        
        if name not in active_now:
            active_now[name] = True
            log_to_excel(name, "Entry")

    # كشف الخروج
    for name in list(active_now.keys()):
        if name not in current_names:
            active_now.pop(name)
            log_to_excel(name, "Exit")

    # رسم النتائج
    for (top, right, bottom, left), name in zip(face_locations, current_names):
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imshow('Security System', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()