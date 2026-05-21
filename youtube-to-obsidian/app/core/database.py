import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """Retorna uma conexão aberta com o banco SQLite."""
    db_path = Path(settings.database_path)
    # Garante que a pasta pai existe
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa as tabelas no banco de dados se não existirem."""
    logger.info("Inicializando banco de dados...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Tabela: Criadores
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            platform TEXT NOT NULL,
            category TEXT NOT NULL,
            followers_count INTEGER DEFAULT 0,
            average_views INTEGER DEFAULT 0,
            posts_per_month INTEGER DEFAULT 0,
            time_window TEXT NOT NULL,
            last_scraped TEXT,
            added_at TEXT NOT NULL
        )
        """)
        
        # Tabela: Configurações
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            analysis_instructions TEXT NOT NULL,
            concepts_instructions TEXT NOT NULL,
            limit_top_k INTEGER DEFAULT 3,
            created_at TEXT NOT NULL
        )
        """)
        
        # Tabela: Pipelines de Execução
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            run_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(config_id) REFERENCES configs(id)
        )
        """)
        
        # Tabela: Resultados do Pipeline
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id INTEGER NOT NULL,
            creator_id INTEGER NOT NULL,
            video_url TEXT NOT NULL,
            views INTEGER DEFAULT 0,
            platform TEXT NOT NULL,
            caption TEXT,
            thumbnail TEXT,
            analysis TEXT,
            concepts TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(pipeline_id) REFERENCES pipelines(id),
            FOREIGN KEY(creator_id) REFERENCES creators(id)
        )
        """)

        # Tabela: Clones de Mentes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            channel_url TEXT NOT NULL,
            max_videos INTEGER DEFAULT 10,
            status TEXT NOT NULL,
            blueprint TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Tabela: Mensagens do Chat com Clones
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clone_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clone_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(clone_id) REFERENCES clones(id) ON DELETE CASCADE
        )
        """)

        # Tabela: Projetos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Tabela: Fases do Projeto (Nós do Canvas)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            pos_x REAL DEFAULT 100,
            pos_y REAL DEFAULT 100,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)

        # Tabela: Conexões do Canvas (Arestas/Setas)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            from_phase_id INTEGER NOT NULL,
            to_phase_id INTEGER NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(from_phase_id) REFERENCES project_phases(id) ON DELETE CASCADE,
            FOREIGN KEY(to_phase_id) REFERENCES project_phases(id) ON DELETE CASCADE,
            UNIQUE(from_phase_id, to_phase_id)
        )
        """)

        # Tabela: Subtarefas de uma Fase do Projeto
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_phase_subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            FOREIGN KEY(phase_id) REFERENCES project_phases(id) ON DELETE CASCADE
        )
        """)
        
        conn.commit()
    logger.info("Banco de dados inicializado com sucesso!")

