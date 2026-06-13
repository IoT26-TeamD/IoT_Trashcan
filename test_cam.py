import cv2
import numpy as np
from ultralytics import YOLO
from picamera2 import Picamera2
from gpiozero import LED
import time

# 1. 핀 설정 (보드 핀 번호와 매칭 확인하세요)
leds = {
    0: LED(17), # can
    1: LED(22), # plastic
    2: LED(27), # paper
    3: LED(5)   # bottle
}

def turn_off_all():
    for led in leds.values():
        led.off()

# 2. 모델 로드
# 모델 경로가 정확한지 확인하세요!
model = YOLO('./best.pt')

# 3. 메인 프로세스
try:
    with Picamera2() as picam:
        config = picam.create_preview_configuration(main={'format': 'RGB888', 'size': (640, 480)})
        picam.configure(config)
        picam.start()
        
        print("시스템 가동 시작...")
        
        while True:
            # 프레임 캡처 및 BGR 변환
            frame_array = picam.capture_array()
            cv_frame = cv2.cvtColor(frame_array, cv2.COLOR_RGB2BGR)
            
            # YOLO 추론 (conf를 0.3~0.4 정도로 낮춰서 테스트해보세요)
            results = model.predict(source=cv_frame, conf=0.4, verbose=False)
            
            # 결과 그리기 및 상태 추출
            status = "Idle"
            detected_name = "None"
            
            if results[0].boxes:
                status = "Active"
                # 확신도가 가장 높은 객체 하나 선택
                box = results[0].boxes[0]
                cls_id = int(box.cls[0])
                detected_name = model.names[cls_id]
                
                # LED 제어
                turn_off_all()
                if cls_id in leds:
                    leds[cls_id].on()
            else:
                turn_off_all()
            
            # 화면 UI 그리기
            annotated_frame = results[0].plot()
            cv2.putText(annotated_frame, f"Status: {status}", (20, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Detected: {detected_name}", (20, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # 영상 출력
            cv2.imshow('Smart Recycle Bin', annotated_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

except Exception as e:
    print(f"오류 발생: {e}")

finally:
    turn_off_all()
    cv2.destroyAllWindows()
    print("시스템 종료 및 자원 반납")
