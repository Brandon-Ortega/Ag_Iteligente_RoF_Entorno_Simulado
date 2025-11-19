import sqlite3
import random
import time

# --- Nombres de los recursos (del documento) ---
RECURSOS = {
    'longitudes_onda': [f'λ{i+1}' for i in range(4)],
    'canales_mmwave': [f'Ch{i+1}' for i in range(8)],
    'niveles_potencia': [f'P{i+1}' for i in range(3)]
}
N_RAUS = 10
N_USUARIOS = 50

def setup_database():
    """
    Crea y pobla la base de datos SQLite para la simulación del agente.
    """
    # Conecta (y crea si no existe) la base de datos
    conn = sqlite3.connect('NGN_RoF.db')
    cursor = conn.cursor()

    print("Creando esquema de la base de datos...")

    # --- 1. Tablas de Configuración y Recursos ---
    cursor.execute("DROP TABLE IF EXISTS Recursos_Longitudes_Onda;")
    cursor.execute("""
    CREATE TABLE Recursos_Longitudes_Onda (
        lambda_id INTEGER PRIMARY KEY AUTOINCREMENT,
        valor_lambda TEXT NOT NULL UNIQUE
    );
    """)

    cursor.execute("DROP TABLE IF EXISTS Recursos_Canales_mmWave;")
    cursor.execute("""
    CREATE TABLE Recursos_Canales_mmWave (
        canal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        valor_canal TEXT NOT NULL UNIQUE,
        ancho_banda_mhz REAL
    );
    """)

    cursor.execute("DROP TABLE IF EXISTS Recursos_Niveles_Potencia;")
    cursor.execute("""
    CREATE TABLE Recursos_Niveles_Potencia (
        potencia_id INTEGER PRIMARY KEY AUTOINCREMENT,
        valor_potencia_dbm REAL NOT NULL UNIQUE
    );
    """)

    # --- Tabla Principal de RAUs (Estado Actual) ---
    cursor.execute("DROP TABLE IF EXISTS RAUs;")
    cursor.execute("""
    CREATE TABLE RAUs (
        rau_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ubicacion_desc TEXT,
        config_actual_lambda_id INTEGER,
        config_actual_canal_id INTEGER,
        config_actual_potencia_id INTEGER,
        FOREIGN KEY (config_actual_lambda_id) REFERENCES Recursos_Longitudes_Onda(lambda_id),
        FOREIGN KEY (config_actual_canal_id) REFERENCES Recursos_Canales_mmWave(canal_id),
        FOREIGN KEY (config_actual_potencia_id) REFERENCES Recursos_Niveles_Potencia(potencia_id)
    );
    """)

    # --- 2. Tablas de Percepción Dinámica ---
    cursor.execute("DROP TABLE IF EXISTS Metricas_Usuarios;")
    cursor.execute("""
    CREATE TABLE Metricas_Usuarios (
        reporte_id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        rau_id_conectada INTEGER NOT NULL,
        cqi_sinr_db REAL NOT NULL,
        demanda_qos_mbps REAL NOT NULL,
        timestamp_reporte INTEGER NOT NULL,
        FOREIGN KEY (rau_id_conectada) REFERENCES RAUs(rau_id)
    );
    """)

    cursor.execute("DROP TABLE IF EXISTS Metricas_Trafico_RAU;")
    cursor.execute("""
    CREATE TABLE Metricas_Trafico_RAU (
        metrica_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rau_id INTEGER NOT NULL,
        carga_datos_actual_mbps REAL NOT NULL,
        num_usuarios_conectados INTEGER NOT NULL,
        timestamp_metrica INTEGER NOT NULL,
        FOREIGN KEY (rau_id) REFERENCES RAUs(rau_id)
    );
    """)

    conn.commit()
    print("Esquema creado con éxito.")

    # --- Poblar la base de datos con datos de ejemplo ---
    print("Poblando la base de datos con datos de simulación...")
    
    # Poblar Recursos
    lambda_ids = {val: i+1 for i, val in enumerate(RECURSOS['longitudes_onda'])}
    cursor.executemany("INSERT INTO Recursos_Longitudes_Onda (valor_lambda) VALUES (?)", 
                       [(val,) for val in RECURSOS['longitudes_onda']])
    
    canal_ids = {val: i+1 for i, val in enumerate(RECURSOS['canales_mmwave'])}
    cursor.executemany("INSERT INTO Recursos_Canales_mmWave (valor_canal, ancho_banda_mhz) VALUES (?, ?)", 
                       [(val, 100.0) for val in RECURSOS['canales_mmwave']])

    potencia_ids = {val: i+1 for i, val in enumerate(RECURSOS['niveles_potencia'])}
    cursor.executemany("INSERT INTO Recursos_Niveles_Potencia (valor_potencia_dbm) VALUES (?)", 
                       [(random.uniform(20, 30),) for val in RECURSOS['niveles_potencia']])
    
    # Poblar RAUs (con asignación inicial aleatoria)
    for i in range(N_RAUS):
        cursor.execute("""
        INSERT INTO RAUs (ubicacion_desc, config_actual_lambda_id, config_actual_canal_id, config_actual_potencia_id) 
        VALUES (?, ?, ?, ?)
        """, (
            f'Poste {i+1} Calle {random.randint(1, 10)}',
            random.choice(list(lambda_ids.values())),
            random.choice(list(canal_ids.values())),
            random.choice(list(potencia_ids.values()))
        ))
    
    # Poblar Métricas (simulando reportes de los últimos 10 segundos)
    current_time = int(time.time())
    for _ in range(N_USUARIOS * 2): # Simular un par de reportes por usuario
        cursor.execute("""
        INSERT INTO Metricas_Usuarios (usuario_id, rau_id_conectada, cqi_sinr_db, demanda_qos_mbps, timestamp_reporte)
        VALUES (?, ?, ?, ?, ?)
        """, (
            random.randint(1, N_USUARIOS),
            random.randint(1, N_RAUS),
            random.uniform(5, 25), # SINR
            random.uniform(50, 100), # Demanda QoS <-- ¡CORREGIDO!
            current_time - random.randint(0, 10)
        ))
        
    for i in range(N_RAUS):
        cursor.execute("""
        INSERT INTO Metricas_Trafico_RAU (rau_id, carga_datos_actual_mbps, num_usuarios_conectados, timestamp_metrica)
        VALUES (?, ?, ?, ?)
        """, (
            i + 1,
            random.uniform(100, 1000), # Carga actual
            N_USUARIOS // N_RAUS + random.randint(-2, 2),
            current_time - random.randint(0, 5)
        ))

    conn.commit()
    conn.close()
    print(f"¡Éxito! Base de datos 'NGN_RoF.db' creada y poblada.")

# --- Ejecutar la función ---
if __name__ == "__main__":
    setup_database()