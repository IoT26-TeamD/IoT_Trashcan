# 📊 시스템 아키텍처 및 규격서: 스마트 쓰레기통 프로젝트

## 1. 하드웨어 구성 및 GPIO 핀 맵핑

라즈베리파이 5(Raspberry Pi 5) 기반의 하드웨어 제어를 위한 핀 할당표입니다. 모든 핀 번호는 **BCM 기준**입니다.

| 모듈 | 기능 / 분류 | GPIO 핀 번호 (BCM) | 라즈베리파이 물리 핀 번호 | 비고 |
| --- | --- | --- | --- | --- |
| **카메라** | Pi Camera | `CSI Port` | - | 전용 리본 케이블 연결 |
| **초음파 센서** | Trigger (발신) | **GPIO 23** | Pin 16 | 물체 접근 감지용 (20cm) |
| **초음파 센서** | Echo (수신) | **GPIO 24** | Pin 18 | 5V -> 3.3V 전압 강하(저항 분배) 필요 |
| **온습도 센서** | DHT11 / DHT22 | **GPIO 4** | Pin 7 | Data 핀 연결 (10kΩ 풀업 저항 권장) |
| **LED 1** | Can (캔) | **GPIO 17** | Pin 11 | 220Ω ~ 330Ω 저항 직렬 연결 |
| **LED 2** | Plastic (플라스틱) | **GPIO 22** | Pin 15 | 220Ω ~ 330Ω 저항 직렬 연결 |
| **LED 3** | Paper (종이) | **GPIO 27** | Pin 13 | 220Ω ~ 330Ω 저항 직렬 연결 |
| **LED 4** | Bottle (병) | **GPIO 5** | Pin 29 | 220Ω ~ 330Ω 저항 직렬 연결 |

---

## 2. 서버 통신 규격 (API 통신)

라즈베리파이에서 객체 인식이 성공했을 때, 중앙 서버로 데이터를 전송하기 위한 HTTP REST API 규격입니다.

### 2.1. API 엔드포인트 (Endpoint)

* **URL:** `http://YOUR_SERVER_IP/api/recycle`
* **Method:** `POST`
* **Content-Type:** `application/json`

### 2.2. Request Payload (요청 데이터 형식)

센서에서 측정한 실시간 환경 데이터와 모델이 판별한 쓰레기 종류를 JSON 형태로 서버에 전송합니다.

```json
{
  "type": "can",
  "temperature": 24.5,
  "humidity": 45.0
}

```

* **`type` (String):** YOLO 모델이 예측한 클래스 이름 (`can`, `plastic`, `paper`, `bottle` 중 하나).
* **`temperature` (Float):** 실시간 섭씨 온도 (예: 24.5). 읽기 실패 시 `null`.
* **`humidity` (Float):** 실시간 상대 습도 단위 % (예: 45.0). 읽기 실패 시 `null`.

### 2.3. 기대되는 Response (응답)

* **성공 시 (200 OK):** `{"status": "success", "message": "Data saved"}`
* 라즈베리파이 측(클라이언트)에서는 트래픽 및 시스템 블로킹 방지를 위해 응답에 대한 엄격한 예외 처리(Timeout=1초 등)를 적용하여, 서버 장애가 라즈베리파이의 동작에 영향을 주지 않도록 설계합니다.

---

## 3. 시스템 동작 흐름 (Workflow)

1. **상태 모니터링 (대기):** 백그라운드에서 주기적으로 온습도(DHT) 데이터를 갱신하며, 초음파 센서를 통해 20cm 이내의 물체 접근을 감지합니다.
2. **이벤트 트리거:** 물체가 감지되면 대기 상태에서 활성(Active) 상태로 전환되며 PiCamera2의 프레임을 캡처합니다.
3. **AI 객체 인식:** 캡처된 프레임을 YOLOv8_class 모델(`best.pt`)에 통과시켜 객체 종류(클래스)와 신뢰도(Confidence)를 판별합니다. (흰 배경에 물체 탐색이므로, classification 모델 사용)
4. **하드웨어 제어:** 인식된 객체에 해당하는 GPIO LED 핀에 HIGH(On) 신호를 주어 점등합니다.
5. **클라우드 전송:** 판별된 `type`과 저장해 둔 `temperature`, `humidity` 값을 JSON으로 묶어 서버의 엔드포인트로 POST 요청을 보냅니다.
6. **UI 피드백:** HDMI로 연결된 모니터에 인식된 객체의 박스와 현재 상태, 온습도 텍스트를 실시간으로 오버레이하여 출력합니다.