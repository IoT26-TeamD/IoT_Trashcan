import time
import board
import adafruit_dht

# GPIO 4번 핀 사용 (board.D4)
dht_device = adafruit_dht.DHT11(board.D4)

print("온습도 측정 시작... (종료하려면 Ctrl+C)")

try:
    while True:
        try:
            # 센서 데이터 읽기
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            
            if temperature is not None and humidity is not None:
                print(f"온도: {temperature:.1f}°C | 습도: {humidity:.1f}%")
                
        except RuntimeError as error:
            # DHT11 센서 특성상 미세한 타이밍 문제로 읽기 실패(RuntimeError)가 종종 발생합니다.
            # 에러를 무시하고 2초 뒤에 다시 측정하도록 처리합니다.
            print(f"센서 읽기 재시도 중... ({error.args[0]})")
            time.sleep(2.0)
            continue
            
        except Exception as error:
            dht_device.exit()
            raise error

        # 다음 측정까지 2초 대기 (DHT11 센서의 권장 측정 주기)
        time.sleep(2.0)
        
except KeyboardInterrupt:
    print("\n테스트를 종료합니다.")

finally:
    # 종료 시 센서 연결을 안전하게 해제
    dht_device.exit()
