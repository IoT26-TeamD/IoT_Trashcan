from flask import Flask, request, jsonify, render_template, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = 'iot_data.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            metal INT,
            general INT,
            bottle INT,
            plastic INT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/api/data', methods=['POST'])
def receive_data():
    data = request.json
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    temp = data.get('temperature', 0)
    humidity = data.get('humidity', 0)
    metal = data.get('metal', 0)
    general = data.get('general', 0)
    bottle = data.get('bottle', 0)
    plastic = data.get('plastic', 0)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO sensor_data 
        (timestamp, temperature, humidity, metal, general, bottle, plastic) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, temp, humidity, metal, general, bottle, plastic))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Data saved!"}), 201

@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    latest_data = rows[0] if rows else None
    
    conn.close()
    return render_template('index.html', records=rows, latest=latest_data)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """최신 누적 통계를 JSON으로 반환 (라즈베리파이 GUI에서 조회용)"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM sensor_data ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        return jsonify({
            "temperature": row["temperature"],
            "humidity":    row["humidity"],
            "metal":       row["metal"],
            "general":     row["general"],
            "bottle":      row["bottle"],
            "plastic":     row["plastic"],
            "timestamp":   row["timestamp"],
        })
    return jsonify({
        "temperature": 0, "humidity": 0,
        "metal": 0, "general": 0, "bottle": 0, "plastic": 0,
        "timestamp": None,
    })

@app.route('/reset', methods=['POST'])
def reset_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM sensor_data")
    c.execute("DELETE FROM sqlite_sequence WHERE name='sensor_data'")
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)