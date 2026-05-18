import os
import sys

# Adiciona a raiz do projeto ao sys.path para imports do app funcionarem
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.graph import update_vault_graph

def run():
    print("Iniciando migração do vault para conexão de grafo e extração de tópicos...")
    try:
        res = update_vault_graph()
        if res:
            notes, connections = res
            print(f"Migração concluída com sucesso!")
            print(f"Notas processadas: {notes}")
            print(f"Conexões de grafo escritas: {connections}")
        else:
            print("Nenhuma alteração foi realizada. Talvez não haja vídeos suficientes no vault.")
    except Exception as e:
        print(f"Erro durante a migração: {e}")

if __name__ == "__main__":
    run()
