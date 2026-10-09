"""Persistência local SQLite: telemetria, alertas e metadados, sem dependências externas."""
import json
import sqlite3
from pathlib import Path

class Store:
    def __init__(self, filename):
        Path(filename).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(filename,check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS readings (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           timestamp TEXT NOT NULL,
           tp3 REAL NOT NULL,
           motor_current REAL NOT NULL,
           oil_temperature REAL NOT NULL,
           dv_eletric REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           method TEXT NOT NULL, timestamp TEXT NOT NULL,
           cycle_start TEXT NOT NULL, elapsed_s REAL NOT NULL,
           pressure_bar REAL NOT NULL, start_pressure_bar REAL NOT NULL,
           motor_current_a REAL NOT NULL, severity TEXT NOT NULL, message TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_r_timestamp ON readings(timestamp);
        CREATE INDEX IF NOT EXISTS idx_a_timestamp ON alerts(timestamp);
        ''')
        self.db.commit()

    def insert(self, sample, alerts):
        self.db.execute('''INSERT INTO readings(timestamp,tp3,motor_current,oil_temperature,dv_eletric)
          VALUES(?,?,?,?,?)''', (sample['timestamp'],sample['TP3'],sample['Motor_current'],sample['Oil_temperature'],sample['DV_eletric']))
        for a in alerts:
            self.db.execute('''INSERT INTO alerts(method,timestamp,cycle_start,elapsed_s,pressure_bar,
              start_pressure_bar,motor_current_a,severity,message) VALUES(?,?,?,?,?,?,?,?,?)''',
              tuple(a[k] for k in ('method','timestamp','cycle_start','elapsed_s','pressure_bar','start_pressure_bar','motor_current_a','severity','message')))
        self.db.commit()

    def recent(self, table, limit):
        limit=max(1,min(int(limit),5000))
        self.db.row_factory=sqlite3.Row
        records=[dict(x) for x in self.db.execute(f'SELECT * FROM {table} ORDER BY id DESC LIMIT ?', (limit,))]
        records.reverse()
        return records

    def counts(self):
        reads=self.db.execute('SELECT COUNT(*) FROM readings').fetchone()[0]
        alerts=self.db.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]
        primary=self.db.execute("SELECT COUNT(*) FROM alerts WHERE method='Pressao_nao_recuperada_q99'").fetchone()[0]
        return {'readings':reads,'alerts':alerts,'primary_alerts':primary}

    def all_alerts(self):
        self.db.row_factory=sqlite3.Row
        return [dict(x) for x in self.db.execute('SELECT * FROM alerts ORDER BY id')]

    def clear(self):
        self.db.execute('DELETE FROM readings')
        self.db.execute('DELETE FROM alerts')
        self.db.commit()
