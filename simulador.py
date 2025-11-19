import sqlite3
import random
import time
import crear_db       # Importa tu script de creación de DB
import agente_con_db  # Importa tu agente inteligente

DB_FILE = 'NGN_RoF.db'

# --- Funciones de "Naturaleza" (Simulan eventos) ---

def evento_aumento_demanda(rau_id, n_usuarios_nuevos, demanda_min, demanda_max):
    """
    Simula una "multitud flash" (ej. un bus llega) en una RAU específica.
    """
    print(f"\n[EVENTO DE SIMULACIÓN] ¡Una multitud de {n_usuarios_nuevos} usuarios llega a la RAU #{rau_id}!")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    current_time = int(time.time())
    
    # Obtener el ID de usuario más alto para no crear duplicados
    max_user_id = cursor.execute("SELECT MAX(usuario_id) FROM Metricas_Usuarios").fetchone()[0]
    if max_user_id is None: max_user_id = 0
            
    for i in range(n_usuarios_nuevos):
        cursor.execute("""
        INSERT INTO Metricas_Usuarios (usuario_id, rau_id_conectada, cqi_sinr_db, demanda_qos_mbps, timestamp_reporte)
        VALUES (?, ?, ?, ?, ?)
        """, (
            max_user_id + i + 1, # ID de usuario nuevo
            rau_id,               # Conectado a la RAU del evento
            random.uniform(10, 25), # SINR base
            random.uniform(demanda_min, demanda_max), # Demanda de la multitud
            current_time
        ))
    conn.commit()
    conn.close()

def evento_migracion_usuarios(rau_origen, rau_destino, n_usuarios_migran):
    """
    Simula usuarios moviéndose de una antena a otra.
    """
    print(f"\n[EVENTO DE SIMULACIÓN] ¡{n_usuarios_migran} usuarios se mueven de RAU #{rau_origen} a RAU #{rau_destino}!")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Encontrar N usuarios al azar en la RAU de origen
    cursor.execute("""
        SELECT reporte_id FROM Metricas_Usuarios
        WHERE rau_id_conectada = ?
        ORDER BY RANDOM()
        LIMIT ?
    """, (rau_origen, n_usuarios_migran))
    
    reportes_a_migrar = cursor.fetchall()
    ids_a_migrar = [r[0] for r in reportes_a_migrar]

    if not ids_a_migrar:
        print(f"[SIMULADOR] Advertencia: No hay suficientes usuarios en RAU #{rau_origen} para migrar.")
        conn.close()
        return
    
    # Actualizar su ubicación a la nueva RAU
    cursor.executemany("""
        UPDATE Metricas_Usuarios
        SET rau_id_conectada = ?
        WHERE reporte_id = ?
    """, [(rau_destino, r_id) for r_id in ids_a_migrar])
    
    conn.commit()
    conn.close()


# --- El Ciclo de Simulación Principal ---
def ejecutar_simulacion():
    
    print("==============================================")
    print("🚀 INICIO DE LA SIMULACIÓN DE RED ADAPTATIVA")
    print("==============================================")

    # --- TICK 1: ESTADO INICIAL (Red Saludable) ---
    print("\n--- TICK 1: Creando red 'saludable' inicial... ---")
    # Usamos la versión de demanda "fácil" (10-50 Mbps) en tu crear_db.py
    crear_db.setup_database()
    time.sleep(1)
    
    print("\n--- TICK 2: Agente optimiza la red 'saludable' ---")
    agente_con_db.ejecutar_ciclo_agente()
    print("==============================================")

    # --- TICK 3: EVENTO DE ESTRÉS ---
    time.sleep(3) # Pausa dramática
    evento_aumento_demanda(rau_id=3, n_usuarios_nuevos=20, demanda_min=100, demanda_max=300)
    time.sleep(1)

    # --- TICK 4: ADAPTACIÓN DEL AGENTE ---
    print("\n--- TICK 3: Agente detecta el estrés y se readapta... ---")
    agente_con_db.ejecutar_ciclo_agente()
    print("==============================================")
    
    # --- TICK 5: EVENTO DE MIGRACIÓN ---
    time.sleep(3) # Pausa dramática
    evento_migracion_usuarios(rau_origen=3, rau_destino=7, n_usuarios_migran=20)
    time.sleep(1)

    # --- TICK 6: ADAPTACIÓN FINAL ---
    print("\n--- TICK 4: Agente detecta la migración y rebalancea la red... ---")
    agente_con_db.ejecutar_ciclo_agente()
    print("==============================================")
    print("✅ SIMULACIÓN FINALIZADA")

if __name__ == "__main__":
    ejecutar_simulacion()