import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from collections.abc import Mapping
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

class PostgresRow(Mapping):
    """
    Simula o comportamento de sqlite3.Row para o PostgreSQL.
    Permite acesso a campos por chave (row['name']) e por índice numérico (row[0]),
    além de suportar dict(row).
    """
    def __init__(self, description, values):
        self._keys = [desc[0] for desc in description]
        self._values = values
        self._dict = dict(zip(self._keys, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict[key]

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)

    def keys(self):
        return self._keys

    def values(self):
        return self._values

class PostgresCursorWrapper:
    """
    Wrapper para o cursor do PostgreSQL que:
    1. Traduz automaticamente parâmetros ? do SQLite para %s do Postgres.
    2. Injeta RETURNING id nas queries de INSERT para simular o lastrowid do SQLite.
    3. Converte os resultados para objetos PostgresRow que emulam sqlite3.Row.
    """
    def __init__(self, cursor):
        self._cursor = cursor
        self._lastrowid = None

    def execute(self, sql, params=None):
        if sql:
            # 1. Traduz os placeholders "?" para "%s"
            sql = sql.replace("?", "%s")
            
            # 2. Emula lastrowid injetando RETURNING id para INSERTS
            is_insert = sql.strip().upper().startswith("INSERT")
            if is_insert and "RETURNING" not in sql.upper():
                sql = sql.rstrip(";").strip() + " RETURNING id"
        else:
            is_insert = False

        # Executa a query
        if params:
            self._cursor.execute(sql, params)
        else:
            self._cursor.execute(sql)

        # Se foi INSERT, consome e salva o ID gerado
        if is_insert:
            try:
                row = self._cursor.fetchone()
                if row:
                    self._lastrowid = row[0]
            except Exception:
                self._lastrowid = None
        else:
            self._lastrowid = None

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is not None:
            return PostgresRow(self._cursor.description, row)
        return None

    def fetchall(self):
        rows = self._cursor.fetchall()
        if rows:
            desc = self._cursor.description
            return [PostgresRow(desc, r) for r in rows]
        return []

    @property
    def lastrowid(self):
        return self._lastrowid

    def __getattr__(self, name):
        return getattr(self._cursor, name)

class PostgresConnectionWrapper:
    """
    Wrapper para a conexão do PostgreSQL que emula o gerenciador
    de contexto do sqlite3 (fecha a conexão e faz commit/rollback automaticamente).
    """
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PostgresCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

def get_db_connection():
    """
    Retorna uma conexão ativa com o banco.
    Se a DATABASE_URL estiver configurada no .env, conecta ao Postgres (Supabase).
    Caso contrário, conecta ao SQLite local.
    """
    if settings.database_url:
        if not HAS_POSTGRES:
            raise ImportError(
                "psycopg2-binary não está instalado. "
                "Por favor, execute: pip install psycopg2-binary"
            )
        try:
            conn = psycopg2.connect(settings.database_url)
            return PostgresConnectionWrapper(conn)
        except Exception as e:
            logger.error(f"Erro ao conectar ao banco PostgreSQL do Supabase: {e}")
            raise e
    else:
        db_path = Path(settings.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Inicializa as tabelas no banco de dados se não existirem."""
    logger.info("Inicializando banco de dados...")
    
    if settings.database_url:
        init_postgres()
    else:
        init_sqlite()

def init_postgres():
    """Cria tabelas no banco PostgreSQL se não existirem."""
    logger.info("Executando DDL para PostgreSQL no Supabase...")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Tabela: creators
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS creators (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            platform VARCHAR(100) NOT NULL,
            category VARCHAR(255) NOT NULL,
            followers_count INTEGER DEFAULT 0,
            average_views INTEGER DEFAULT 0,
            posts_per_month INTEGER DEFAULT 0,
            time_window VARCHAR(100) NOT NULL,
            last_scraped VARCHAR(100),
            added_at VARCHAR(100) NOT NULL
        )
        """)
        
        # 2. Tabela: configs
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            category VARCHAR(255) NOT NULL,
            analysis_instructions TEXT NOT NULL,
            concepts_instructions TEXT NOT NULL,
            limit_top_k INTEGER DEFAULT 3,
            created_at VARCHAR(100) NOT NULL
        )
        """)
        
        # 3. Tabela: pipelines
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipelines (
            id SERIAL PRIMARY KEY,
            config_id INTEGER NOT NULL REFERENCES configs(id) ON DELETE CASCADE,
            run_date VARCHAR(100) NOT NULL,
            status VARCHAR(100) NOT NULL
        )
        """)
        
        # 4. Tabela: pipeline_results
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_results (
            id SERIAL PRIMARY KEY,
            pipeline_id INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
            creator_id INTEGER NOT NULL REFERENCES creators(id) ON DELETE CASCADE,
            video_url TEXT NOT NULL,
            views INTEGER DEFAULT 0,
            platform VARCHAR(100) NOT NULL,
            caption TEXT,
            thumbnail TEXT,
            analysis TEXT,
            concepts TEXT,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 5. Tabela: clones
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clones (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            channel_url TEXT NOT NULL,
            max_videos INTEGER DEFAULT 10,
            status VARCHAR(100) NOT NULL,
            blueprint TEXT,
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL
        )
        """)

        # 6. Tabela: clone_messages
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clone_messages (
            id SERIAL PRIMARY KEY,
            clone_id INTEGER NOT NULL REFERENCES clones(id) ON DELETE CASCADE,
            role VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 7. Tabela: projects
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL
        )
        """)

        # 8. Tabela: project_phases
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_phases (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(100) NOT NULL DEFAULT 'pending',
            pos_x REAL DEFAULT 100,
            pos_y REAL DEFAULT 100
        )
        """)

        # 9. Tabela: project_connections
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_connections (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            from_phase_id INTEGER NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            to_phase_id INTEGER NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            UNIQUE(from_phase_id, to_phase_id)
        )
        """)

        # 10. Tabela: project_phase_subtasks
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_phase_subtasks (
            id SERIAL PRIMARY KEY,
            phase_id INTEGER NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            status VARCHAR(100) NOT NULL DEFAULT 'pending'
        )
        """)
        
        conn.commit()
    logger.info("Banco PostgreSQL inicializado com sucesso!")

def init_sqlite():
    """Cria tabelas no banco SQLite local se não existirem."""
    logger.info("Executando DDL para SQLite local...")
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
    logger.info("Banco SQLite inicializado com sucesso!")
