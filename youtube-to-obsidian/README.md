# 📥 YouTube to Obsidian

Importa transcrições de vídeos do YouTube como notas markdown estruturadas para o seu vault do Obsidian, com **metadados ricos em frontmatter YAML** prontos para RAG, busca e filtros avançados.

> **Visão de futuro:** Este é o primeiro módulo de um sistema de _segundo cérebro_ alimentado por IA. O vault do Obsidian servirá como base de conhecimento para um agente de IA com RAG, que poderá responder perguntas, gerar resumos e conectar ideias entre vídeos, artigos e outras fontes.

---

## ✨ Funcionalidades (V1)

- 🎬 Importação de vídeos via URL (formatos: `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`)
- 📜 Extração automática de transcrição com fallback de idioma
- 📝 Markdown rico com frontmatter YAML completo
- ⏱ Transcrição agrupada em blocos de ~30s com deep-links para o YouTube
- 🔍 Idempotência: não duplica vídeos já importados
- 📚 Listagem de todos os vídeos importados
- 🌙 Interface web dark mode premium

## 📋 Pré-requisitos

- **Python 3.11+**
- **Vault do Obsidian** existente no filesystem
- Conexão com a internet (para acessar o YouTube)

## 🚀 Instalação

```bash
# 1. Clone o repositório
git clone <seu-repo-url>
cd youtube-to-obsidian

# 2. Crie e ative o ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

## ⚙️ Configuração

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com seu editor preferido
# Ajuste OBSIDIAN_VAULT_PATH para o caminho do seu vault
```

**Variáveis importantes:**

| Variável | Descrição | Padrão |
|---|---|---|
| `OBSIDIAN_VAULT_PATH` | Caminho absoluto para a raiz do vault | `C:/Documentos/Obsidian Vault` |
| `OBSIDIAN_YOUTUBE_FOLDER` | Subpasta dentro do vault para os vídeos | `YouTube` |
| `DEFAULT_TRANSCRIPT_LANGUAGE` | Idioma preferido da transcrição | `pt` |
| `PORT` | Porta do servidor web | `8000` |

## ▶️ Execução

```bash
# Opção 1: script
./run.sh

# Opção 2: diretamente
uvicorn app.main:app --reload --port 8000

# Opção 3: Windows
python -m uvicorn app.main:app --reload --port 8000
```

Abra **http://localhost:8000** no navegador.

## 🧪 Testes

```bash
pytest
```

Os testes usam mocks para as APIs externas — não fazem requisições reais ao YouTube.

## 📁 Estrutura do Projeto

```
youtube-to-obsidian/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings via .env
│   ├── routes/videos.py     # POST/GET /api/videos
│   ├── services/
│   │   ├── youtube.py       # Validação de URL + metadados (yt-dlp)
│   │   ├── transcript.py    # Transcrição (youtube-transcript-api)
│   │   └── obsidian.py      # Geração de markdown + vault
│   ├── models/video.py      # Modelos Pydantic v2
│   └── utils/               # Helpers: slugify, timestamp
├── static/                  # Frontend (HTML/CSS/JS vanilla)
├── tests/                   # Testes unitários
├── .env.example
├── requirements.txt
└── run.sh
```

## 🗺️ Roadmap

Funcionalidades planejadas para versões futuras:

- [ ] 🤖 **Agente de IA com RAG** — perguntas e respostas sobre o conteúdo do vault
- [ ] 📄 **Suporte a PDFs e artigos web** — expandir fontes além do YouTube
- [ ] ✍️ **Resumo automático via LLM** — preencher seções de resumo e pontos-chave
- [ ] 🏷️ **Tags automáticas via IA** — categorização inteligente do conteúdo
- [ ] 📊 **Dashboard de analytics** — estatísticas sobre o vault
- [ ] 🔄 **Fila de processamento** — importação em batch com Celery/RQ
- [ ] 🗂️ **Múltiplos vaults** — suporte a mais de um vault do Obsidian
- [ ] 🎙️ **Podcasts** — importar transcrições de podcasts

## 📄 Licença

MIT
