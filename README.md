# ♻️ AIoT 스마트 분리수거 쓰레기통

> **YOLOv8 객체 인식 + 라즈베리파이 5 + Flask 대시보드**로 구현한 AI 기반 자동 분리수거 시스템

카메라 앞에 쓰레기를 놓으면 AI가 종류를 인식하고, 해당 LED를 점등하여 올바른 분리수거함을 안내합니다.  
인식 결과와 환경 데이터(온·습도)는 클라우드 서버로 전송되어 실시간 대시보드에서 모니터링할 수 있습니다.

---

## 📋 목차

- [시스템 개요](#-시스템-개요)
- [인식 클래스](#-인식-클래스)
- [하드웨어 구성](#-하드웨어-구성)
- [소프트웨어 아키텍처](#-소프트웨어-아키텍처)
- [프로젝트 구조](#-프로젝트-구조)
- [설치 및 실행](#-설치-및-실행)
- [서버 API 규격](#-서버-api-규격)
- [시스템 동작 흐름](#-시스템-동작-흐름)

---

## 🔍 시스템 개요

| 항목 | 내용 |
|---|---|
| **플랫폼** | Raspberry Pi 5 |
| **AI 모델** | YOLOv8n Object Detection (`best.pt`) |
| **GUI** | tkinter 기반 풀스크린 (7인치 LCD 최적화) |
| **서버** | Flask + SQLite (Docker 컨테이너) |
| **통신** | HTTP REST API (JSON) |

---

## 🏷️ 인식 클래스

| 클래스명 | 의미 | LED GPIO (BCM) | LED 색상 |
|---|---|---|---|
| `metal` | 캔 / 고철 | GPIO 17 | 🟠 Orange |
| `plastic` | 플라스틱 | GPIO 22 | 🔵 Blue |
| `general` | 일반쓰레기 | GPIO 27 | 🔴 Red |
| `bottle` | 유리병 | GPIO 5 | 🟣 Purple |

---

## 🔧 하드웨어 구성

### GPIO 핀 맵핑 (BCM 기준)

| 모듈 | 기능 | GPIO 핀 | 물리 핀 | 비고 |
|---|---|---|---|---|
| **Pi Camera** | 영상 캡처 | CSI Port | - | 전용 리본 케이블 |
| **초음파 센서** | Trigger | GPIO 23 | Pin 16 | 물체 접근 감지 (18cm) |
| **초음파 센서** | Echo | GPIO 24 | Pin 18 | 5V→3.3V 전압 분배 필요 |
| **DHT11** | 온습도 | GPIO 6 | Pin 31 | 10kΩ 풀업 저항 권장 |
| **LED 1** | Metal (캔/고철) | GPIO 17 | Pin 11 | 220~330Ω 저항 직렬 |
| **LED 2** | Plastic (플라스틱) | GPIO 22 | Pin 15 | 220~330Ω 저항 직렬 |
| **LED 3** | General (일반쓰레기) | GPIO 27 | Pin 13 | 220~330Ω 저항 직렬 |
| **LED 4** | Bottle (유리병) | GPIO 5 | Pin 29 | 220~330Ω 저항 직렬 |

### 회로 연결 요약

```
Raspberry Pi 5
├── CSI ──── Pi Camera
├── GPIO 23 ── Ultrasonic TRIG
├── GPIO 24 ── Ultrasonic ECHO (voltage divider)
├── GPIO 6  ── DHT11 DATA
├── GPIO 17 ── LED (Metal)
├── GPIO 22 ── LED (Plastic)
├── GPIO 27 ── LED (General)
└── GPIO 5  ── LED (Bottle)
```

---

## 🏗️ 소프트웨어 아키텍처

```
┌──────────────────────────────────────────────┐
│              Raspberry Pi 5                  │
│                                              │
│  ┌────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Camera │→ │ YOLOv8n  │→ │  tkinter    │  │
│  │(PiCam2)│  │ (best.pt)│  │  GUI (LCD)  │  │
│  └────────┘  └──────────┘  └─────────────┘  │
│       │           │              │           │
│  ┌────┴───┐  ┌────┴────┐  ┌─────┴─────┐    │
│  │Ultrason│  │  LED×4  │  │  DHT11    │    │
│  │  Sensor│  │ Control │  │ Temp/Hum  │    │
│  └────────┘  └─────────┘  └───────────┘    │
│                    │                         │
│              HTTP POST/GET                   │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  Cloud Server (AWS EC2)          │
│  ┌────────────────────────────┐  │
│  │  Flask + SQLite (Docker)  │  │
│  │  - POST /api/data         │  │
│  │  - GET  /api/stats        │  │
│  │  - GET  / (Dashboard)     │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

---

## 📁 프로젝트 구조

```
IoT_TrashCan/
├── main.py                  # 메인 GUI 애플리케이션 (라즈베리파이)
├── best.pt                  # YOLOv8 학습 모델 가중치 (.gitignore)
├── cam_test_cls.py          # 카메라 + LED 테스트 (클래스명 기반)
├── test_cam.py              # 카메라 + LED 테스트 (인덱스 기반)
├── distance_test.py         # 초음파 센서 단독 테스트
├── hum_test.py              # DHT11 온습도 센서 테스트
├── led_test.py              # LED 개별 점등 테스트
├── run.sh                   # 실행 스크립트
├── SmartRecycleBin.desktop  # 라즈베리파이 바탕화면 바로가기
├── .gitignore
├── README.md
│
├── WebServer/               # Flask 웹 대시보드 서버
│   ├── app.py               # Flask 서버 메인
│   ├── requirements.txt     # Python 의존성 (Flask)
│   ├── Dockerfile           # Docker 빌드 파일
│   ├── .dockerignore
│   └── templates/
│       └── index.html       # 대시보드 HTML
│
└── Ku-Yolo-DataSet/         # YOLO 학습 데이터셋
```

---

## 🚀 설치 및 실행

### 1. 라즈베리파이 (클라이언트)

```bash
# 저장소 클론
git clone https://github.com/IoT26-TeamD/IoT_TrashCan.git
cd IoT_TrashCan

# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install ultralytics opencv-python-headless pillow
pip install picamera2 gpiozero lgpio adafruit-circuitpython-dht

# best.pt 모델 파일을 프로젝트 루트에 배치

# 실행
python main.py
```

> **💡 Tip:** `run.sh`로 실행하거나, `SmartRecycleBin.desktop`을 바탕화면에 복사하면 더블클릭으로 실행할 수 있습니다.

### 2. 웹 서버 (Docker)

```bash
# Docker Hub에서 이미지 가져오기
docker pull your-dockerhub-id/iot-dashboard:latest

# 컨테이너 실행 (서울 타임존)
docker run -d \
  --name iot-dashboard \
  -p 80:5000 \
  -e TZ=Asia/Seoul \
  --restart unless-stopped \
  your-dockerhub-id/iot-dashboard:latest
```

#### 서버 업데이트 시

```bash
docker stop iot-dashboard && docker rm iot-dashboard
docker pull your-dockerhub-id/iot-dashboard:latest
docker run -d \
  --name iot-dashboard \
  -p 80:5000 \
  -e TZ=Asia/Seoul \
  --restart unless-stopped \
  your-dockerhub-id/iot-dashboard:latest
```

---

## 📡 서버 API 규격

### `POST /api/data` — 분류 결과 전송

라즈베리파이에서 객체 인식 후 서버로 누적 데이터를 전송합니다.

**Request:**
```json
{
  "temperature": 25.3,
  "humidity": 48.0,
  "metal": 1,
  "general": 0,
  "bottle": 2,
  "plastic": 1
}
```

**Response (201):**
```json
{
  "status": "success",
  "message": "Data saved!"
}
```

### `GET /api/stats` — 최신 통계 조회

라즈베리파이 GUI에서 주기적으로 호출하여 통계를 표시합니다.

**Response (200):**
```json
{
  "temperature": 25.3,
  "humidity": 48.0,
  "metal": 1,
  "general": 0,
  "bottle": 2,
  "plastic": 1,
  "timestamp": "2026-06-16 22:53:47"
}
```

### `GET /` — 웹 대시보드

브라우저에서 접속하면 실시간 분리수거 통계 대시보드를 확인할 수 있습니다.

### `POST /reset` — DB 초기화 (테스트용)

대시보드에서 버튼 클릭으로 전체 데이터를 초기화합니다.

---

## ⚙️ 시스템 동작 흐름

1. **대기 상태** — 초음파 센서로 18cm 이내 물체 접근을 감지하며 대기
2. **객체 감지** — 물체가 감지되면 카메라 프레임을 YOLOv8 모델에 전달
3. **분류 판정** — 신뢰도가 가장 높은 클래스(`metal` / `plastic` / `general` / `bottle`)를 선택
4. **LED 점등** — 해당 분류의 LED를 3초간 점등하여 사용자에게 안내
5. **서버 전송** — 분류 결과 + 온습도 데이터를 서버로 POST
6. **GUI 표시** — LCD 모니터에 카메라 화면, 분류 결과, 분리수거 방법을 실시간 표시
7. **쿨다운** — 3초간 중복 인식 방지 후 대기 상태로 복귀

---

## 📜 License

This project is developed for educational purposes.
