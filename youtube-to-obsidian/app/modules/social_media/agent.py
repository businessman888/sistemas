import httpx
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

async def analyze_and_generate_concepts(
    video_details: Dict[str, Any],
    analysis_instructions: str,
    concepts_instructions: str
) -> Dict[str, str]:
    """
    Envia as instruções de análise e contexto de conceitos para o Claude
    a fim de analisar o vídeo do concorrente e gerar novas ideias e roteiros para o usuário.
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("Anthropic API Key não está configurada no arquivo .env")
        
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    caption = video_details.get("caption") or "(Sem legenda)"
    views = video_details.get("views") or 0
    url = video_details.get("video_url") or ""
    platform = video_details.get("platform") or "Rede Social"
    
    prompt = f"""
Você é um especialista em marketing viral de redes sociais (Instagram Reels, TikTok e YouTube).
Sua tarefa é analisar o vídeo de um concorrente de sucesso e criar novos conceitos de vídeos para o usuário com roteiros prontos, aplicando engenharia reversa.

---
### DADOS DO VÍDEO CONCORRENTE:
- **Plataforma:** {platform}
- **Visualizações:** {views}
- **URL do Vídeo:** {url}
- **Legenda/Roteiro aproximado do vídeo:**
{caption}

---
### INSTRUÇÕES DE ANÁLISE:
{analysis_instructions}

---
### INSTRUÇÕES PARA GERAÇÃO DOS MEUS NOVOS CONCEITOS E ROTEIROS:
{concepts_instructions}

---
### FORMATO DE RESPOSTA OBRIGATÓRIO:
Você deve retornar sua resposta contendo exatamente duas partes delimitadas por tags XML, como mostrado abaixo. Seja detalhado e fale em português.

<analysis>
(Escreva a análise detalhada do vídeo do concorrente aqui, baseando-se nas INSTRUÇÕES DE ANÁLISE. Fale sobre o Gancho/Hook, Retenção, Recompensa e Estrutura.)
</analysis>

<concepts>
(Escreva os novos conceitos e roteiros gerados para mim aqui, baseando-se nas INSTRUÇÕES PARA GERAÇÃO. Escreva os scripts inteiros que posso gravar agora.)
</concepts>
"""

    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 8192,
        "temperature": 1.0,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "system": "Você é um estrategista digital especializado em conteúdo de alto engajamento no Instagram Reels, TikTok e YouTube."
    }
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        logger.info("Enviando requisição para a API da Anthropic...")
        response = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Falha na API da Anthropic: {response.text}")
            
        res_data = response.json()
        content_list = res_data.get("content", [])
        
        if not content_list:
            raise Exception("Claude retornou uma resposta vazia.")
            
        full_text = content_list[0].get("text", "")
        
        # Parseando as tags <analysis> e <concepts>
        analysis_content = ""
        concepts_content = ""
        
        try:
            if "<analysis>" in full_text and "</analysis>" in full_text:
                analysis_content = full_text.split("<analysis>")[1].split("</analysis>")[0].strip()
            if "<concepts>" in full_text and "</concepts>" in full_text:
                concepts_content = full_text.split("<concepts>")[1].split("</concepts>")[0].strip()
        except Exception as e:
            logger.warning(f"Erro ao parsear tags da resposta do Claude: {e}")
            
        if not analysis_content or not concepts_content:
            # Fallback se as tags falharem
            logger.warning("Falha ao parsear tags. Salvando texto bruto.")
            parts = full_text.split("---")
            if len(parts) >= 2:
                analysis_content = parts[0].strip()
                concepts_content = "".join(parts[1:]).strip()
            else:
                analysis_content = full_text
                concepts_content = "Claude não separou adequadamente os conceitos."
                
        return {
            "analysis": analysis_content,
            "concepts": concepts_content
        }
