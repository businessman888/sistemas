import httpx
import logging
import asyncio
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

# Configurações do Apify
API_URL = "https://api.apify.com/v2"

async def _trigger_actor_and_wait(actor_id: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Dispara um actor do Apify, faz polling até concluir e retorna os itens do dataset."""
    token = settings.apify_api_key
    if not token:
        raise ValueError("Apify API Key não está configurada no arquivo .env")

    headers = {"Content-Type": "application/json"}
    
    # 1. Iniciar a execução do Actor
    run_url = f"{API_URL}/acts/{actor_id}/runs?token={token}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info(f"Disparando actor Apify {actor_id}...")
        response = await client.post(run_url, json=payload, headers=headers)
        if response.status_code not in (200, 201):
            raise Exception(f"Falha ao disparar Actor do Apify: {response.text}")
        
        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId")
        
        if not run_id or not dataset_id:
            raise Exception("Apify não retornou run ID ou dataset ID.")
            
        logger.info(f"Actor {actor_id} iniciado. Run ID: {run_id}. Dataset ID: {dataset_id}")
        
        # 2. Polling para verificar conclusão
        status_url = f"{API_URL}/actor-runs/{run_id}?token={token}"
        max_attempts = 60  # ~10 minutos
        attempt = 0
        
        while attempt < max_attempts:
            await asyncio.sleep(10)
            status_response = await client.get(status_url)
            if status_response.status_code == 200:
                run_status = status_response.json().get("data", {}).get("status")
                logger.info(f"Status do Actor {actor_id} ({run_id}): {run_status}")
                
                if run_status == "SUCCEEDED":
                    break
                elif run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    raise Exception(f"Execução do Actor no Apify terminou com status de erro: {run_status}")
            attempt += 1
            
        if attempt >= max_attempts:
            raise TimeoutError(f"Tempo esgotado aguardando conclusão do Actor {actor_id}")
            
        # 3. Baixar resultados
        items_url = f"{API_URL}/datasets/{dataset_id}/items?token={token}"
        logger.info(f"Baixando resultados do dataset {dataset_id}...")
        items_response = await client.get(items_url)
        if items_response.status_code == 200:
            return items_response.json()
        else:
            raise Exception(f"Erro ao obter dados do dataset do Apify: {items_response.text}")

async def scrape_instagram_profile(username: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Raspagem de posts do Instagram de um determinado perfil usando Apify."""
    actor_id = "apify~instagram-post-scraper"
    # Documentação padrão do apify/instagram-post-scraper aceita username
    payload = {
        "username": [username],
        "resultsLimit": limit,
        "onlyPosts": False
    }
    return await _trigger_actor_and_wait(actor_id, payload)

async def scrape_tiktok_profile(username: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Raspagem de vídeos do TikTok de um perfil usando Apify clockworks/tiktok-scraper."""
    actor_id = "clockworks~tiktok-scraper"
    
    # Remove o @ se existir para passar apenas o username limpo no array
    clean_username = username[1:] if username.startswith("@") else username
    
    payload = {
        "profiles": [clean_username],
        "maxResults": limit,
        "profileScrapeSections": ["videos"],
        "proxyConfiguration": {
            "useApifyProxy": True
        }
    }
    logger.info(f"Acionando scraper do TikTok (clockworks) para perfil: {clean_username}")
    return await _trigger_actor_and_wait(actor_id, payload)

async def scrape_youtube_channel(username: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Raspagem de vídeos do YouTube de um canal usando Apify streamers/youtube-scraper."""
    actor_id = "streamers~youtube-scraper"
    
    # Reconstrói a URL do canal com base no formato do username
    if username.startswith(("channel/", "c/", "user/")):
        channel_url = f"https://www.youtube.com/{username}"
    elif username.startswith("@"):
        channel_url = f"https://www.youtube.com/{username}"
    else:
        channel_url = f"https://www.youtube.com/@{username}"
        
    payload = {
        "startUrls": [
            { "url": channel_url }
        ],
        "maxResults": limit,
        "maxResultsShorts": 0,
        "maxResultStreams": 0
    }
    logger.info(f"Acionando scraper do YouTube para: {channel_url}")
    return await _trigger_actor_and_wait(actor_id, payload)

def parse_abbreviated_number(val: Any) -> int:
    """Converte números abreviados (ex: '11.6K', '1.5M') ou normais em inteiros."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
        
    val_str = str(val).strip().upper()
    if not val_str:
        return 0
        
    # Remove símbolos não numéricos exceto ponto e sufixos
    suffix = ""
    for char in ["K", "M", "B"]:
        if char in val_str:
            suffix = char
            parts = val_str.split(char)[0]
            clean_num = "".join(c for c in parts if c.isdigit() or c in (".", ","))
            clean_num = clean_num.replace(",", ".")
            try:
                multiplier = 1000 if suffix == "K" else (1000000 if suffix == "M" else 1000000000)
                return int(float(clean_num) * multiplier)
            except ValueError:
                pass
                
    clean_num = "".join(c for c in val_str if c.isdigit())
    try:
        return int(clean_num) if clean_num else 0
    except ValueError:
        return 0

def parse_time_window(window_str: str) -> datetime:
    """Retorna o limite de tempo inferior com base na janela selecionada."""
    now = datetime.utcnow()
    if window_str == "1_week":
        return now - timedelta(days=7)
    elif window_str == "1_month":
        return now - timedelta(days=30)
    elif window_str == "3_months":
        return now - timedelta(days=90)
    # Default/Recent: sem limite estrito de data, confia no limite de itens
    return now - timedelta(days=365)

def get_platform_metrics(platform: str, items: List[Dict[str, Any]], window_str: str) -> Dict[str, Any]:
    """Calcula estatísticas (followers, visualizações médias, posts por mês) a partir dos dados brutos."""
    if not items:
        return {"followers_count": 0, "average_views": 0, "posts_per_month": 0, "parsed_posts": []}
        
    followers = 0
    views_list = []
    fallback_views_list = []
    parsed_posts = []
    
    cutoff_date = parse_time_window(window_str)
    
    # Datas para cálculo de posts/mês
    dates = []
    
    for item in items:
        try:
            # 1. Extrair Seguidores/Inscritos primeiro (independente de data/janela)
            if platform == "instagram":
                owner = item.get("owner", {})
                if owner.get("followersCount"):
                    followers = max(followers, int(owner.get("followersCount")))
                elif item.get("followersCount"):
                    followers = max(followers, int(item.get("followersCount")))
            elif platform == "tiktok":
                author = item.get("authorMeta", {})
                if author.get("fans"):
                    followers = max(followers, int(author.get("fans")))
            elif platform == "youtube":
                if item.get("numberOfSubscribers"):
                    followers = max(followers, parse_abbreviated_number(item.get("numberOfSubscribers")))
                elif item.get("subscriberCount"):
                    followers = max(followers, parse_abbreviated_number(item.get("subscriberCount")))

            # 2. Obter e parsear a data do post
            timestamp_raw = item.get("timestamp") or item.get("createTime") or item.get("datetime") or item.get("date")
            if not timestamp_raw:
                continue
                
            if isinstance(timestamp_raw, int):
                post_date = datetime.utcfromtimestamp(timestamp_raw)
            else:
                clean_ts = timestamp_raw.split(".")[0].replace("Z", "")
                post_date = datetime.fromisoformat(clean_ts)
                
            dates.append(post_date)
            
            # 3. Obter dados do post para o fallback (todas as views)
            if platform == "instagram":
                views = item.get("videoPlayCount") or item.get("playCount") or item.get("likesCount", 0)
                video_url = item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode')}/"
                caption = item.get("caption", "")
                thumbnail = item.get("displayUrl")
            elif platform == "tiktok":
                views = item.get("playCount") or item.get("videoMeta", {}).get("playCount", 0)
                video_url = item.get("videoUrl") or item.get("webVideoUrl")
                caption = item.get("text") or item.get("desc", "")
                thumbnail = item.get("coverUrl") or item.get("dynamicCover")
            elif platform == "youtube":
                views = item.get("viewCount") or 0
                video_url = item.get("url") or f"https://www.youtube.com/watch?v={item.get('id')}"
                caption = item.get("title", "")
                thumbnail = item.get("thumbnailUrl")
                
            fallback_views_list.append(int(views))
            
            # Filtro por janela de tempo
            if window_str != "recent" and post_date < cutoff_date:
                continue
                
            views_list.append(int(views))
            parsed_posts.append({
                "video_url": video_url,
                "views": int(views),
                "caption": caption,
                "thumbnail": thumbnail,
                "published_at": post_date.isoformat()
            })
            
        except Exception as e:
            logger.warning(f"Erro ao processar post no parser de métricas: {e}")
            continue
            
    # Calcular posts por mês
    if dates:
        dates.sort()
        span_days = (dates[-1] - dates[0]).days
        if span_days < 7:
            # Se for muito curto, estimamos baseado na quantidade
            posts_per_month = len(dates) * 4
        else:
            posts_per_month = int(len(dates) / (span_days / 30.0))
    else:
        posts_per_month = 0
        
    if views_list:
        avg_views = int(sum(views_list) / len(views_list))
    else:
        avg_views = int(sum(fallback_views_list) / len(fallback_views_list)) if fallback_views_list else 0
        
    # Fallback: Se nenhum post passou pelo filtro de data, vamos usar os posts recentes como fallback
    # para garantir que o pipeline tenha vídeos para analisar e o usuário receba resultados.
    if not parsed_posts and fallback_views_list:
        logger.info("Nenhum post encontrado na janela de tempo especificada. Usando posts recentes como fallback.")
        for item in items:
            try:
                if platform == "instagram":
                    views = item.get("videoPlayCount") or item.get("playCount") or item.get("likesCount", 0)
                    video_url = item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode')}/"
                    caption = item.get("caption", "")
                    thumbnail = item.get("displayUrl")
                elif platform == "tiktok":
                    views = item.get("playCount") or item.get("videoMeta", {}).get("playCount", 0)
                    video_url = item.get("videoUrl") or item.get("webVideoUrl")
                    caption = item.get("text") or item.get("desc", "")
                    thumbnail = item.get("coverUrl") or item.get("dynamicCover")
                elif platform == "youtube":
                    views = item.get("viewCount") or 0
                    video_url = item.get("url") or f"https://www.youtube.com/watch?v={item.get('id')}"
                    caption = item.get("title", "")
                    thumbnail = item.get("thumbnailUrl")
                
                timestamp_raw = item.get("timestamp") or item.get("createTime") or item.get("datetime") or item.get("date")
                if timestamp_raw:
                    if isinstance(timestamp_raw, int):
                        post_date = datetime.utcfromtimestamp(timestamp_raw)
                    else:
                        clean_ts = timestamp_raw.split(".")[0].replace("Z", "")
                        post_date = datetime.fromisoformat(clean_ts)
                    post_date_str = post_date.isoformat()
                else:
                    post_date_str = datetime.utcnow().isoformat()

                parsed_posts.append({
                    "video_url": video_url,
                    "views": int(views),
                    "caption": caption,
                    "thumbnail": thumbnail,
                    "published_at": post_date_str
                })
            except Exception:
                continue

    return {
        "followers_count": followers,
        "average_views": avg_views,
        "posts_per_month": posts_per_month,
        "parsed_posts": parsed_posts
    }

async def scrape_instagram_profile_info(username: str) -> Optional[int]:
    """Obtém o número de seguidores do perfil de forma dedicada usando o profile scraper."""
    actor_id = "apify~instagram-profile-scraper"
    payload = {
        "usernames": [username]
    }
    try:
        logger.info(f"Buscando seguidores dedicados do perfil @{username}...")
        results = await _trigger_actor_and_wait(actor_id, payload)
        if results and isinstance(results, list):
            followers = results[0].get("followersCount")
            if followers is not None:
                return int(followers)
    except Exception as e:
        logger.warning(f"Erro ao obter seguidores via profile scraper: {e}")
    return None

async def get_creator_metrics(username: str, platform: str, window_str: str) -> Dict[str, Any]:
    """Busca posts do criador baseado na janela de tempo e retorna métricas estruturadas."""
    limit = 15
    if window_str == "3_months":
        limit = 40  # Histórico maior
    elif window_str == "1_month":
        limit = 25
        
    if platform == "instagram":
        # Roda o scraper de posts e o scraper de profile em paralelo para não adicionar latência
        posts_task = scrape_instagram_profile(username, limit)
        profile_task = scrape_instagram_profile_info(username)
        
        items, followers_dedicated = await asyncio.gather(posts_task, profile_task)
        
        metrics = get_platform_metrics(platform, items, window_str)
        if followers_dedicated is not None:
            metrics["followers_count"] = followers_dedicated
        return metrics
    elif platform == "tiktok":
        items = await scrape_tiktok_profile(username, limit)
        return get_platform_metrics(platform, items, window_str)
    elif platform == "youtube":
        items = await scrape_youtube_channel(username, limit)
        return get_platform_metrics(platform, items, window_str)
    else:
        raise ValueError(f"Plataforma inválida: {platform}")
