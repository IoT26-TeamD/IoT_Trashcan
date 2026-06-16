import cv2
import numpy as np
from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import LED
import time

# ──────────────────────────────────────────────
# 1. 핀 설정 (BCM 기준)
# ──────────────────────────────────────────────
leds = {
    "metal":   LED(17),
    "general": LED(22),
    "bottle":  LED(27),
    "plastic": LED(5),
}

def turn_off_all():
    for led in leds.values():
        led.off()

# ──────────────────────────────────────────────
# 2. 모델 로드 (YOLOv8n Object Detection)
# ──────────────────────────────────────────────
model = YOLO('./best.pt')
print(f"모델 로드 완료. 클래스: {model.names}")

CONF_THRESHOLD = 0.4   # 신뢰도 임계값 (0.3~0.5 사이에서 조정)

# ──────────────────────────────────────────────
# 3. 메인 프로세스
# ──────────────────────────────────────────────
try:
    with Picamera2() as picam:
        config = picam.create_preview_configuration(
            main={'format': 'RGB888', 'size': (640, 480)}
        )
        picam.configure(config)
        picam.start()
        time.sleep(1)  # 카메라 워밍업

        print("시스템 가동 시작... (종료: q)")

        while True:
            # ── 프레임 캡처 및 BGR 변환 ──
            frame_array = picam.capture_array()
            cv_frame    = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)

            # ── Detection 추론 ──
            results = model.predict(source=cv_frame, conf=CONF_THRESHOLD, verbose=False)

            # ── 결과 파싱 (detection: results[0].boxes 사용) ──
            status        = "Idle"
            detected_name = "None"
            top_conf      = 0.0

            if results[0].boxes and len(results[0].boxes) > 0:
                # 신뢰도가 가장 높은 박스 선택
                boxes    = results[0].boxes
                best_idx = int(boxes.conf.argmax())
                cls_id   = int(boxes.cls[best_idx])
                top_conf = float(boxes.conf[best_idx])

                detected_name = model.names[cls_id]
                status        = "Active"

                # LED 제어
                turn_off_all()
                if detected_name in leds:
                    leds[detected_name].on()
            else:
                turn_off_all()

            # ── 화면 UI (바운딩박스 + 텍스트 오버레이) ──
            # results[0].plot() 으로 바운딩박스 자동 렌더링
            display = results[0].plot()

            # 상단 반투명 배경
            overlay = display.copy()
            cv2.rectangle(overlay, (0, 0), (640, 175), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.4, display, 0.6, 0, display)

            # 상태 텍스트
            cv2.putText(display, f"Status  : {status}",
                        (20, 50),  cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                        (0, 255, 0) if status == "Active" else (180, 180, 180), 2)
            cv2.putText(display, f"Detected: {detected_name}",
                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 100, 255), 2)
            cv2.putText(display, f"Conf    : {top_conf:.1%}" if status == "Active" else "Conf    : -",
                        (20, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 220, 255), 2)

            # 신뢰도 바 (감지된 경우에만)
            if status == "Active":
                bar_w = int(600 * top_conf)
                cv2.rectangle(display, (20, 160), (20 + bar_w, 172), (0, 200, 80), -1)
            cv2.rectangle(display, (20, 160), (620, 172), (80, 80, 80), 1)

            cv2.imshow('Smart Recycle Bin [Detection Test]', display)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

except Exception as e:
    print(f"오류 발생: {e}")
    raise

finally:
    turn_off_all()
    cv2.destroyAllWindows()
    print("시스템 종료 및 자원 반납")
