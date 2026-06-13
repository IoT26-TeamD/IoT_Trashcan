"""
스마트 쓰레기통 GUI 애플리케이션 (라즈베리파이 5)
-----------------------------------------------
하드웨어 구성 (BCM 핀 번호):
  - 초음파 센서 TRIG : GPIO 23
  - 초음파 센서 ECHO : GPIO 24
  - DHT11           : GPIO 4
  - LED (캔)        : GPIO 17
  - LED (플라스틱)  : GPIO 22
  - LED (종이)      : GPIO 27
  - LED (병)        : GPIO 5

서버 API:
  POST http://3.34.47.69/api/data
  GET  http://3.34.47.69/api/stats
모델: YOLOv26n Object Detection (best.pt)

GUI: tkinter 기반, LCD 모니터에 카메라 화면 · 분류 결과 · 분리수거 방법 · 통계 표시
"""

import os
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"

import tkinter as tk
from tkinter import font as tkfont
from PIL import Image, ImageTk
import cv2
import time
import threading
import requests
import numpy as np
from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import LED, DistanceSensor
import adafruit_dht
import board

# ══════════════════════════════════════════════
# 1. 설정 상수
# ══════════════════════════════════════════════
SERVER_URL      = "http://placeholder/api/data"
STATS_URL       = "http://placeholder/api/stats"
REQUEST_TIMEOUT = 1
DETECT_DISTANCE = 0.20       # 20cm
MODEL_PATH      = "./best.pt"
CONF_THRESHOLD  = 0.4
DHT_INTERVAL    = 2          # DHT11 권장 2초
LED_ON_DURATION = 3
STATS_INTERVAL  = 10         # 서버 통계 조회 주기 (초)
ENV_POST_INTERVAL = 60       # 온습도 주기적 서버 전송 (초, 1분)
FRAME_INTERVAL  = 50         # 프레임 갱신 주기 (ms, ~20fps)

CAM_W, CAM_H         = 640, 480     # 카메라 캡처 해상도
DISPLAY_W, DISPLAY_H = 520, 390   # 7인치 1024x600 디스플레이 최적화 (창모드 대비 축소)

# ── 색상 (다크 테마) ──
BG_DARK   = "#0d1117"
BG_CARD   = "#161b22"
BG_HEADER = "#1a2332"
FG_WHITE  = "#e6edf3"
FG_DIM    = "#8b949e"
FG_GREEN  = "#3fb950"
FG_ORANGE = "#d29922"
FG_RED    = "#f85149"
FG_BLUE   = "#58a6ff"
FG_PURPLE = "#bc8cff"

# ── Recycling Info ──
RECYCLE_INFO = {
    "can": {
        "name": "Can",
        "color": FG_ORANGE,
        "tips": [
            "1. Empty contents and rinse with water",
            "2. Crush to reduce volume",
            "3. Place in the CAN recycling bin",
        ],
    },
    "plastic": {
        "name": "Plastic",
        "color": FG_BLUE,
        "tips": [
            "1. Remove labels and caps",
            "2. Empty contents and rinse",
            "3. Compress and place in PLASTIC bin",
        ],
    },
    "paper": {
        "name": "Paper",
        "color": FG_GREEN,
        "tips": [
            "1. Remove tape and foreign materials",
            "2. Coated paper goes to general waste",
            "3. Fold and place in PAPER bin",
        ],
    },
    "bottle": {
        "name": "Glass Bottle",
        "color": FG_PURPLE,
        "tips": [
            "1. Remove the cap",
            "2. Empty contents and rinse",
            "3. Sort by color into GLASS bin",
        ],
    },
}

# ══════════════════════════════════════════════
# 2. 하드웨어 초기화
# ══════════════════════════════════════════════
leds = {
    "can":     LED(17),
    "plastic": LED(22),
    "paper":   LED(27),
    "bottle":  LED(5),
}

ultrasonic = DistanceSensor(echo=24, trigger=23, max_distance=1.0)
dht_sensor = adafruit_dht.DHT11(board.D6)


def turn_off_all():
    for led in leds.values():
        led.off()


# ══════════════════════════════════════════════
# 3. 공유 상태
# ══════════════════════════════════════════════
class State:
    lock = threading.Lock()
    temperature: float | None = None
    humidity:    float | None = None
    # POST에 사용할 로컬 누적 카운터
    counts = {"plastic": 0, "paper": 0, "can": 0, "bottle": 0}
    # 서버에서 가져온 표시용 통계
    display_stats = {"plastic": 0, "paper": 0, "can": 0, "bottle": 0}


# ══════════════════════════════════════════════
# 4. 메인 GUI 클래스
# ══════════════════════════════════════════════
class SmartRecycleBinApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smart Recycling Bin")
        self.root.geometry("1024x530")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)

        # 7인치 디스플레이 — 시작 시 풀스크린
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Escape>", self._exit_fullscreen)
        self._fullscreen = True
        self.root.attributes("-fullscreen", True)

        self.running = True
        self.cooldown = False
        self._photo = None   # PhotoImage 참조 유지 (GC 방지)

        # ── 하드웨어 준비 ──
        self.model = YOLO(MODEL_PATH)
        print(f"[MODEL] {MODEL_PATH} loaded. Classes: {self.model.names}")

        self.picam = Picamera2()
        cfg = self.picam.create_preview_configuration(
            main={"format": "RGB888", "size": (CAM_W, CAM_H)}
        )
        self.picam.configure(cfg)
        self.picam.start()
        time.sleep(1)

        # ── UI 구축 ──
        self._setup_fonts()
        self._build_ui()

        # ── 백그라운드 스레드 ──
        threading.Thread(target=self._dht_loop, daemon=True).start()
        threading.Thread(target=self._stats_loop, daemon=True).start()
        threading.Thread(target=self._env_post_loop, daemon=True).start()

        # ── 프레임 처리 시작 ──
        self.root.after(FRAME_INTERVAL, self._process_frame)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        print("[SYSTEM] GUI started  (F11: fullscreen, Esc: windowed)")

    # ──────────────────────────────────────────
    # UI 구축
    # ──────────────────────────────────────────
    def _setup_fonts(self):
        families = tkfont.families()
        kr_fonts = ["Noto Sans CJK KR", "NanumGothic", "UnDotum", "Malgun Gothic"]
        family = "TkDefaultFont"
        for f in kr_fonts:
            if f in families:
                family = f
                break

        self.f_title  = (family, 16, "bold")
        self.f_large  = (family, 15, "bold")
        self.f_status = (family, 13, "bold")
        self.f_med    = (family, 12)
        self.f_small  = (family, 10)

    def _build_ui(self):
        # ── 상단 타이틀 ──
        hdr = tk.Frame(self.root, bg=BG_HEADER, pady=6)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="Smart Recycling Bin", font=self.f_title,
                 fg=FG_WHITE, bg=BG_HEADER).pack()

        # ── 중앙 영역 ──
        mid = tk.Frame(self.root, bg=BG_DARK)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 좌측: 카메라
        cam_card = tk.Frame(mid, bg=BG_CARD)
        cam_card.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5))

        tk.Label(cam_card, text="Live Camera", font=self.f_small,
                 fg=FG_DIM, bg=BG_CARD, pady=3).pack()
        self.lbl_cam = tk.Label(cam_card, bg="#000000")
        self.lbl_cam.pack(padx=4, pady=(0, 2))
        self.lbl_dist = tk.Label(cam_card, text="Distance: -- cm", font=self.f_small,
                                 fg=FG_DIM, bg=BG_CARD, pady=2)
        self.lbl_dist.pack()

        # 우측: 정보 패널
        info_card = tk.Frame(mid, bg=BG_CARD, width=420)
        info_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        info_card.pack_propagate(False)

        # 상태
        sec_status = tk.Frame(info_card, bg=BG_CARD, pady=8, padx=12)
        sec_status.pack(fill=tk.X)

        self.lbl_status = tk.Label(sec_status, text="Waiting...",
                                   font=self.f_status, fg=FG_DIM, bg=BG_CARD, anchor="w")
        self.lbl_status.pack(fill=tk.X)

        self.lbl_class = tk.Label(sec_status, text="", font=self.f_large,
                                  fg=FG_WHITE, bg=BG_CARD, anchor="w")
        self.lbl_class.pack(fill=tk.X, pady=(5, 0))

        self.lbl_conf = tk.Label(sec_status, text="", font=self.f_small,
                                 fg=FG_DIM, bg=BG_CARD, anchor="w")
        self.lbl_conf.pack(fill=tk.X)

        # 구분선
        tk.Frame(info_card, bg=FG_DIM, height=1).pack(fill=tk.X, padx=15, pady=5)

        # 분리수거 방법
        sec_tips = tk.Frame(info_card, bg=BG_CARD, padx=12, pady=4)
        sec_tips.pack(fill=tk.BOTH, expand=True)

        tk.Label(sec_tips, text="How to Recycle", font=self.f_med,
                 fg=FG_WHITE, bg=BG_CARD, anchor="w").pack(fill=tk.X, pady=(0, 6))

        self.lbl_tips = []
        for _ in range(3):
            lbl = tk.Label(sec_tips, text="", font=self.f_small, fg=FG_DIM,
                           bg=BG_CARD, anchor="w", wraplength=380, justify=tk.LEFT)
            lbl.pack(fill=tk.X, pady=1)
            self.lbl_tips.append(lbl)

        self._show_idle_tips()

        # ── 하단 통계 바 ──
        btm = tk.Frame(self.root, bg=BG_HEADER, pady=5)
        btm.pack(fill=tk.X, side=tk.BOTTOM)

        # 좌측: 누적 통계
        stats_l = tk.Frame(btm, bg=BG_HEADER)
        stats_l.pack(side=tk.LEFT, padx=15)
        tk.Label(stats_l, text="Total Recycled (Server)", font=self.f_small,
                 fg=FG_DIM, bg=BG_HEADER).pack(anchor="w")
        self.lbl_stats = tk.Label(stats_l,
                                  text="Can: 0   Plastic: 0   Paper: 0   Bottle: 0",
                                  font=self.f_med, fg=FG_WHITE, bg=BG_HEADER)
        self.lbl_stats.pack(anchor="w")

        # 우측: 온습도
        stats_r = tk.Frame(btm, bg=BG_HEADER)
        stats_r.pack(side=tk.RIGHT, padx=15)
        tk.Label(stats_r, text="Environment", font=self.f_small,
                 fg=FG_DIM, bg=BG_HEADER).pack(anchor="e")
        self.lbl_env = tk.Label(stats_r, text="Temp: --C   Humidity: --%",
                                font=self.f_med, fg=FG_WHITE, bg=BG_HEADER)
        self.lbl_env.pack(anchor="e")

    # ──────────────────────────────────────────
    # 정보 패널 갱신 헬퍼
    # ──────────────────────────────────────────
    def _show_idle_tips(self):
        self.lbl_status.configure(text="Waiting...", fg=FG_DIM)
        self.lbl_class.configure(text="")
        self.lbl_conf.configure(text="")
        self.lbl_tips[0].configure(text="Place an item above the bin", fg=FG_DIM)
        self.lbl_tips[1].configure(text="(bring within 20cm)", fg=FG_DIM)
        self.lbl_tips[2].configure(text="")

    def _show_detection(self, class_name: str, confidence: float):
        info = RECYCLE_INFO.get(class_name)
        if not info:
            return
        self.lbl_status.configure(text="Detected!", fg=FG_GREEN)
        self.lbl_class.configure(text=info["name"], fg=info["color"])
        self.lbl_conf.configure(text=f"Confidence: {confidence:.1%}")
        for i, tip in enumerate(info["tips"]):
            self.lbl_tips[i].configure(text=tip, fg=FG_WHITE)

    # ──────────────────────────────────────────
    # 메인 프레임 처리 (after 콜백)
    # ──────────────────────────────────────────
    def _process_frame(self):
        if not self.running:
            return

        try:
            # 1) 초음파
            try:
                distance    = ultrasonic.distance
                object_near = distance < DETECT_DISTANCE
                self.lbl_dist.configure(
                    text=f"Distance: {distance * 100:.1f} cm",
                    fg=FG_GREEN if object_near else FG_DIM,
                )
            except Exception as echo_err:
                # DHT11 등의 다른 센서와의 타이밍 충돌이나 No Echo 발생 시 프로그램 중단을 방지
                print(f"[ULTRASONIC] Reading failed (No Echo/Timing conflict): {echo_err}")
                distance    = 1.0
                object_near = False
                self.lbl_dist.configure(
                    text="Distance: Error",
                    fg=FG_RED,
                )

            # 2) 카메라 캡처
            frame_rgb = self.picam.capture_array()
            cv_frame  = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

            # 3) YOLO 추론
            results = self.model.predict(source=cv_frame, conf=CONF_THRESHOLD, verbose=False)

            # 4) 결과 판정
            if (object_near
                    and results[0].boxes
                    and len(results[0].boxes) > 0
                    and not self.cooldown):
                boxes    = results[0].boxes
                best_idx = int(boxes.conf.argmax())
                cls_id   = int(boxes.cls[best_idx])
                top_conf = float(boxes.conf[best_idx])
                detected = self.model.names[cls_id]

                print(f"[DETECT] {detected} ({top_conf:.1%}, {distance * 100:.1f}cm)")

                # LED 점등
                turn_off_all()
                if detected in leds:
                    leds[detected].on()

                # 서버 전송
                self._send_to_server(detected)

                # UI 갱신
                self._show_detection(detected, top_conf)

                # 쿨다운
                self.cooldown = True
                def _reset():
                    time.sleep(LED_ON_DURATION)
                    self.cooldown = False
                    turn_off_all()
                threading.Thread(target=_reset, daemon=True).start()

            elif not object_near and not self.cooldown:
                turn_off_all()
                self._show_idle_tips()

            # 5) 카메라 화면을 tkinter에 표시
            annotated     = results[0].plot()                         # BGR
            annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            display       = cv2.resize(annotated_rgb, (DISPLAY_W, DISPLAY_H))
            img           = Image.fromarray(display)
            self._photo   = ImageTk.PhotoImage(img)
            self.lbl_cam.configure(image=self._photo)

        except Exception as e:
            print(f"[FRAME] Error: {e}")

        self.root.after(FRAME_INTERVAL, self._process_frame)

    # ──────────────────────────────────────────
    # 서버 전송
    # ──────────────────────────────────────────
    def _send_to_server(self, detected_class: str):
        with State.lock:
            key = detected_class if detected_class in State.counts else "bottle"
            State.counts[key] += 1
            payload = {
                "temperature": State.temperature,
                "humidity":    State.humidity,
                **State.counts,
            }

        def _post():
            try:
                resp = requests.post(SERVER_URL, json=payload, timeout=REQUEST_TIMEOUT)
                print(f"[SERVER] {resp.status_code} - {detected_class} sent")
            except Exception as e:
                print(f"[SERVER] Send failed: {e}")

        threading.Thread(target=_post, daemon=True).start()

    def _post_env_update(self):
        """Post current temp/humidity + counts to server (periodic update)"""
        with State.lock:
            if State.temperature is None and State.humidity is None:
                return
            payload = {
                "temperature": State.temperature,
                "humidity":    State.humidity,
                **State.counts,
            }

        def _post():
            try:
                resp = requests.post(SERVER_URL, json=payload, timeout=REQUEST_TIMEOUT)
                print(f"[SERVER] {resp.status_code} - periodic env update")
            except Exception as e:
                print(f"[SERVER] Periodic send failed: {e}")

        threading.Thread(target=_post, daemon=True).start()

    # ──────────────────────────────────────────
    # 백그라운드: DHT11
    # ──────────────────────────────────────────
    def _dht_loop(self):
        while self.running:
            try:
                t = dht_sensor.temperature
                h = dht_sensor.humidity
                if t is not None and h is not None:
                    with State.lock:
                        State.temperature = t
                        State.humidity    = h
                    self.root.after(0, self._update_env, t, h)
            except RuntimeError as e:
                print(f"[DHT] Retrying... ({e.args[0]})")
                time.sleep(DHT_INTERVAL)
                continue
            except Exception as e:
                print(f"[DHT] Exception: {e}")
            time.sleep(DHT_INTERVAL)

    def _update_env(self, t: float, h: float):
        self.lbl_env.configure(text=f"Temp: {t:.1f}C   Humidity: {h:.1f}%")

    # ──────────────────────────────────────────
    # 백그라운드: 온습도 주기적 서버 전송 (1분)
    # ──────────────────────────────────────────
    def _env_post_loop(self):
        while self.running:
            time.sleep(ENV_POST_INTERVAL)
            if not self.running:
                break
            self._post_env_update()

    # ──────────────────────────────────────────
    # 백그라운드: 서버 통계 조회
    # ──────────────────────────────────────────
    def _stats_loop(self):
        first = True
        while self.running:
            try:
                resp = requests.get(STATS_URL, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    with State.lock:
                        State.display_stats = {
                            "can":     data.get("can", 0),
                            "plastic": data.get("plastic", 0),
                            "paper":   data.get("paper", 0),
                            "bottle":  data.get("bottle", 0),
                        }
                        # 첫 실행 시 로컬 카운터를 서버 값으로 동기화
                        if first:
                            State.counts = State.display_stats.copy()
                            first = False
                    self.root.after(0, self._update_stats)
            except Exception as e:
                print(f"[STATS] Server fetch failed: {e}")
            time.sleep(STATS_INTERVAL)

    def _update_stats(self):
        with State.lock:
            s = State.display_stats
        self.lbl_stats.configure(
            text=f"Can: {s['can']}   Plastic: {s['plastic']}   "
                 f"Paper: {s['paper']}   Bottle: {s['bottle']}"
        )

    # ──────────────────────────────────────────
    # 풀스크린 / 종료
    # ──────────────────────────────────────────
    def _toggle_fullscreen(self, _event=None):
        self._fullscreen = not self._fullscreen
        self.root.attributes("-fullscreen", self._fullscreen)

    def _exit_fullscreen(self, _event=None):
        self._fullscreen = False
        self.root.attributes("-fullscreen", False)

    def _on_close(self):
        print("[SYSTEM] Shutting down...")
        self.running = False
        turn_off_all()
        try:
            self.picam.stop()
        except Exception:
            pass
        try:
            dht_sensor.exit()
        except Exception:
            pass
        self.root.destroy()
        print("[SYSTEM] Shutdown complete")


# ══════════════════════════════════════════════
# 5. 엔트리포인트
# ══════════════════════════════════════════════
if __name__ == "__main__":
    root = tk.Tk()
    app  = SmartRecycleBinApp(root)
    root.mainloop()
