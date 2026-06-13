from flask import Flask, request, jsonify, render_template, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = 'iot_data.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if 'bottle' column exists
    try:
        c.execute("SELECT bottle FROM sensor_data LIMIT 1")
    except sqlite3.OperationalError:
        # If 'bottle' column is missing (or table doesn't exist)
        try:
            # Try to migrate general to bottle
            c.execute("ALTER TABLE sensor_data RENAME COLUMN general TO bottle")
            conn.commit()
            print("[DB] Migrated general column to bottle successfully.")
        except sqlite3.OperationalError:
            # If migration fails (e.g. SQLite version too old, or no table at all), drop and recreate
            c.execute("DROP TABLE IF EXISTS sensor_data")
            conn.commit()
            print("[DB] Dropped old table to recreate with new schema.")

    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            plastic INT,
            paper INT,
            can INT,
            bottle INT
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
    plastic = data.get('plastic', 0)
    paper = data.get('paper', 0)
    can = data.get('can', 0)
    bottle = data.get('bottle', 0)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO sensor_data 
        (timestamp, temperature, humidity, plastic, paper, can, bottle) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, temp, humidity, plastic, paper, can, bottle))
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
            "plastic":     row["plastic"],
            "paper":       row["paper"],
            "can":         row["can"],
            "bottle":      row["bottle"],
            "timestamp":   row["timestamp"],
        })
    return jsonify({
        "temperature": 0, "humidity": 0,
        "plastic": 0, "paper": 0, "can": 0, "bottle": 0,
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