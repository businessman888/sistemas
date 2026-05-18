# Prompt: Ajustes no projeto — Rebranding "Oyto OS" + Conexão de Grafo

> Cole este prompt inteiro no agente de código da IDE. **O projeto já existe e funciona** — isto são ajustes, não uma reescrita. Preserve tudo que já funciona (pipeline de transcrição, escrita no vault, frontmatter atual).

---

## 🎯 Contexto

O projeto atual importa vídeos do YouTube, transcreve via `youtube-transcript-api` e salva como markdown no vault do Obsidian (pasta `YouTube/`). Está funcionando. Agora preciso de **quatro ajustes**:

1. **Rebranding** — o app não se chama "YouTube to Obsidian". Ele é o **Oyto OS**, e a importação de vídeos é apenas **um módulo** de um sistema que vai ganhar mais módulos com o tempo.
2. **Conexão automática no grafo do Obsidian** — hoje as notas ficam isoladas no grafo. Vídeos com conteúdo parecido precisam ficar interligados.
3. **Tags de tópico automáticas** — extraídas do conteúdo, para organização e filtro.
4. **Script de migração** — para reprocessar os ~10 vídeos já importados e aplicar os itens 2 e 3 neles.

**Importante:** nada de IA generativa / LLM / APIs externas neste ajuste. Tudo deve ser **determinístico, local e sem custo**. Os títulos das notas devem **permanecer como estão** (título original do YouTube) — não alterar.

---

## 🧩 Ajuste 1 — Rebranding para "Oyto OS"

O app passa a ser o **Oyto OS** — pense nele como um "sistema operacional" pessoal que hospeda vários módulos. A importação de vídeos do YouTube vira o **primeiro módulo**, não o app inteiro.

**Mudanças na interface (frontend):**
- Renomear de "YouTube to Obsidian" para **Oyto OS** em todos os lugares: título da página, cabeçalho, textos.
- Transformar a interface em um **shell com sidebar**:
  - **Sidebar à esquerda:** logo "Oyto OS" no topo + lista de módulos navegáveis. Por enquanto há um módulo: **"YouTube → Obsidian"** (a tela de importação atual). Pode incluir um item "Configurações" se fizer sentido. Não invente outros módulos.
  - **Área de conteúdo principal:** renderiza o módulo ativo. A tela de importação atual (campo de URL, idioma, botão, lista de importados) passa a ser o conteúdo do módulo "YouTube → Obsidian".
- **Manter a identidade visual atual** — o dark mode roxo/elegante está bom. Só reorganizar o layout em shell + sidebar.
- O frontend deve ser estruturado de forma **modular**: adicionar um novo módulo no futuro deve ser simples (registrar uma entrada na sidebar + um componente/tela de conteúdo). Documente brevemente como adicionar um módulo.

**Mudanças no backend / projeto:**
- Reorganizar o código numa estrutura de módulos, por exemplo:
  ```
  app/
    modules/
      youtube/
        routes.py        # rotas do módulo (antigo routes/videos.py)
        ... (services de youtube, transcript, obsidian podem migrar para cá)
    core/                # config, utils compartilhados, app factory
  ```
  Mantenha simples — o objetivo é só deixar claro que cada módulo é autocontido. Não sobre-engenheire.
- Atualizar `README.md`: novo nome (Oyto OS), explicação de que é um sistema modular, e a seção de roadmap refletindo isso.
- Atualizar quaisquer nomes internos óbvios (título no `<title>`, nome no `package`/metadata, etc.).

> Observação: assumi a grafia **"Oyto OS"**. Se estiver diferente, é só ajustar o texto.

---

## 🕸️ Ajuste 2 — Conexão automática no grafo do Obsidian

**Problema:** no grafo do Obsidian, as notas de vídeo aparecem desconectadas. O grafo só conecta notas via `[[links internos]]`, e hoje nenhuma nota linka outra.

**Solução (100% determinística, sem LLM):** cada nota de vídeo ganha uma seção **"Relacionados"** com links diretos para os vídeos mais semelhantes, calculados por similaridade de texto.

**Como calcular a similaridade:**
- Usar **TF-IDF + similaridade de cosseno** via `scikit-learn` (`TfidfVectorizer` + `cosine_similarity`).
- Entrada: o texto da transcrição de cada vídeo (pode incluir o título e a descrição no texto vetorizado para reforçar o sinal).
- Pré-processamento: lowercase; remover stopwords de **inglês** (built-in do sklearn) **e português** (forneça uma lista de stopwords PT, já que o vault pode misturar idiomas); usar unigrams + bigrams (`ngram_range=(1,2)`).
- Para cada vídeo, selecionar os **top-K vizinhos mais similares** acima de um **limiar mínimo de similaridade** (para não forçar conexões fracas). Ambos configuráveis no `.env`.

**Como aplicar no markdown:**
- Cada nota ganha uma seção, por exemplo:
  ```markdown
  ## 🔗 Relacionados
  - [[2025-10-26 - He made $2.2M from building simple apps]]
  - [[2026-03-09 - I speedran an ai app from 0 to $100k exit in 26 days]]
  ```
  Os `[[wikilinks]]` usam o **nome do arquivo sem `.md`**.
- **Links bidirecionais (crítico):** ao importar um vídeo novo, além de escrever a seção "Relacionados" dele, é preciso **atualizar a seção "Relacionados" dos vídeos que passaram a ser similares a ele**, adicionando o vídeo novo lá. Sem isso o grafo fica com conexões só de um lado.
- A seção "Relacionados" é **totalmente regenerável**: ao atualizar, reescrever apenas o bloco entre o heading `## 🔗 Relacionados` e o próximo heading. **Não tocar** em nenhuma outra parte da nota — especialmente "Notas Pessoais", "Resumo" e a transcrição, que o usuário pode ter editado à mão.
- Onde a seção "Relacionados" se encaixa no template: posicione-a de forma consistente (sugestão: logo após os "Pontos-Chave" / antes da transcrição, ou no fim antes das "Notas Pessoais" — escolha um lugar fixo e documente).

**Isolamento por domínio (importante para o futuro):**
- O cálculo de similaridade deve agrupar e conectar **apenas notas do mesmo `source`**, lido do frontmatter. Nesta versão isso significa conectar `source: youtube` somente com `source: youtube` — **nunca** com notas pessoais ou qualquer outro conteúdo do vault.
- A lógica de seleção/isolamento deve se basear no campo **`source` do frontmatter**, não no nome da pasta. Isso garante que módulos futuros (livros, artigos, contexto da empresa) funcionem sem reescrita: cada tipo de conteúdo terá seu próprio `source` (ex: `book`, `article`, `company`) e conectará dentro do seu próprio domínio automaticamente.
- Deixe **claro e isolado no código** o ponto onde essa regra de domínio é aplicada (ex: um único filtro/parâmetro `source`), para que no futuro seja simples permitir conexões cruzadas entre domínios de propósito (ex: ligar um vídeo a livros relacionados) apenas relaxando esse filtro — sem reescrever a lógica de similaridade.

**Performance / persistência:**
- Com dezenas ou poucas centenas de vídeos, recalcular a matriz de similaridade lendo as transcrições do vault a cada importação é instantâneo — **não precisa persistir índice vetorial**. Mantenha simples: o vault é a fonte da verdade.

---

## 🏷️ Ajuste 3 — Tags de tópico automáticas

Extrair, de forma determinística, as palavras-chave mais relevantes de cada transcrição e adicioná-las ao frontmatter como tags.

- Usar os **termos de maior peso TF-IDF** de cada vídeo (reaproveite o vetorizador do Ajuste 2) — extrair as ~5 keywords mais distintivas.
- Normalizar cada keyword (lowercase, sem acentos, espaços viram hífen) e adicioná-las ao campo `tags` do frontmatter com o prefixo `topic/`, por exemplo:
  ```yaml
  tags:
    - youtube
    - canal/superwall
    - source/transcript
    - topic/no-code
    - topic/app-revenue
  ```
- Isso melhora a organização e permite filtrar por tema no Obsidian. (`yake` é uma alternativa opcional de melhor qualidade para extração de keywords, mas TF-IDF já resolve — fica a seu critério, priorize manter as dependências enxutas.)

---

## 🔄 Ajuste 4 — Script de migração dos vídeos existentes

Criar um script executável (ex: `python -m app.scripts.migrate` ou `scripts/migrate.py`) que reprocessa **todos os vídeos já importados** e aplica os Ajustes 2 e 3 a eles.

O script deve:
1. Varrer o vault e selecionar **apenas notas com `source: youtube` no frontmatter**. Notas pessoais e qualquer outro conteúdo do vault são **ignorados completamente** — não são lidos nem alterados. (Não dependa do nome da pasta para isso: use o campo `source`.)
2. Ler o frontmatter e a transcrição de cada nota selecionada.
3. Calcular a matriz de similaridade TF-IDF entre todos.
4. Em cada nota: adicionar/atualizar a seção **"Relacionados"** e adicionar as **tags de tópico** no frontmatter.
5. Ser **idempotente** — rodar de novo não duplica seções nem tags, apenas atualiza.
6. **Não destruir conteúdo editado pelo usuário** — só mexe no frontmatter (adicionando campos/tags) e na seção "Relacionados". Resumo, Pontos-Chave, Notas Pessoais e transcrição ficam intactos.
7. Imprimir um resumo no final: quantas notas processadas, quantas conexões criadas.

---

## 🔧 Configuração (`.env`)

Adicionar ao `.env.example` (mantendo o que já existe):

```dotenv
# Conexão de grafo — vídeos relacionados
RELATED_VIDEOS_COUNT=5          # quantos vídeos relacionados linkar por nota
RELATED_MIN_SIMILARITY=0.10     # similaridade mínima para criar uma conexão (0.0–1.0)

# Tags de tópico
TOPIC_TAGS_COUNT=5              # quantas keywords extrair por vídeo
```

---

## 📦 Dependências novas

- `scikit-learn` — TF-IDF e similaridade de cosseno.
- `python-frontmatter` — se o projeto ainda não usa, adotar para ler/escrever o frontmatter YAML com segurança (em vez de regex frágil).
- Atualizar `requirements.txt`.

---

## ✅ Qualidade e entrega

- Manter o estilo de código atual (type hints, logging, pydantic, sem `print`).
- A nova lógica de similaridade deve ficar em seu próprio serviço/módulo (ex: `app/modules/youtube/related.py` ou `app/core/similarity.py`), isolada e testável.
- Adicionar testes para o cálculo de similaridade e para a extração de keywords (com transcrições de exemplo mockadas).
- Garantir que o pipeline de **importação de um vídeo novo** já dispare automaticamente a atualização das conexões (Ajustes 2 e 3) — não só o script de migração.
- Fazer um commit limpo ao final.

Ao terminar, me responda no chat com:
1. Como rodar o script de migração.
2. Como ficou a estrutura de módulos (para eu entender como adicionar módulos no futuro).
3. Qualquer decisão própria que valha eu revisar, e limitações conhecidas (ex: comportamento quando há poucos vídeos no vault).

Pode começar.
