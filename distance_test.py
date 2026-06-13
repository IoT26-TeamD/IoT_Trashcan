from gpiozero import DistanceSensor
from time import sleep

# ECHO 핀은 GPIO 24, TRIG 핀은 GPIO 23으로 설정
# max_distance는 1m(1.0)로 제한하여 센서 값이 비정상적으로 튀는 것을 방지
sensor = DistanceSensor(echo=24, trigger=23, max_distance=1.0)

print("초음파 거리 측정 시작... (종료하려면 Ctrl+C)")

try:
    while True:
        # sensor.distance는 미터(m) 단위로 반환되므로 100을 곱해 cm로 변환
        distance_cm = sensor.distance * 100
        print(f"측정 거리: {distance_cm:.1f} cm")
        
        # 0.5초 간격으로 측정
        sleep(0.5)

except KeyboardInterrupt:
    print("\n테스트를 종료합니다.")
