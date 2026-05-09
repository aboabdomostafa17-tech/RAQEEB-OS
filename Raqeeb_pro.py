import customtkinter as ctk
import cv2
from PIL import Image
import face_recognition
import os
import pygame
import threading
import pandas as pd
from tkinter import filedialog, messagebox
from cryptography.fernet import Fernet
from datetime import datetime
import requests
from io import BytesIO
import time

# --- Encryption System ---
def get_crypto_key():
    if not os.path.exists("secure_vault.key"):
        key = Fernet.generate_key()
        with open("secure_vault.key", "wb") as f: f.write(key)
    return open("secure_vault.key", "rb").read()

cipher = Fernet(get_crypto_key())

class RaqeebUltraSync(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("RAQEEB-OS v5.1 | Final Pro Edition")
        self.geometry("1400x950")
        ctk.set_appearance_mode("dark")
        
        self.running = False
        self.camera_index = 0
        self.known_encs, self.known_names = [], []
        self.face_locs, self.face_names = [], []
        self.process_this_frame = True
        self.last_telegram_time = 0
        
        # Entrance/Exit Tracking
        self.present_people = {}  # {name: last_seen_timestamp}
        self.EXIT_THRESHOLD = 5    # Seconds before logging an exit
        
        pygame.mixer.init()
        self.load_encrypted_database()
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=300)
        self.sidebar.pack(side="left", fill="y", padx=5, pady=5)
        
        ctk.CTkLabel(self.sidebar, text="🛡️ RAQEEB-OS PRO", font=("Arial", 24, "bold")).pack(pady=10)

        # Telegram Setup
        ctk.CTkLabel(self.sidebar, text="Telegram Bot Token:", font=("Arial", 10)).pack()
        self.bot_token_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Token...", height=25)
        self.bot_token_entry.pack(pady=2, padx=20, fill="x")

        ctk.CTkLabel(self.sidebar, text="Telegram Chat ID:", font=("Arial", 10)).pack()
        self.chat_id_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Chat ID...", height=25)
        self.chat_id_entry.pack(pady=2, padx=20, fill="x")

        # Stats
        self.stats_box = ctk.CTkFrame(self.sidebar, fg_color="#1a1a1a")
        self.stats_box.pack(pady=10, padx=10, fill="x")
        self.allowed_label = ctk.CTkLabel(self.stats_box, text="ALLOWED: 0", font=("Arial", 20, "bold"), text_color="#2ecc71")
        self.allowed_label.pack(pady=2)
        self.unknown_label = ctk.CTkLabel(self.stats_box, text="UNKNOWN: 0", font=("Arial", 20, "bold"), text_color="#e74c3c")
        self.unknown_label.pack(pady=2)

        # Control
        self.start_btn = ctk.CTkButton(self.sidebar, text="START SYSTEM", fg_color="#2d8a4e", command=self.start)
        self.start_btn.pack(pady=5, padx=20, fill="x")
        self.stop_btn = ctk.CTkButton(self.sidebar, text="STOP SYSTEM", fg_color="#8a2d2d", command=self.stop)
        self.stop_btn.pack(pady=5, padx=20, fill="x")
        self.add_btn = ctk.CTkButton(self.sidebar, text="➕ Add User", command=self.add_user, fg_color="#1f538d")
        self.add_btn.pack(pady=5, padx=20, fill="x")

        # Log
        ctk.CTkLabel(self.sidebar, text="LIVE ACTIVITY LOG", font=("Arial", 12, "bold")).pack(pady=(10, 2))
        self.log_box = ctk.CTkTextbox(self.sidebar, width=260, height=200)
        self.log_box.pack(pady=5, padx=10)

        # NEW: Multi-Camera Button under Log
        self.cam_toggle_btn = ctk.CTkButton(self.sidebar, text="🔄 SWITCH CAMERA", fg_color="#5a5a5a", command=self.cycle_camera)
        self.cam_toggle_btn.pack(pady=10, padx=20, fill="x")

        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.pack(side="right", expand=True, fill="both", padx=10, pady=10)
        self.video_feed = ctk.CTkLabel(self.display_frame, text="SYSTEM OFFLINE", font=("Arial", 20))
        self.video_feed.pack(expand=True, fill="both")
    def log_event(self, name, event_type):
        """Logs Entry or Exit to Excel and UI"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M')}] {name}: {event_type}\n")
        self.log_box.see("end")
        
        filename = "activity_log.xlsx"
        try:
            df_new = pd.DataFrame([{"Timestamp": now, "Name": name, "Event": event_type}])
            if os.path.exists(filename):
                df_old = pd.read_excel(filename)
                pd.concat([df_old, df_new]).to_excel(filename, index=False)
            else:
                df_new.to_excel(filename, index=False)
        except: pass

    def cycle_camera(self):
        self.camera_index = (self.camera_index + 1) % 3 # Cycles 0, 1, 2
        if self.running:
            self.stop()
            self.start()

    def send_telegram_alert(self, frame):
        token, chat_id = self.bot_token_entry.get(), self.chat_id_entry.get()
        if not token or not chat_id: return
        def task():
            try:
                _, buffer = cv2.imencode('.jpg', frame)
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", 
                              files={'photo': ('alert.jpg', BytesIO(buffer), 'image/jpeg')},
                              data={'chat_id': chat_id, 'caption': "⚠️ UNKNOWN DETECTED!"})
            except: pass
        threading.Thread(target=task).start()

    def update_ui(self):
        if not self.running: return
        ret, frame = self.cap.read()
        if ret:
            current_time = time.time()
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            if self.process_this_frame:
                self.face_locs = face_recognition.face_locations(rgb_small_frame)
                face_encs = face_recognition.face_encodings(rgb_small_frame, self.face_locs)
                
                self.face_names = []
                seen_this_frame = []

                for enc in face_encs:
                    matches = face_recognition.compare_faces(self.known_encs, enc, 0.5)
                    name = "Unknown"
                    if True in matches:
                        name = self.known_names[matches.index(True)]
                    
                    self.face_names.append(name)
                    seen_this_frame.append(name)

                    # Entry Logic: If new person
                    if name not in self.present_people:
                        self.present_people[name] = current_time
                        self.log_event(name, "ENTERED")
                        if name == "Unknown":
                            if current_time - self.last_telegram_time > 15:
                                self.send_telegram_alert(frame)
                                self.last_telegram_time = current_time
                    else:
                        # Refresh their presence
                        self.present_people[name] = current_time

                # Exit Logic: Check who was seen before but isn't here now
                to_remove = []
                for name, last_seen in self.present_people.items():
                    if name not in seen_this_frame:
                        if current_time - last_seen > self.EXIT_THRESHOLD:
                            self.log_event(name, "EXITED")
                            to_remove.append(name)
                for name in to_remove: del self.present_people[name]

                if "Unknown" in self.face_names: self.play_alarm()
                else: self.stop_alarm()

            self.process_this_frame = not self.process_this_frame

            # UI Rendering
            for (top, right, bottom, left), name in zip(self.face_locs, self.face_names):
                top*=4; right*=4; bottom*=4; left*=4
                color = (46, 204, 113) if name != "Unknown" else (231, 76, 60)
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            self.allowed_label.configure(text=f"ALLOWED: {sum(1 for n in self.face_names if n != 'Unknown')}")
            self.unknown_label.configure(text=f"UNKNOWN: {self.face_names.count('Unknown')}")

            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            tk_img = ctk.CTkImage(img, size=(self.display_frame.winfo_width(), self.display_frame.winfo_height()))
            self.video_feed.configure(image=tk_img, text="")

        self.after(10, self.update_ui)

    # ... (Rest of internal methods: start, stop, play_alarm, load_encrypted_database, add_user remain same) ...
    def play_alarm(self):
        if not pygame.mixer.music.get_busy() and os.path.exists("alarm.mp3"):
            pygame.mixer.music.load("alarm.mp3"); pygame.mixer.music.play(-1)
    def stop_alarm(self):
        if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
    def load_encrypted_database(self):
        self.known_encs, self.known_names = [], []
        if not os.path.exists("vault"): os.makedirs("vault")
        for f in os.listdir("vault"):
            if f.endswith(".crypt"):
                try:
                    with open(f"vault/{f}", "rb") as ef:
                        data = cipher.decrypt(ef.read())
                        with open("t.jpg", "wb") as t: t.write(data)
                        img = face_recognition.load_image_file("t.jpg")
                        enc = face_recognition.face_encodings(img)
                        if enc: self.known_encs.append(enc[0]); self.known_names.append(f.split('.')[0])
                    if os.path.exists("t.jpg"): os.remove("t.jpg")
                except: continue
    def add_user(self):
        path = filedialog.askopenfilename()
        if path:
            name = ctk.CTkInputDialog(text="Name:", title="Register").get_input()
            if name:
                with open(path, "rb") as f:
                    with open(f"vault/{name}.crypt", "wb") as ef: ef.write(cipher.encrypt(f.read()))
                self.load_encrypted_database()
                messagebox.showinfo("Success", "User Added!")
    def start(self):
        if not self.running:
            self.cap = cv2.VideoCapture(self.camera_index)
            if self.cap.isOpened(): self.running = True; self.update_ui()
    def stop(self):
        self.running = False; self.stop_alarm()
        if hasattr(self, 'cap'): self.cap.release()
        self.video_feed.configure(image="", text="SYSTEM OFFLINE")

if __name__== "__main__":
    app = RaqeebUltraSync()
    app.mainloop()
        
   