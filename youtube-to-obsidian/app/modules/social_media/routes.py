import asyncio
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.core.database import get_db_connection
from app.modules.social_media.models import (
    CreatorCreate, CreatorResponse,
    ConfigCreate, ConfigResponse,
    PipelineResponse, PipelineResultResponse,
    PipelineRunRequest
)
from app.modules.social_media.apify import get_creator_metrics
from app.modules.social_media.agent import analyze_and_generate_concepts
from app.modules.social_media.obsidian_export import export_to_obsidian

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/social-media", tags=["social-media"])

# --- ROTAS DE CRIADORES ---

@router.get("/creators", response_model=List[CreatorResponse])
async def list_creators():
    """Lista todos os criadores de conteúdo que estão sendo rastreados."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creators ORDER BY added_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/creators", response_model=CreatorResponse)
async def add_creator(creator: CreatorCreate):
    """
    Adiciona um novo criador para rastreamento.
    Faz uma chamada concisa ao Apify para obter estatísticas do perfil.
    """
    import urllib.parse
    
    # 1. Limpar e extrair o username caso o usuário tenha colado uma URL ou colocado @
    original_input = creator.username.strip()
    raw_username = original_input
    
    # Se for uma URL completa
    if raw_username.startswith(("http://", "https://", "www.")):
        if not raw_username.startswith(("http://", "https://")):
            raw_username = "https://" + raw_username
        try:
            if creator.platform == "youtube":
                # Lógica especial para URLs do YouTube
                if "/@" in raw_username:
                    parts = raw_username.split("/@")
                    if len(parts) > 1:
                        raw_username = parts[1].split("/")[0]
                elif "/channel/" in raw_username:
                    parts = raw_username.split("/channel/")
                    if len(parts) > 1:
                        raw_username = "channel/" + parts[1].split("/")[0]
                elif "/c/" in raw_username:
                    parts = raw_username.split("/c/")
                    if len(parts) > 1:
                        raw_username = "c/" + parts[1].split("/")[0]
                elif "/user/" in raw_username:
                    parts = raw_username.split("/user/")
                    if len(parts) > 1:
                        raw_username = "user/" + parts[1].split("/")[0]
                else:
                    # Fallback
                    parsed = urllib.parse.urlparse(raw_username)
                    path = parsed.path.strip("/")
                    parts = path.split("/")
                    if parts:
                        raw_username = parts[-1]
            else:
                parsed = urllib.parse.urlparse(raw_username)
                # Remove barras no início/fim e divide
                path = parsed.path.strip("/")
                parts = path.split("/")
                if parts:
                    raw_username = parts[0]
        except Exception as pe:
            logger.warning(f"Erro ao fazer o parse da URL do criador: {pe}")
            
    # Remove query string se ainda existir
    if "?" in raw_username:
        raw_username = raw_username.split("?")[0]
        
    # Remove caractere @ se existir no início
    if raw_username.startswith("@"):
        raw_username = raw_username[1:]
        
    # Limpeza final de espaços e barras
    clean_username = raw_username.strip().rstrip("/")
    
    if not clean_username:
        raise HTTPException(
            status_code=400,
            detail="Username inválido. Certifique-se de preencher o nome do criador ou a URL do perfil."
        )
        
    # Atualiza o objeto com o username limpo
    creator.username = clean_username
    logger.info(f"Username limpo extraído: '{creator.username}' (original: '{original_input}')")

    # 2. Buscar métricas do perfil via Apify com base na time_window selecionada
    try:
        metrics = await get_creator_metrics(creator.username, creator.platform, creator.time_window)
    except Exception as e:
        logger.exception(f"Erro ao buscar métricas do criador @{creator.username} via Apify")
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível obter dados para @{creator.username}. Verifique se a conta existe ou está pública. Erro: {e}"
        )
        
    followers = metrics.get("followers_count") or 0
    avg_views = metrics.get("average_views") or 0
    posts_per_month = metrics.get("posts_per_month") or 0
    now = datetime.now().isoformat()
    
    # 2. Salvar no banco de dados (SQLite)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO creators (username, platform, category, followers_count, average_views, posts_per_month, time_window, last_scraped, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                platform = excluded.platform,
                category = excluded.category,
                followers_count = excluded.followers_count,
                average_views = excluded.average_views,
                posts_per_month = excluded.posts_per_month,
                time_window = excluded.time_window,
                last_scraped = excluded.last_scraped
            """, (creator.username, creator.platform, creator.category, followers, avg_views, posts_per_month, creator.time_window, now, now))
            conn.commit()
            
            # Recuperar o criador salvo
            cursor.execute("SELECT * FROM creators WHERE username = ?", (creator.username,))
            row = cursor.fetchone()
            return dict(row)
        except Exception as e:
            logger.exception("Erro ao salvar criador no banco")
            raise HTTPException(status_code=500, detail=f"Erro interno ao salvar no banco: {e}")

@router.delete("/creators/{id}")
async def delete_creator(id: int):
    """Deleta um criador do rastreamento."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM creators WHERE id = ?", (id,))
        conn.commit()
    return {"message": "Criador removido com sucesso"}


# --- ROTAS DE CONFIGURAÇÃO ---

@router.get("/configs", response_model=List[ConfigResponse])
async def list_configs():
    """Lista todas as configurações registradas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM configs ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.post("/configs", response_model=ConfigResponse)
async def create_config(config: ConfigCreate):
    """Cria uma nova configuração de análise e conceitos."""
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO configs (name, category, analysis_instructions, concepts_instructions, limit_top_k, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                category = excluded.category,
                analysis_instructions = excluded.analysis_instructions,
                concepts_instructions = excluded.concepts_instructions,
                limit_top_k = excluded.limit_top_k
            """, (config.name, config.category, config.analysis_instructions, config.concepts_instructions, config.limit_top_k, now))
            conn.commit()
            
            cursor.execute("SELECT * FROM configs WHERE name = ?", (config.name,))
            row = cursor.fetchone()
            return dict(row)
        except Exception as e:
            logger.exception("Erro ao criar configuração")
            raise HTTPException(status_code=500, detail=f"Erro ao salvar configuração: {e}")


# --- ROTAS DE PIPELINE (EXECUÇÃO E HISTÓRICO) ---

@router.get("/pipelines", response_model=List[PipelineResponse])
async def list_pipelines():
    """Lista o histórico de execuções de pipelines."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pipelines ORDER BY run_date DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

@router.get("/pipelines/{id}/results", response_model=List[PipelineResultResponse])
async def get_pipeline_results(id: int):
    """Retorna os resultados de uma execução específica de pipeline."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT pr.*, c.username as creator_username 
        FROM pipeline_results pr
        JOIN creators c ON pr.creator_id = c.id
        WHERE pr.pipeline_id = ?
        ORDER BY pr.views DESC
        """, (id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

async def run_pipeline_background(pipeline_id: int, config_id: int):
    """Tarefa de segundo plano para rodar o scraping e análise do pipeline."""
    logger.info(f"Iniciando pipeline {pipeline_id} em background...")
    try:
        # 1. Carregar Config
        with get_db_connection() as conn:
            conn.row_factory = None  # Para retornar tuplas limpas se necessário
            cursor = conn.cursor()
            cursor.execute("SELECT category, analysis_instructions, concepts_instructions, limit_top_k FROM configs WHERE id = ?", (config_id,))
            config_row = cursor.fetchone()
            
            if not config_row:
                raise ValueError("Configuração não encontrada")
                
            category, analysis_insts, concepts_insts, limit_top_k = config_row
            
            # 2. Carregar Criadores do mesmo Nicho/Categoria
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, platform, time_window FROM creators WHERE category = ?", (category,))
            creators = cursor.fetchall()
            
        if not creators:
            logger.warning(f"Nenhum criador cadastrado para a categoria: {category}")
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE pipelines SET status = 'failed' WHERE id = ?", (pipeline_id,))
                conn.commit()
            return
            
        # 3. Executar o processamento por criador
        for creator_id, username, platform, time_window in creators:
            try:
                logger.info(f"Processando criador @{username} no pipeline {pipeline_id}")
                # Buscar posts dele
                metrics = await get_creator_metrics(username, platform, time_window)
                posts = metrics.get("parsed_posts", [])
                
                # Filtrar os top-K mais virais (maior contagem de views)
                # O parsing já retorna posts ordenados? Por segurança vamos re-ordenar desc.
                posts.sort(key=lambda x: x["views"], reverse=True)
                top_posts = posts[:limit_top_k]
                
                for post in top_posts:
                    try:
                        # Analisar e gerar novos roteiros via Anthropic Claude
                        result = await analyze_and_generate_concepts(
                            video_details={
                                "video_url": post["video_url"],
                                "views": post["views"],
                                "caption": post["caption"],
                                "platform": platform
                            },
                            analysis_instructions=analysis_insts,
                            concepts_instructions=concepts_insts
                        )
                        
                        # Salvar o resultado
                        now = datetime.now().isoformat()
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                            INSERT INTO pipeline_results (pipeline_id, creator_id, video_url, views, platform, caption, thumbnail, analysis, concepts, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (pipeline_id, creator_id, post["video_url"], post["views"], platform, post["caption"], post["thumbnail"], result["analysis"], result["concepts"], now))
                            conn.commit()
                            
                    except Exception as inner_e:
                        logger.error(f"Erro ao processar post {post.get('video_url')} do criador @{username}: {repr(inner_e)}")
                        continue
                    finally:
                        # Pequeno intervalo para não estourar rate limit da API Anthropic
                        await asyncio.sleep(2.0)
                        
            except Exception as e:
                logger.error(f"Erro ao processar criador @{username} no pipeline {pipeline_id}: {e}")
                continue
                
        # 4. Finalizar pipeline com sucesso
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pipelines SET status = 'completed' WHERE id = ?", (pipeline_id,))
            conn.commit()
        logger.info(f"Pipeline {pipeline_id} finalizado com sucesso!")
        
    except Exception as e:
        logger.exception(f"Erro crítico no pipeline {pipeline_id}")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE pipelines SET status = 'failed' WHERE id = ?", (pipeline_id,))
            conn.commit()

@router.post("/pipelines/run", response_model=PipelineResponse)
async def run_pipeline(request: PipelineRunRequest, background_tasks: BackgroundTasks):
    """Dispara a execução de um pipeline de scraping e IA em segundo plano."""
    now = datetime.now().isoformat()
    
    # 1. Verificar se a configuração existe
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, category FROM configs WHERE id = ?", (request.config_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Configuração não encontrada")
        config_id, category = row[0], row[1]
        
        # Verificar se há criadores no nicho da config
        cursor.execute("SELECT COUNT(*) FROM creators WHERE category = ?", (category,))
        count = cursor.fetchone()[0]
        if count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Não há criadores cadastrados no nicho '{category}' dessa configuração. Cadastre criadores antes de executar."
            )
            
        # 2. Registrar o pipeline como running
        cursor.execute("""
        INSERT INTO pipelines (config_id, run_date, status)
        VALUES (?, ?, 'running')
        """, (request.config_id, now))
        conn.commit()
        
        pipeline_id = cursor.lastrowid
        
        # Recuperar registro do pipeline criado
        cursor.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,))
        pipeline_row = cursor.fetchone()
        
    # 3. Disparar processamento assíncrono em background
    background_tasks.add_task(run_pipeline_background, pipeline_id, config_id)
    
    return dict(pipeline_row)


# --- ROTAS DE EXPORTAÇÃO ---

@router.post("/results/{id}/export")
async def export_result(id: int):
    """Busca o resultado do pipeline pelo ID e gera o arquivo Markdown no vault do Obsidian."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT pr.*, c.username, c.category 
        FROM pipeline_results pr
        JOIN creators c ON pr.creator_id = c.id
        WHERE pr.id = ?
        """, (id,))
        row = cursor.fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail="Resultado de pipeline não encontrado")
        
    res = dict(row)
    
    try:
        file_path = export_to_obsidian(
            creator_username=res["username"],
            platform=res["platform"],
            video_url=res["video_url"],
            views=res["views"],
            category=res["category"],
            analysis=res["analysis"],
            concepts=res["concepts"]
        )
        return {"status": "exported", "file_path": file_path}
    except Exception as e:
        logger.exception("Erro ao exportar conceito para o Obsidian")
        raise HTTPException(status_code=500, detail=f"Erro ao exportar arquivo para o Obsidian Vault: {e}")
