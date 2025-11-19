import sqlite3
import pandas as pd
import random
import numpy as np

# --- 0. Constantes ---
DB_FILE = 'NGN_RoF.db'

# Parámetros del GA
TAMANO_POBLACION =50
TASA_MUTACION = 0.15 # 15% es una buena tasa para exploración
N_GENERACIONES = 40 # Mantenemos tus 200
TORNEO_K = 5 # Tamaño del torneo de selección

# --- 1. MÓDULO DE PERCEPCIÓN (Leer de la DB) ---
# (Sin cambios)
def percibir_entorno_db():
    print("Iniciando Percepción: Conectando a la base de datos...")
    conn = sqlite3.connect(DB_FILE)
    
    recursos = {}
    recursos['longitudes_onda'] = pd.read_sql_query("SELECT * FROM Recursos_Longitudes_Onda", conn)
    recursos['canales_mmwave'] = pd.read_sql_query("SELECT * FROM Recursos_Canales_mmWave", conn)
    recursos['niveles_potencia'] = pd.read_sql_query("SELECT * FROM Recursos_Niveles_Potencia", conn)

    # Nota: Leemos TODOS los usuarios, no solo los recientes.
    # Queremos saber la DEMANDA total, no el SINR.
    query_usuarios = "SELECT * FROM Metricas_Usuarios"
    df_usuarios = pd.read_sql_query(query_usuarios, conn)

    df_estado_rau = pd.read_sql_query("SELECT * FROM RAUs", conn)
    
    conn.close()
    print(f"Percepción completa: {len(df_usuarios)} reportes de usuario leídos.")
    
    return recursos, df_usuarios, df_estado_rau


# --- 2. MÓDULO DE ACCIÓN (Escribir en la DB) ---
# (Sin cambios)
def ejecutar_accion_db(mejor_solucion_df, recursos):
    print("\nIniciando Acción: Aplicando nueva configuración a la base de datos...")
    
    lambda_map = pd.Series(recursos['longitudes_onda'].lambda_id.values, 
                           index=recursos['longitudes_onda'].valor_lambda).to_dict()
    canal_map = pd.Series(recursos['canales_mmwave'].canal_id.values, 
                          index=recursos['canales_mmwave'].valor_canal).to_dict()
    potencia_map = pd.Series(recursos['niveles_potencia'].potencia_id.values, 
                             index=recursos['niveles_potencia'].valor_potencia_dbm).to_dict()
    
    solucion_con_ids = mejor_solucion_df.copy()
    solucion_con_ids['lambda_id'] = solucion_con_ids['longitud_onda'].map(lambda_map)
    solucion_con_ids['canal_id'] = solucion_con_ids['canal_mmwave'].map(canal_map)
    solucion_con_ids['potencia_id'] = solucion_con_ids['potencia'].map(potencia_map)

    if solucion_con_ids.isnull().values.any():
        print("Error: No se pudo mapear un valor de la solución a un ID de la base de datos.")
        print(solucion_con_ids[solucion_con_ids.isnull().any(axis=1)])
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for _, row in solucion_con_ids.iterrows():
        cursor.execute("""
            UPDATE RAUs
            SET config_actual_lambda_id = ?,
                config_actual_canal_id = ?,
                config_actual_potencia_id = ?
            WHERE rau_id = ?
        """, (int(row['lambda_id']), int(row['canal_id']), int(row['potencia_id']), int(row['rau_id'])))

    conn.commit()
    conn.close()
    
    print(f"Acción completada: {len(solucion_con_ids)} RAUs actualizadas en la base de datos.")


# --- 3. LÓGICA DEL AGENTE (Algoritmo Genético) ---

def crear_cromosoma(recursos_db, n_raus):
    # (Sin cambios)
    lista_lambdas = recursos_db['longitudes_onda']['valor_lambda'].tolist()
    lista_canales = recursos_db['canales_mmwave']['valor_canal'].tolist()
    lista_potencias = recursos_db['niveles_potencia']['valor_potencia_dbm'].tolist()

    cromosoma = []
    for i in range(n_raus):
        gen = {
            'longitud_onda': random.choice(lista_lambdas),
            'canal_mmwave': random.choice(lista_canales),
            'potencia': random.choice(lista_potencias)
        }
        cromosoma.append(gen)
    return cromosoma

# --- ¡NUEVA FUNCIÓN DE APTITUD! (El "Modelo Interno") ---
def calcular_aptitud(cromosoma, df_demanda_agg, interfer_matrix, n_raus):
    """
    Función de Aptitud (Fitness) BASADA EN MODELO.
    Ya no usa el SINR de la DB. Calcula un SINR simulado desde cero
    usando el modelo de interferencia (matriz).
    """
    
    # Pesos de la Función de Utilidad
    W_THROUGHPUT = 1.0  # Maximizar
    W_QOS_PENALTY = 2.0 # Minimizar (penalización fuerte)
    
    # Parámetros del Modelo Físico (Simulación)
    BW = 100e6 # Ancho de banda: 100 MHz (como acordamos)
    RUIDO_PISO = 1e-12 # Potencia de ruido de fondo (un valor pequeño)
    
    # Para convertir la potencia de dBm (DB) a Watts (Lineal) para los cálculos
    # P(W) = 10**((P(dBm) - 30) / 10)
    
    fitness_total = 0.0
    
    for i in range(n_raus):
        gen_i = cromosoma[i]
        rau_id_i = i + 1 # Asumiendo que los rau_id van de 1 a N
        
        # 1. Obtener la SEÑAL deseada
        # Convertimos la potencia de transmisión de dBm a Watts
        potencia_tx_W = 10**((gen_i['potencia'] - 30) / 10)
        
        # SIMULACIÓN DE SEÑAL: Asumimos una atenuación de señal (Path Loss) simple
        # En un modelo real, esto dependería de la distancia. Aquí es un valor fijo.
        path_loss_simple = 1e-10
        potencia_senal_recibida_W = potencia_tx_W * path_loss_simple

        # 2. Calcular la INTERFERENCIA total en esta RAU
        potencia_interferencia_total_W = 0.0
        
        for j in range(n_raus):
            if i == j:
                continue # Una RAU no interfiere consigo misma
            
            # El "Modelo Interno":
            # Si la RAU 'j' es vecina de 'i' Y usan el mismo canal...
            if interfer_matrix[i][j] == 1 and cromosoma[j]['canal_mmwave'] == gen_i['canal_mmwave']:
                
                # ...entonces su transmisión se convierte en interferencia.
                potencia_tx_j_W = 10**((cromosoma[j]['potencia'] - 30) / 10)
                
                # Asumimos que la interferencia sufre la misma atenuación
                potencia_interferencia_W = potencia_tx_j_W * path_loss_simple
                potencia_interferencia_total_W += potencia_interferencia_W

        # 3. Calcular SINR (Lineal, no en dB)
        # SINR = Señal / (Interferencia + Ruido)
        sinr_lineal = potencia_senal_recibida_W / (potencia_interferencia_total_W + RUIDO_PISO)
        
        # 4. Calcular Throughput (Shannon-Hartley)
        # C = BW * log2(1 + SINR)
        throughput_bps = BW * np.log2(1 + sinr_lineal)
        throughput_mbps = throughput_bps / 1e6 # Convertir a Mbps
        
        # 5. Calcular Penalización de QoS
        demanda_rau = 0
        if rau_id_i in df_demanda_agg.index:
            demanda_rau = df_demanda_agg.loc[rau_id_i]['demanda_total_mbps']
            
        penalizacion_qos_mbps = max(0, demanda_rau - throughput_mbps)

        # 6. Calcular Aptitud (Función de Utilidad [cite: 30])
        # Maximiza throughput, minimiza QoS incumplida
        aptitud_rau = (W_THROUGHPUT * throughput_mbps) - (W_QOS_PENALTY * penalizacion_qos_mbps)
        
        fitness_total += aptitud_rau

    return fitness_total


def seleccion(poblacion_con_aptitud, k=TORNEO_K):
    # (Sin cambios, pero optimizado)
    torneo = random.sample(poblacion_con_aptitud, k)
    torneo.sort(key=lambda x: x[1], reverse=True)
    return torneo[0][0]

def cruce(padre1, padre2):
    # (Sin cambios)
    punto_cruce = random.randint(1, len(padre1) - 1)
    hijo1 = padre1[:punto_cruce] + padre2[punto_cruce:]
    hijo2 = padre2[:punto_cruce] + padre1[punto_cruce:]
    return hijo1, hijo2

def mutacion(cromosoma, recursos_db):
    # (Usamos la "Super Mutación" que es más efectiva)
    lista_lambdas = recursos_db['longitudes_onda']['valor_lambda'].tolist()
    lista_canales = recursos_db['canales_mmwave']['valor_canal'].tolist()
    lista_potencias = recursos_db['niveles_potencia']['valor_potencia_dbm'].tolist()

    for i in range(len(cromosoma)):
        if random.random() < TASA_MUTACION:
            # Reemplazamos el gen [i] por uno completamente nuevo y aleatorio.
            cromosoma[i] = {
                'longitud_onda': random.choice(lista_lambdas),
                'canal_mmwave': random.choice(lista_canales),
                'potencia': random.choice(lista_potencias)
            }
    return cromosoma


# --- 4. CICLO PRINCIPAL (PEAS) - MODIFICADO ---

def crear_modelo_interferencia(n_raus, p_vecino=0.3):
    """
    Crea el "Modelo Interno" del agente.
    Simula el entorno urbano denso.
    
    Retorna una matriz NxN donde matrix[i][j] = 1 
    significa que RAU 'i' y 'j' están cerca e interfieren.
    """
    print(f"Construyendo modelo interno: Matriz de interferencia {n_raus}x{n_raus}...")
    matrix = np.zeros((n_raus, n_raus), dtype=int)
    for i in range(n_raus):
        for j in range(i + 1, n_raus): # Solo la mitad superior
            # Con probabilidad 'p_vecino', dos antenas son vecinas
            if random.random() < p_vecino:
                matrix[i][j] = 1
                matrix[j][i] = 1 # Es simétrico
    
    print("Modelo de interferencia construido.")
    return matrix

def ejecutar_ciclo_agente():
    
    # --- 1. PERCEPCIÓN (Leer de la DB) ---
    try:
        recursos_db, df_usuarios, df_estado_rau = percibir_entorno_db()
    except Exception as e:
        print(f"Error fatal al percibir el entorno: {e}")
        return

    N_RAUS = len(df_estado_rau)
    if N_RAUS == 0:
        print("Error: No se encontraron RAUs en la base de datos.")
        return

    # --- 2. MODELADO (Crear estado interno) ---
    
    # A) Construir el Modelo de Interferencia 
    # Esta matriz simula la geografía y qué RAUs son vecinas.
    interfer_matrix = crear_modelo_interferencia(N_RAUS, p_vecino=0.3) # 30% de prob. de ser vecinos
    
    # B) Procesar Percepción de Demanda
    # Agregamos la demanda total de QoS por RAU.
    # ESTO es lo que la función de aptitud usará, NO el SINR.
    df_demanda_agg = df_usuarios.groupby('rau_id_conectada').agg(
        demanda_total_mbps=('demanda_qos_mbps', 'sum')
    )

    print(f"Iniciando GA... optimizando {N_RAUS} RAUs.")
    
    # --- 3. DECISIÓN (Ejecución del GA) ---
    
    poblacion = [crear_cromosoma(recursos_db, N_RAUS) for _ in range(TAMANO_POBLACION)]
    
    mejor_solucion_global = None
    mejor_aptitud_global = -float('inf')
    
    for gen in range(N_GENERACIONES):
        
        poblacion_con_aptitud = []
        for cromosoma in poblacion:
            # ¡Aquí está la magia!
            # La aptitud se calcula usando el MODELO (interfer_matrix)
            # y la DEMANDA (df_demanda_agg), no el SINR de la DB.
            aptitud = calcular_aptitud(cromosoma, df_demanda_agg, interfer_matrix, N_RAUS)
            
            poblacion_con_aptitud.append((cromosoma, aptitud))
            
            if aptitud > mejor_aptitud_global:
                mejor_aptitud_global = aptitud
                mejor_solucion_global = cromosoma
        
        # Crear la siguiente generación
        nueva_poblacion = [mejor_solucion_global] # Elitismo: el mejor pasa directo
        
        while len(nueva_poblacion) < TAMANO_POBLACION:
            padre1 = seleccion(poblacion_con_aptitud)
            padre2 = seleccion(poblacion_con_aptitud)
            hijo1, hijo2 = cruce(padre1, padre2)
            nueva_poblacion.append(mutacion(hijo1, recursos_db))
            # Asegurarse de no exceder el tamaño
            if len(nueva_poblacion) < TAMANO_POBLACION:
                nueva_poblacion.append(mutacion(hijo2, recursos_db))
            
        poblacion = nueva_poblacion
        
        if (gen + 1) % 1 == 0:
            print(f"Generación {gen + 1}/{N_GENERACIONES} - Mejor Aptitud: {mejor_aptitud_global:.2f}")

    print("\nGA finalizado. Mejor asignación encontrada.")
    
    df_accion = pd.DataFrame(mejor_solucion_global)
    df_accion['rau_id'] = df_estado_rau['rau_id']

    print("Acción propuesta (nueva configuración de red):")
    print(df_accion[['rau_id', 'longitud_onda', 'canal_mmwave', 'potencia']])

    # --- 4. ACCIÓN (Escribir en la DB) ---
    ejecutar_accion_db(df_accion, recursos_db)


# --- Ejecutar el ciclo ---
if __name__ == "__main__":
    ejecutar_ciclo_agente()