"""Detector causal de ciclos de pressurização. Replica Etapa 4 amostra a amostra.

Nenhum timestamp/evento futuro é consultado. Datas são as do histórico e são interpretadas
sem timezone porque a fonte não fornece deslocamento UTC.
"""
from dataclasses import dataclass
from datetime import datetime
from math import isfinite

REQUIRED = ('timestamp', 'TP3', 'Motor_current', 'Oil_temperature', 'DV_eletric')

@dataclass
class RunState:
    started: datetime
    pressure_start: float
    reached_target: bool
    fired: set

class Detector:
    def __init__(self, config):
        self.target = float(config['pressao_referencia_bar'])
        self.recovery_cutoff = float(config['q99_tempo_ate_9_7_s'])
        self.duration_cutoff = float(config['q99_duracao_carga_s'])
        self.max_gap = float(config['max_intervalo_telemetria_s'])
        self.test_start = datetime.fromisoformat('2020-05-23T00:00:00')
        self.prev_time = None
        self.active = None
        self.processed = 0
        self.cycle_count = 0
        self.gaps = 0

    def process(self, reading):
        ts = datetime.fromisoformat(str(reading['timestamp']).replace(' ', 'T'))
        if self.prev_time is not None:
            step = (ts-self.prev_time).total_seconds()
            if step <= 0:
                raise ValueError('Timestamp repetido ou fora de ordem; inicie nova sessão para um novo replay')
            if step > self.max_gap:
                self.gaps += 1
                self.active = None
        self.prev_time = ts
        self.processed += 1
        tp3 = float(reading['TP3'])
        current = float(reading['Motor_current'])
        dv = float(reading['DV_eletric'])
        loaded = current > 2.0 and dv > 0.5
        if not loaded:
            self.active = None
            return []
        if self.active is None:
            self.active = RunState(ts, tp3, tp3 >= self.target, set())
            self.cycle_count += 1
        state = self.active
        if tp3 >= self.target:
            state.reached_target = True
        if not 7.7 <= state.pressure_start <= 8.5 or state.started < self.test_start:
            return []
        elapsed = (ts-state.started).total_seconds()
        alerts = []
        specs = (
            ('Carga_longa_q99', self.duration_cutoff, False),
            ('Pressao_nao_recuperada_q99', self.recovery_cutoff, True),
            ('Somente_carga_mesmo_limiar', self.recovery_cutoff, False),
        )
        for method, limit, require_pressure in specs:
            if method in state.fired or elapsed < limit or (require_pressure and state.reached_target):
                continue
            state.fired.add(method)
            alerts.append({
                'method': method, 'timestamp': ts.isoformat(sep=' '),
                'cycle_start': state.started.isoformat(sep=' '),
                'elapsed_s': elapsed, 'pressure_bar': tp3,
                'start_pressure_bar': state.pressure_start,
                'motor_current_a': current,
                'severity': 'ATENCAO' if method == 'Pressao_nao_recuperada_q99' else 'INFORMATIVO',
                'message': ('Recuperacao lenta: pressao ainda abaixo de %.1f bar apos %.0f s' % (self.target,elapsed))
                           if require_pressure else ('Ciclo sob carga excedeu o tempo-limite de %.2f s' % limit),
            })
        return alerts


def validate_reading(obj):
    if not isinstance(obj, dict):
        raise ValueError('Leitura deve ser objeto JSON')
    if any(col not in obj for col in REQUIRED):
        raise ValueError('Leitura sem os campos obrigatorios: ' + ', '.join(REQUIRED))
    try:
        ts = datetime.fromisoformat(str(obj['timestamp']).replace(' ', 'T'))
    except (ValueError, TypeError) as e:
        raise ValueError('timestamp invalido; esperado YYYY-MM-DD HH:MM:SS') from e
    if ts.tzinfo is not None:
        raise ValueError('Timestamps sem fuso horario, conforme fonte MetroPT-3')
    result={'timestamp':ts.isoformat(sep=' ')}
    for x in REQUIRED[1:]:
        try:
            v=float(obj[x])
        except (ValueError,TypeError) as e:
            raise ValueError(x+' deve ser numerico') from e
        if not isfinite(v):
            raise ValueError(x+' deve ser finito')
        result[x]=v
    return result
