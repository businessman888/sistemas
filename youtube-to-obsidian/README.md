# 🧠 Oyto OS

Oyto OS é um "sistema operacional" pessoal projetado para hospedar módulos de extração de conhecimento e interligar ideias de forma autônoma. 

A arquitetura do projeto é modular, facilitando a adição de novas fontes e integrações no futuro. Atualmente, o módulo central extrai transcrições de vídeos do YouTube e os salva como notas markdown no seu vault do Obsidian, formando uma base de conhecimento estruturada e conectada.

---

## ✨ Funcionalidades (V1)

### Módulo: YouTube → Obsidian
- 🎬 **Importação de vídeos** via URL (suporte a shorts, URLs reduzidas, etc.)
- 📜 **Extração de transcrição** com suporte a múltiplos idiomas
- ⏱ **Marcação de tempo agrupada** (blocos de ~30s com links para o player do YouTube)
- 📝 **Markdown rico** com metadados em frontmatter YAML
- 🕸️ **Conexão de Grafo (Determinística)**: gera seção "Relacionados" linkando notas de conteúdo similar (TF-IDF + similaridade de cosseno), fortalecendo o grafo do Obsidian.
- 🏷️ **Tags de Tópicos Automáticas**: extrai as principais palavras-chave da transcrição e adiciona como `topic/...`.
- 🔍 **Idempotência**: protege contra duplicação de vídeos.

## 📋 Pré-requisitos

- **Python 3.11+**
- **Vault do Obsidian** existente no filesystem local
- Conexão com a internet

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

Copie `.env.example` para `.env` e ajuste:

| Variável | Padrão | Descrição |
|---|---|---|
| `OBSIDIAN_VAULT_PATH` | `C:/Documentos/Obsidian Vault` | Caminho do vault |
| `OBSIDIAN_YOUTUBE_FOLDER` | `YouTube` | Pasta raiz de importação |
| `RELATED_VIDEOS_COUNT` | `5` | Máximo de conexões no grafo por nota |
| `RELATED_MIN_SIMILARITY`| `0.10` | Similaridade mínima (0-1) |
| `TOPIC_TAGS_COUNT` | `5` | Quantidade de tags extraídas |
| `PORT` | `8000` | Porta do app |

## ▶️ Execução

Para iniciar o shell da aplicação:
```bash
uvicorn app.main:app --reload --port 8000
```
Acesse **http://localhost:8000** no navegador.

## 🔄 Script de Migração

Para reprocessar todos os vídeos já importados, calcular a similaridade entre eles e criar as conexões no grafo (Ajuste 2 e 3):

```bash
python scripts/migrate.py
```
> O script é idempotente e ignorará anotações feitas manualmente, atualizando apenas o frontmatter e a seção "Relacionados".

## 📁 Estrutura de Módulos

A estrutura atual é construída para a inclusão de novos módulos facilmente:

```
oyto-os/
├── app/
│   ├── main.py              # FastAPI app setup
│   ├── core/                # Funcionalidades e utils compartilhados
│   │   ├── config.py
│   │   ├── graph.py         # Conexão no Obsidian (TF-IDF)
│   │   └── similarity.py    # Cálculos matemáticos de NLP (scikit-learn)
│   └── modules/             # Módulos independentes do Oyto OS
│       └── youtube/         # Módulo 1: YouTube → Obsidian
│           ├── routes.py
│           ├── obsidian.py
│           ├── transcript.py
│           └── youtube.py
├── scripts/
│   └── migrate.py           # Script para conectar o grafo existente
├── static/                  # Shell Frontend (HTML/CSS/JS)
└── tests/
```

### Como Adicionar Novos Módulos
1. Crie uma pasta em `app/modules/seu-modulo/`.
2. Adicione as rotas e regras de negócio relativas a ele.
3. Importe o roteador em `app/main.py`.
4. Adicione um novo botão na barra lateral (`static/index.html`) e um componente de visualização.

## 🗺️ Roadmap

O Oyto OS se tornará o centro nervoso de conhecimento pessoal:

- [ ] 🤖 **Agente RAG Nativo** — Q&A em todo o vault
- [ ] 📄 **Módulo: Extrator de Web & PDF**
- [ ] ✍️ **Resumos com LLM Local** (LLaMA via Ollama)
- [ ] 📊 **Dashboard de Analytics do Conhecimento**
