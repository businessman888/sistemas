import os
import time
import logging
import asyncio
import threading
from typing import AsyncIterator, Iterator, List, Dict, Any, Optional
from anthropic import Anthropic, AsyncAnthropic
from app.core.config import settings

logger = logging.getLogger(__name__)

def map_model_name(model_name: Optional[str]) -> str:
    """Retorna o nome do modelo configurado ou informado, sem mapeamento."""
    if not model_name:
        return settings.anthropic_model_default
    return model_name

class UsageTracker:
    """Classe thread-safe para rastreamento de custos e uso de tokens na Anthropic."""
    def __init__(self):
        self._lock = threading.Lock()
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_creation_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cost = 0.0

    def add_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0
    ) -> float:
        # Resolve preços com base no modelo (Haiku vs Sonnet)
        is_haiku = "haiku" in model.lower()
        if is_haiku:
            base_input = 0.80 / 1_000_000.0
            base_output = 4.00 / 1_000_000.0
            cache_creation = 1.00 / 1_000_000.0
            cache_read = 0.08 / 1_000_000.0
        else:
            base_input = 3.00 / 1_000_000.0
            base_output = 15.00 / 1_000_000.0
            cache_creation = 3.75 / 1_000_000.0
            cache_read = 0.30 / 1_000_000.0

        # Para Anthropic, input_tokens reportados já incluem cache_creation e cache_read.
        # Deduzimos para calcular o custo dos tokens normais de entrada.
        std_input = max(0, input_tokens - cache_creation_tokens - cache_read_tokens)
        
        cost = (
            (std_input * base_input) +
            (output_tokens * base_output) +
            (cache_creation_tokens * cache_creation) +
            (cache_read_tokens * cache_read)
        )

        with self._lock:
            self.total_calls += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cache_creation_tokens += cache_creation_tokens
            self.total_cache_read_tokens += cache_read_tokens
            self.total_cost += cost
            return cost

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_calls": self.total_calls,
                "total_input_tokens": self.total_input_tokens,
                "total_output_tokens": self.total_output_tokens,
                "total_cache_creation_tokens": self.total_cache_creation_tokens,
                "total_cache_read_tokens": self.total_cache_read_tokens,
                "total_cost_usd": round(self.total_cost, 6),
            }

usage_tracker = UsageTracker()

class AnthropicClientManager:
    """Gerencia instâncias únicas (singleton) dos clientes síncrono e assíncrono do Anthropic."""
    _sync_client = None
    _async_client = None
    _lock = threading.Lock()

    @classmethod
    def get_sync_client(cls) -> Anthropic:
        if cls._sync_client is None:
            with cls._lock:
                if cls._sync_client is None:
                    api_key = settings.anthropic_api_key
                    if not api_key:
                        raise ValueError("Chave de API do Anthropic não configurada.")
                    cls._sync_client = Anthropic(
                        api_key=api_key,
                        timeout=float(settings.llm_request_timeout_seconds),
                        max_retries=3,
                        default_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
                    )
        return cls._sync_client

    @classmethod
    def get_async_client(cls) -> AsyncAnthropic:
        if cls._async_client is None:
            with cls._lock:
                if cls._async_client is None:
                    api_key = settings.anthropic_api_key
                    if not api_key:
                        raise ValueError("Chave de API do Anthropic não configurada.")
                    cls._async_client = AsyncAnthropic(
                        api_key=api_key,
                        timeout=float(settings.llm_request_timeout_seconds),
                        max_retries=3,
                        default_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
                    )
        return cls._async_client

def format_messages_for_anthropic(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converte mensagens do formato Bedrock Converse para o formato simples da Anthropic."""
    formatted = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and "text" in part:
                    parts.append(part["text"])
                elif isinstance(part, dict) and "type" in part and part["type"] == "text":
                    parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    parts.append(part)
            content = "\n".join(parts)
        formatted.append({"role": role, "content": content})
    return formatted

def invoke_llm(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    use_cache: bool = True
) -> str:
    """
    Chamada síncrona para a API da Anthropic.
    Compatível com a assinatura e funcionamento do Bedrock.
    """
    client = AnthropicClientManager.get_sync_client()
    target_model = map_model_name(model)
    formatted_messages = format_messages_for_anthropic(messages)
    
    # Prepara o system prompt com cache se solicitado
    system_param = None
    if system:
        if use_cache:
            system_param = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        else:
            system_param = system

    start_time = time.time()
    logger.info("Enviando chamada síncrona para Anthropic. Modelo original: %s -> Mapeado: %s", model or "default", target_model)
    
    response = client.messages.create(
        model=target_model,
        messages=formatted_messages,
        system=system_param,
        max_tokens=max_tokens or settings.llm_max_tokens_default,
        temperature=temperature or settings.llm_temperature_default
    )
    
    latency = time.time() - start_time
    text_response = "".join([block.text for block in response.content if hasattr(block, "text")])
    
    # Extrai tokens para o tracker
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    
    cost = usage_tracker.add_usage(
        model=target_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read
    )
    stats = usage_tracker.get_stats()
    
    logger.info(
        "Sucesso Anthropic: %s | Tokens: In=%d Out=%d (Cache: Cr=%d Rd=%d) | Latência: %.2fs | Custo chamada: $%.6f | Custo total sessão: $%.6f",
        target_model, input_tokens, output_tokens, cache_creation, cache_read, latency, cost, stats["total_cost_usd"]
    )
    
    return text_response

async def ainvoke_llm(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    use_cache: bool = True
) -> str:
    """
    Chamada assíncrona nativa para a API da Anthropic.
    """
    client = AnthropicClientManager.get_async_client()
    target_model = map_model_name(model)
    formatted_messages = format_messages_for_anthropic(messages)
    
    system_param = None
    if system:
        if use_cache:
            system_param = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        else:
            system_param = system

    start_time = time.time()
    logger.info("Enviando chamada assíncrona para Anthropic. Modelo original: %s -> Mapeado: %s", model or "default", target_model)
    
    response = await client.messages.create(
        model=target_model,
        messages=formatted_messages,
        system=system_param,
        max_tokens=max_tokens or settings.llm_max_tokens_default,
        temperature=temperature or settings.llm_temperature_default
    )
    
    latency = time.time() - start_time
    text_response = "".join([block.text for block in response.content if hasattr(block, "text")])
    
    usage = response.usage
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    
    cost = usage_tracker.add_usage(
        model=target_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_tokens=cache_creation,
        cache_read_tokens=cache_read
    )
    stats = usage_tracker.get_stats()
    
    logger.info(
        "Sucesso Anthropic Assíncrono: %s | Tokens: In=%d Out=%d (Cache: Cr=%d Rd=%d) | Latência: %.2fs | Custo chamada: $%.6f | Custo total sessão: $%.6f",
        target_model, input_tokens, output_tokens, cache_creation, cache_read, latency, cost, stats["total_cost_usd"]
    )
    
    return text_response

async def astream_llm(
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    use_cache: bool = True
) -> AsyncIterator[str]:
    """
    Gera uma resposta por streaming (assíncrono nativo) via API da Anthropic.
    """
    client = AnthropicClientManager.get_async_client()
    target_model = map_model_name(model)
    formatted_messages = format_messages_for_anthropic(messages)
    
    system_param = None
    if system:
        if use_cache:
            system_param = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        else:
            system_param = system

    start_time = time.time()
    logger.info("Iniciando streaming assíncrono Anthropic. Modelo original: %s -> Mapeado: %s", model or "default", target_model)
    
    async with client.messages.stream(
        model=target_model,
        messages=formatted_messages,
        system=system_param,
        max_tokens=max_tokens or settings.llm_max_tokens_default,
        temperature=temperature or settings.llm_temperature_default
    ) as stream:
        async for text in stream.text_stream:
            yield text
            
        final_message = await stream.get_final_message()
        usage = final_message.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        
        latency = time.time() - start_time
        cost = usage_tracker.add_usage(
            model=target_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read
        )
        stats = usage_tracker.get_stats()
        
        logger.info(
            "Streaming Anthropic Finalizado: %s | Tokens: In=%d Out=%d (Cache: Cr=%d Rd=%d) | Latência: %.2fs | Custo chamada: $%.6f | Custo total sessão: $%.6f",
            target_model, input_tokens, output_tokens, cache_creation, cache_read, latency, cost, stats["total_cost_usd"]
        )
