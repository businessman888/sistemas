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

        # 11. Tabela: brain_chat_sessions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_chat_sessions (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            persona_id INTEGER REFERENCES clones(id) ON DELETE SET NULL,
            is_clone_only INTEGER DEFAULT 0,
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL
        )
        """)

        # 12. Tabela: brain_chat_messages
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_chat_messages (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES brain_chat_sessions(id) ON DELETE CASCADE,
            role VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            sources_json TEXT,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            cost_usd DOUBLE PRECISION DEFAULT 0.0,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 13. Tabela: document_categories
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            parent_id INTEGER REFERENCES document_categories(id) ON DELETE CASCADE,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 14. Tabela: documents
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_name VARCHAR(255) NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type VARCHAR(100),
            category_id INTEGER REFERENCES document_categories(id) ON DELETE SET NULL,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 15. Tabela: financial_expenses
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_expenses (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            periodicity VARCHAR(50) NOT NULL,
            due_date VARCHAR(10) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at VARCHAR(100) NOT NULL
        )
        """)

        # 16. Tabela: credentials
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id SERIAL PRIMARY KEY,
            service_name VARCHAR(255) NOT NULL,
            login VARCHAR(500) NOT NULL,
            password VARCHAR(500) DEFAULT '',
            notes TEXT DEFAULT '',
            category VARCHAR(100) DEFAULT 'Geral',
            created_at VARCHAR(100) DEFAULT NOW()::text,
            updated_at VARCHAR(100) DEFAULT NOW()::text
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

        # Tabela: Sessões de Chat do Segundo Cérebro
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            persona_id INTEGER,
            is_clone_only INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(persona_id) REFERENCES clones(id) ON DELETE SET NULL
        )
        """)

        # Tabela: Mensagens de Chat do Segundo Cérebro
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS brain_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            sources_json TEXT,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES brain_chat_sessions(id) ON DELETE CASCADE
        )
        """)

        # Tabela: Categorias de Documentos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(parent_id) REFERENCES document_categories(id) ON DELETE CASCADE
        )
        """)

        # Tabela: Documentos / Arquivos
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type TEXT,
            category_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(category_id) REFERENCES document_categories(id) ON DELETE SET NULL
        )
        """)

        # Tabela: Despesas Financeiras
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS financial_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            periodicity TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # Tabela: Parâmetros e Métricas do Painel Executivo
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS executive_panel_metrics (
            metric_key TEXT PRIMARY KEY,
            metric_group TEXT NOT NULL,
            metric_label TEXT NOT NULL,
            metric_value REAL NOT NULL DEFAULT 0.0,
            unit TEXT DEFAULT 'BRL',
            notes TEXT,
            updated_at TEXT NOT NULL
        )
        """)

        # Tabela: Performance por Formato de Mídia
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS media_performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            format_name TEXT NOT NULL UNIQUE,
            clicks INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            cpa REAL DEFAULT 0.0,
            revenue_generated REAL DEFAULT 0.0,
            notes TEXT,
            updated_at TEXT NOT NULL
        )
        """)

        # Tabela: credentials
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT NOT NULL,
            login TEXT NOT NULL,
            password TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            category TEXT DEFAULT 'Geral',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Seed inicial para o Painel Executivo se estiver vazio
        cursor.execute("SELECT COUNT(*) FROM executive_panel_metrics")
        if cursor.fetchone()[0] == 0:
            now_iso = datetime.now().isoformat()
            default_metrics = [
                ('capex_maintenance', 'cashflow', 'Capex de Manutenção', 15400.0, 'BRL', 'Investimento em manutenção', now_iso),
                ('tax_recurring', 'tax', 'Imposto Recorrente', 18500.0, 'BRL', 'Estimativa mensal', now_iso),
                ('working_capital', 'cashflow', 'Capital de Giro Total', 125000.0, 'BRL', 'Reserva de liquidez', now_iso),
                ('working_capital_growth', 'cashflow', 'Capital de Giro Aumentando', 12.5, '%', 'Crescimento do NCG', now_iso),
                ('bad_debt_provision', 'risk', 'Inadimplência Mal Provisionada', 4200.0, 'BRL', 'Provisão de perda', now_iso),
                ('client_concentration', 'risk', 'Cliente Concentrado (% Maior Cliente)', 18.5, '%', 'Risco de concentração', now_iso),
                ('partner_out_expense', 'governance', 'Despesa do Sócio Fora da Empresa', 3500.0, 'BRL', 'Retiradas não operacionais', now_iso),
                ('dcf_valuation', 'valuation', 'Valuation DCF', 4500000.0, 'BRL', 'Fluxo de Caixa Descontado', now_iso),
                ('future_cash_pv', 'valuation', 'Caixa Futuro Trazido a Valor Presente', 3850000.0, 'BRL', 'VP dos fluxos projetados', now_iso),
                ('ebitda_adjusted_deductions', 'dre', 'Deduções EBITDA (Ajustes)', 8500.0, 'BRL', 'Outras despesas não recorrentes', now_iso),
                ('partner_dividends', 'dre', 'Parte dos Sócios (Dividendos)', 35000.0, 'BRL', 'Distribuição de lucro', now_iso),
                ('dso_days', 'cashflow', 'Tempo Médio de Recebimento (PMR)', 38.0, 'dias', 'Média de dias para receber', now_iso),
                ('churn_rate', 'unit_economics', 'Churn Rate Mensal', 2.1, '%', 'Taxa de cancelamento', now_iso),
                ('arpu_user_margin', 'unit_economics', 'Margem por Usuário (ARPU Líquido)', 420.0, 'BRL', 'Lucro médio por cliente', now_iso),
                ('productivity_score', 'unit_economics', 'Produtividade Executiva', 94.5, '%', 'Eficiência de entrega', now_iso),
                ('yoy_growth', 'unit_economics', 'Crescimento % ao Ano', 48.2, '%', 'YoY Revenue Growth', now_iso),
                ('cpa_campaign', 'marketing', 'CPA de Campanha', 45.5, 'BRL', 'Custo por aquisição pago', now_iso),
                ('cpa_influencer', 'marketing', 'CPA de Influencer / Embaixador', 68.0, 'BRL', 'Custo por aquisição influência', now_iso),
            ]
            cursor.executemany(
                "INSERT INTO executive_panel_metrics (metric_key, metric_group, metric_label, metric_value, unit, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                default_metrics
            )

        # Seed inicial de mídias se vazio
        cursor.execute("SELECT COUNT(*) FROM media_performance_metrics")
        if cursor.fetchone()[0] == 0:
            now_iso = datetime.now().isoformat()
            default_media = [
                ('Reels Orgânico/Pago', 14200, 420, 38.5, 84000.0, 'Performance alta engajamento', now_iso),
                ('Post Estático', 6100, 115, 62.0, 23000.0, 'Conteúdo institucional', now_iso),
                ('Carrossel Educacional', 18500, 560, 32.1, 112000.0, 'Taxa de salvamento elevada', now_iso),
                ('Post Colab com Influencer', 22400, 890, 28.4, 178000.0, 'Excelente conversão direta', now_iso),
                ('Story Diario', 9800, 280, 41.0, 56000.0, 'Sequência de vendas', now_iso),
                ('Story de Influencer', 16500, 490, 48.0, 98000.0, 'Cupom específico', now_iso),
                ('Reels de Influencer', 31000, 1120, 24.5, 224000.0, 'Maior ROI da campanha', now_iso),
            ]
            cursor.executemany(
                "INSERT INTO media_performance_metrics (format_name, clicks, conversions, cpa, revenue_generated, notes, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                default_media
            )

        cursor.execute("SELECT COUNT(*) FROM credentials")
        if cursor.fetchone()[0] == 0:
            now_iso = datetime.now().isoformat()
            default_credentials = [
                ('Login INPI', 'oytotec', 'Lagorce369!', '', 'Governo', now_iso, now_iso),
                ('AWS', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'Cloud', now_iso, now_iso),
                ('Revenue Cat', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'SaaS', now_iso, now_iso),
                ('Fitbit', 'Google irineu', '', 'https://dev.fitbit.com/apps/new', 'API', now_iso, now_iso),
                ('Polar', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'API', now_iso, now_iso),
                ('Garmin', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'API', now_iso, now_iso),
                ('Google', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'Cloud', now_iso, now_iso),
                ('Apple', 'contato@oyto.com.br', 'SanmarinoLagorce02!', '', 'Cloud', now_iso, now_iso),
                ('Antigravity', 'Google irineu', '', '', 'AI', now_iso, now_iso),
                ('Claude', 'Google irineu', '', '', 'AI', now_iso, now_iso),
                ('Hostinger', 'Google irineu', '', '', 'Hosting', now_iso, now_iso),
                ('Google Irineu', 'irineuVieiramelo@gmail.com', 'j56486765', 'Conta pessoal', 'Pessoal', now_iso, now_iso),
                ('Superwall', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'SaaS', now_iso, now_iso),
                ('Asaas', 'contato@oytotecnologia.com', 'LagorceSanmarino369!', '', 'Financeiro', now_iso, now_iso),
                ('Github', 'businessman888', 'Jyc56486765!', '', 'Dev', now_iso, now_iso),
            ]
            cursor.executemany(
                "INSERT INTO credentials (service_name, login, password, notes, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                default_credentials
            )

        conn.commit()
    logger.info("Banco SQLite inicializado com sucesso!")
