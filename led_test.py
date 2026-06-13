from gpiozero import LED
from time import sleep

# 1. 핀 설정 (GPIO 번호 기준)
can_led = LED(17)     # 캔
paper_led = LED(27)   # 종이
plastic_led = LED(22) # 플라스틱
bottle_led = LED(5)   # 병

# 리스트로 묶어두면 순환시키기 편합니다.
leds = [can_led, paper_led, plastic_led, bottle_led]
names = ["Can(17)", "Paper(27)", "Plastic(22)", "Bottle(5)"]

print("LED 테스트를 시작합니다. (종료하려면 Ctrl+C)")

try:
    while True:
        # 하나씩 순서대로 켜고 끄기        
        # 전체 한 번에 켜보기
        print("전체 LED 켜짐")
        for led in leds:
            led.on()
        sleep(1)
        for led in leds:
            led.off()
        sleep(1)

except KeyboardInterrupt:
    print("\n테스트 종료")
    # 안전을 위해 모든 LED 끄기
    for led in leds:
        led.off()
