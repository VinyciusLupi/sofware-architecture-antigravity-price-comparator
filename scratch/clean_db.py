import sqlite3
import os

db_path = 'amazon_offers_history.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Busca variações que contenham 'Jogo' e 'Gen'
    cursor.execute("DELETE FROM cheapest_offers_history WHERE variant_name LIKE 'Jogo Gen%'")
    deleted = cursor.rowcount
    
    conn.commit()
    conn.close()
    print(f"Sucesso: {deleted} registros removidos.")
else:
    print("Erro: Banco de dados não encontrado.")
