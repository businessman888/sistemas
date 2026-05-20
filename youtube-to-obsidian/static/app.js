/**
 * YouTube to Obsidian — Frontend Logic
 * Gerencia importação de vídeos e listagem via API.
 */

(function () {
    'use strict';

    // --- DOM Elements ---
    const form = document.getElementById('import-form');
    const urlInput = document.getElementById('video-url');
    const languageSelect = document.getElementById('language-select');
    const btnImport = document.getElementById('btn-import');
    const btnText = document.getElementById('btn-text');
    const statusArea = document.getElementById('status-area');
    const videosList = document.getElementById('videos-list');
    const videosCount = document.getElementById('videos-count');
    const emptyState = document.getElementById('empty-state');

    // --- State ---
    let isLoading = false;

    // --- API ---
    const API_BASE = '/api/videos';

    async function importVideo(url, language) {
        const response = await fetch(API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, language }),
        });

        const data = await response.json();

        if (!response.ok) {
            const error = new Error(data.detail || 'Erro desconhecido');
            error.status = response.status;
            error.data = data;
            throw error;
        }

        return data;
    }

    async function fetchVideos() {
        const response = await fetch(API_BASE);
        if (!response.ok) {
            throw new Error('Falha ao carregar vídeos');
        }
        return response.json();
    }

    // --- UI Updates ---
    function setLoading(loading) {
        isLoading = loading;
        btnImport.disabled = loading;
        urlInput.disabled = loading;
        languageSelect.disabled = loading;

        if (loading) {
            btnText.innerHTML = '<span class="spinner"></span> Importando...';
        } else {
            btnText.textContent = 'Importar Transcrição';
        }
    }

    function showStatus(type, message) {
        const classMap = {
            success: 'status-success',
            error: 'status-error',
            conflict: 'status-conflict',
        };

        statusArea.innerHTML = `
            <div class="status-message ${classMap[type] || ''}">
                ${message}
            </div>
        `;

        // Auto-clear success after 10s
        if (type === 'success') {
            setTimeout(() => {
                if (statusArea.querySelector('.status-success')) {
                    statusArea.innerHTML = '';
                }
            }, 10000);
        }
    }

    function clearStatus() {
        statusArea.innerHTML = '';
    }

    function renderVideos(videos) {
        videosCount.textContent = videos.length;

        if (videos.length === 0) {
            emptyState.style.display = '';
            return;
        }

        emptyState.style.display = 'none';

        // Keep empty state hidden, build video items
        const html = videos.map(video => {
            const publishedDate = video.published_at
                ? formatDate(video.published_at)
                : '—';
            const importedDate = video.imported_at
                ? formatDateTime(video.imported_at)
                : '—';

            return `
                <div class="video-item">
                    <div class="video-item-title">${escapeHtml(video.title)}</div>
                    <div class="video-item-meta">
                        <span>📺 ${escapeHtml(video.channel)}</span>
                        <span>📅 ${publishedDate}</span>
                        ${video.duration ? `<span>⏱ ${video.duration}</span>` : ''}
                        ${video.language ? `<span>🌐 ${video.language}</span>` : ''}
                    </div>
                    <div class="video-item-meta" style="margin-top: 6px;">
                        <a href="${escapeHtml(video.url)}" target="_blank" rel="noopener" class="video-item-link">
                            Abrir no YouTube ↗
                        </a>
                        <span style="color: var(--text-muted);">Importado: ${importedDate}</span>
                    </div>
                </div>
            `;
        }).join('');

        videosList.innerHTML = html;
    }

    // --- Event Handlers ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (isLoading) return;

        const url = urlInput.value.trim();
        if (!url) return;

        const language = languageSelect.value;

        clearStatus();
        setLoading(true);

        try {
            const result = await importVideo(url, language);

            showStatus('success', `
                ✅ <strong>${escapeHtml(result.title)}</strong> importado com sucesso!<br>
                <small>Idioma: ${result.language_used} · Duração: ${result.duration}</small><br>
                <small>Arquivo: ${escapeHtml(result.file_path)}</small>
            `);

            urlInput.value = '';
            await loadVideos(); // Refresh list
        } catch (err) {
            if (err.status === 409) {
                // Conflict — already imported
                const detail = typeof err.data?.detail === 'object' ? err.data.detail : {};
                showStatus('conflict', `
                    ⚠️ Este vídeo já foi importado anteriormente.<br>
                    <small>Arquivo: ${escapeHtml(detail.file_path || '')}</small>
                `);
            } else {
                const message = typeof err.data?.detail === 'string'
                    ? err.data.detail
                    : err.message || 'Erro desconhecido';
                showStatus('error', `❌ ${escapeHtml(message)}`);
            }
        } finally {
            setLoading(false);
        }
    });

    // --- Helpers ---
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        try {
            const d = new Date(dateStr + 'T00:00:00');
            return d.toLocaleDateString('pt-BR');
        } catch {
            return dateStr;
        }
    }

    function formatDateTime(dtStr) {
        try {
            const d = new Date(dtStr);
            return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return dtStr;
        }
    }

    // --- Init ---
    async function loadVideos() {
        try {
            const videos = await fetchVideos();
            renderVideos(videos);
        } catch (err) {
            console.error('Erro ao carregar vídeos:', err);
        }
    }

    // Load video list on page load
    loadVideos();

    // ============================================================
    // Lógica do Módulo Social Media AI
    // ============================================================

    const navYoutube = document.getElementById('nav-youtube');
    const navSocialMedia = document.getElementById('nav-social-media');
    const navClone = document.getElementById('nav-clone');
    const moduleYoutube = document.getElementById('module-youtube');
    const moduleSocialMedia = document.getElementById('module-social-media');
    const moduleClone = document.getElementById('module-clone');

    // Troca de módulo na Sidebar
    function switchModule(activeNav, activeModule) {
        [navYoutube, navSocialMedia, navClone].forEach(nav => {
            if (nav) nav.classList.remove('active');
        });
        [moduleYoutube, moduleSocialMedia, moduleClone].forEach(mod => {
            if (mod) mod.style.display = 'none';
        });
        activeNav.classList.add('active');
        activeModule.style.display = 'block';
    }

    navYoutube.addEventListener('click', () => {
        switchModule(navYoutube, moduleYoutube);
    });

    navSocialMedia.addEventListener('click', () => {
        switchModule(navSocialMedia, moduleSocialMedia);
        loadCreators();
        loadConfigs();
        loadPipelines();
    });

    navClone.addEventListener('click', () => {
        switchModule(navClone, moduleClone);
        loadClones();
    });


    // Troca de abas secundárias (sub-tabs)
    const subtabs = ['creators', 'configs', 'run', 'history'];
    subtabs.forEach(tab => {
        const btn = document.getElementById(`subtab-${tab}`);
        btn.addEventListener('click', () => {
            subtabs.forEach(t => {
                document.getElementById(`subtab-${t}`).classList.remove('active');
                document.getElementById(`subcontent-${t}`).style.display = 'none';
            });
            btn.classList.add('active');
            document.getElementById(`subcontent-${tab}`).style.display = 'block';

            if (tab === 'creators') loadCreators();
            if (tab === 'configs') loadConfigs();
            if (tab === 'run') loadRunTabConfigs();
            if (tab === 'history') loadPipelines();
        });
    });

    // --- Helpers de Requisição ---
    async function apiFetch(url, options = {}) {
        const response = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Erro na requisição');
        }
        return data;
    }

    // --- GERENCIAMENTO DE CRIADORES ---
    const creatorForm = document.getElementById('creator-form');
    const btnAddCreator = document.getElementById('btn-add-creator');
    const creatorStatus = document.getElementById('creator-status');
    const creatorsTableBody = document.getElementById('creators-table-body');

    async function loadCreators() {
        try {
            const creators = await apiFetch('/api/social-media/creators');
            if (creators.length === 0) {
                creatorsTableBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">Nenhum criador cadastrado ainda.</td></tr>`;
                return;
            }
            creatorsTableBody.innerHTML = creators.map(c => {
                const dateStr = c.last_scraped ? formatDateTime(c.last_scraped) : '—';
                const windowMap = {
                    'recent': 'Mais Recentes',
                    '1_week': 'Última semana',
                    '1_month': 'Último mês',
                    '3_months': 'Últimos 3 meses'
                };
                return `
                    <tr>
                        <td><strong>@${escapeHtml(c.username)}</strong></td>
                        <td><span class="platform-badge platform-${c.platform}">${escapeHtml(c.platform.toUpperCase())}</span></td>
                        <td>${escapeHtml(c.category)}</td>
                        <td>${c.followers_count.toLocaleString()}</td>
                        <td>${c.average_views.toLocaleString()}</td>
                        <td>${c.posts_per_month}</td>
                        <td>${windowMap[c.time_window] || c.time_window}</td>
                        <td><small>${dateStr}</small></td>
                        <td>
                            <button class="btn-danger btn-delete-creator" data-id="${c.id}">Remover</button>
                        </td>
                    </tr>
                `;
            }).join('');

            // Adiciona handlers de delete
            document.querySelectorAll('.btn-delete-creator').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const id = e.target.getAttribute('data-id');
                    if (confirm('Deseja realmente parar de rastrear este criador?')) {
                        try {
                            await apiFetch(`/api/social-media/creators/${id}`, { method: 'DELETE' });
                            loadCreators();
                        } catch (err) {
                            alert('Erro ao remover criador: ' + err.message);
                        }
                    }
                });
            });
        } catch (err) {
            console.error(err);
        }
    }

    creatorForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('creator-username').value.trim();
        const platform = document.getElementById('creator-platform').value;
        const category = document.getElementById('creator-category').value.trim();
        const time_window = document.getElementById('creator-window').value;

        if (!username || !category) return;

        creatorStatus.innerHTML = '<div class="status-message status-success">⏳ Buscando dados do criador via Apify (isso pode levar de 30s a 2min)...</div>';
        btnAddCreator.disabled = true;

        try {
            await apiFetch('/api/social-media/creators', {
                method: 'POST',
                body: JSON.stringify({ username, platform, category, time_window })
            });
            creatorStatus.innerHTML = '<div class="status-message status-success">✅ Criador cadastrado e métricas analisadas com sucesso!</div>';
            creatorForm.reset();
            loadCreators();
            setTimeout(() => { creatorStatus.innerHTML = ''; }, 6000);
        } catch (err) {
            creatorStatus.innerHTML = `<div class="status-message status-error">❌ ${escapeHtml(err.message)}</div>`;
        } finally {
            btnAddCreator.disabled = false;
        }
    });

    // --- GERENCIAMENTO DE CONFIGURAÇÕES ---
    const configForm = document.getElementById('config-form');
    const btnSaveConfig = document.getElementById('btn-save-config');
    const configStatus = document.getElementById('config-status');
    const configsTableBody = document.getElementById('configs-table-body');

    async function loadConfigs() {
        try {
            const configs = await apiFetch('/api/social-media/configs');
            if (configs.length === 0) {
                configsTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Nenhuma configuração salva ainda.</td></tr>`;
                return;
            }
            configsTableBody.innerHTML = configs.map(c => `
                <tr>
                    <td><strong>${escapeHtml(c.name)}</strong></td>
                    <td>${escapeHtml(c.category)}</td>
                    <td>Top ${c.limit_top_k}</td>
                    <td><small>${formatDateTime(c.created_at)}</small></td>
                </tr>
            `).join('');
        } catch (err) {
            console.error(err);
        }
    }

    configForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('config-name').value.trim();
        const category = document.getElementById('config-category').value.trim();
        const limit_top_k = parseInt(document.getElementById('config-limit').value);
        const analysis_instructions = document.getElementById('config-analysis').value.trim();
        const concepts_instructions = document.getElementById('config-concepts').value.trim();

        btnSaveConfig.disabled = true;
        configStatus.innerHTML = '';

        try {
            await apiFetch('/api/social-media/configs', {
                method: 'POST',
                body: JSON.stringify({ name, category, analysis_instructions, concepts_instructions, limit_top_k })
            });
            configStatus.innerHTML = '<div class="status-message status-success">✅ Configuração salva com sucesso!</div>';
            configForm.reset();
            loadConfigs();
            setTimeout(() => { configStatus.innerHTML = ''; }, 6000);
        } catch (err) {
            configStatus.innerHTML = `<div class="status-message status-error">❌ ${escapeHtml(err.message)}</div>`;
        } finally {
            btnSaveConfig.disabled = false;
        }
    });

    // --- PIPELINE RUN ---
    const runConfigSelect = document.getElementById('run-config-select');
    const runPipelineForm = document.getElementById('run-pipeline-form');
    const btnRunPipeline = document.getElementById('btn-run-pipeline');
    const pipelineStatusCard = document.getElementById('pipeline-status-card');
    const pipelineProgressBar = document.getElementById('pipeline-progress-bar');
    const pipelineLog = document.getElementById('pipeline-log');
    
    let activePipelineId = null;
    let pollingInterval = null;

    async function loadRunTabConfigs() {
        try {
            const configs = await apiFetch('/api/social-media/configs');
            if (configs.length === 0) {
                runConfigSelect.innerHTML = `<option value="" disabled selected>Nenhuma config encontrada. Crie uma na aba ao lado.</option>`;
                return;
            }
            runConfigSelect.innerHTML = `<option value="" disabled selected>Escolha uma configuração...</option>` + 
                configs.map(c => `<option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.category)})</option>`).join('');
        } catch (err) {
            console.error(err);
        }
    }

    runPipelineForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const config_id = parseInt(runConfigSelect.value);
        if (!config_id) return;

        btnRunPipeline.disabled = true;
        pipelineStatusCard.style.display = 'block';
        pipelineProgressBar.style.width = '10%';
        pipelineLog.textContent = 'Solicitando início do pipeline...';

        try {
            const run = await apiFetch('/api/social-media/pipelines/run', {
                method: 'POST',
                body: JSON.stringify({ config_id })
            });

            activePipelineId = run.id;
            pipelineLog.textContent = 'Pipeline iniciado em background. Espionando criadores do nicho...';
            
            // Inicia o polling de status
            startPipelinePolling(run.id);
        } catch (err) {
            pipelineProgressBar.style.width = '100%';
            pipelineLog.innerHTML = `<span style="color: var(--error);">❌ ${escapeHtml(err.message)}</span>`;
            btnRunPipeline.disabled = false;
        }
    });

    function startPipelinePolling(id) {
        if (pollingInterval) clearInterval(pollingInterval);
        
        let elapsed = 0;
        pollingInterval = setInterval(async () => {
            elapsed += 3;
            try {
                const pipelines = await apiFetch('/api/social-media/pipelines');
                const current = pipelines.find(p => p.id === id);
                
                if (!current) return;
                
                document.getElementById('pipeline-time').textContent = `Iniciado há ${elapsed}s`;

                if (current.status === 'completed') {
                    clearInterval(pollingInterval);
                    pipelineProgressBar.style.width = '100%';
                    document.getElementById('pipeline-status-card').querySelector('.status-badge').className = 'status-badge completed';
                    document.getElementById('pipeline-status-card').querySelector('.status-badge').textContent = 'Concluído';
                    pipelineLog.innerHTML = `<span style="color: var(--success);">🎉 Pipeline concluído com sucesso! Vá para a aba "Histórico" para ver os roteiros criados!</span>`;
                    btnRunPipeline.disabled = false;
                    loadPipelines();
                } else if (current.status === 'failed') {
                    clearInterval(pollingInterval);
                    pipelineProgressBar.style.width = '100%';
                    document.getElementById('pipeline-status-card').querySelector('.status-badge').className = 'status-badge failed';
                    document.getElementById('pipeline-status-card').querySelector('.status-badge').textContent = 'Erro';
                    pipelineLog.innerHTML = `<span style="color: var(--error);">❌ Falha na execução do pipeline. Verifique as chaves de API e se os criadores cadastrados têm posts recentes.</span>`;
                    btnRunPipeline.disabled = false;
                } else {
                    // Simulação visual de progresso enquanto roda
                    const currentWidth = parseFloat(pipelineProgressBar.style.width);
                    if (currentWidth < 90) {
                        pipelineProgressBar.style.width = (currentWidth + 5) + '%';
                    }
                    pipelineLog.textContent = `Scraping & Processamento de IA em andamento... (${elapsed}s)`;
                }
            } catch (err) {
                console.error('Erro no polling do pipeline:', err);
            }
        }, 3000);
    }

    // --- HISTÓRICO E RESULTADOS ---
    const historyPipelineSelect = document.getElementById('history-pipeline-select');
    const resultsDisplaySection = document.getElementById('results-display-section');
    const resultsList = document.getElementById('results-list');

    async function loadPipelines() {
        try {
            const pipelines = await apiFetch('/api/social-media/pipelines');
            const configs = await apiFetch('/api/social-media/configs');
            
            const configMap = {};
            configs.forEach(c => { configMap[c.id] = c; });

            if (pipelines.length === 0) {
                historyPipelineSelect.innerHTML = `<option value="" disabled selected>Nenhuma execução encontrada no histórico.</option>`;
                return;
            }

            historyPipelineSelect.innerHTML = `<option value="" disabled selected>Escolha uma execução...</option>` +
                pipelines.map(p => {
                    const cfgName = configMap[p.config_id] ? configMap[p.config_id].name : `Config #${p.config_id}`;
                    const statusStr = p.status === 'completed' ? 'Sucesso' : p.status === 'failed' ? 'Falha' : 'Executando';
                    return `<option value="${p.id}">${formatDateTime(p.run_date)} — ${escapeHtml(cfgName)} [${statusStr}]</option>`;
                }).join('');
        } catch (err) {
            console.error(err);
        }
    }

    historyPipelineSelect.addEventListener('change', async (e) => {
        const pipelineId = parseInt(e.target.value);
        if (!pipelineId) return;

        resultsList.innerHTML = '<div style="text-align: center; padding: 20px;">Carregando resultados...</div>';
        resultsDisplaySection.style.display = 'block';

        try {
            const results = await apiFetch(`/api/social-media/pipelines/${pipelineId}/results`);
            if (results.length === 0) {
                resultsList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhum vídeo pôde ser analisado ou gravado nesta execução.</div>';
                return;
            }

            resultsList.innerHTML = results.map(r => `
                <div class="result-card">
                    <div class="result-card-header">
                        <div class="result-creator-info">
                            <span class="result-creator-username">@${escapeHtml(r.creator_username)}</span>
                            <span class="result-creator-meta">Plataforma: <span class="platform-badge platform-${r.platform}">${escapeHtml(r.platform.toUpperCase())}</span></span>
                        </div>
                        <div class="result-views-badge">
                            🔥 ${r.views.toLocaleString()} visualizações
                        </div>
                    </div>
                    <div class="result-card-body">
                        <div class="result-original-post">
                            ${r.thumbnail ? `<img src="${escapeHtml(r.thumbnail)}" class="result-thumbnail" alt="Thumbnail">` : ''}
                            <div class="result-post-desc">
                                <strong>Descrição do Post Concorrente:</strong><br>
                                <p style="margin-top: 6px;">${escapeHtml(r.caption)}</p>
                                <a href="${escapeHtml(r.video_url)}" target="_blank" rel="noopener" class="result-post-link">Post Concorrente Original ↗</a>
                            </div>
                        </div>
                        <div class="result-sections">
                            <div class="result-section">
                                <h4>🔍 Análise Estrutural do Concorrente</h4>
                                <div class="result-section-content">${escapeHtml(r.analysis)}</div>
                            </div>
                            <div class="result-section">
                                <h4>💡 Meu Novo Roteiro Customizado</h4>
                                <div class="result-section-content" style="color: var(--text-primary); font-weight: 500;">${escapeHtml(r.concepts)}</div>
                            </div>
                        </div>
                    </div>
                    <div class="result-card-footer">
                        <button class="btn-import btn-export-obsidian" data-id="${r.id}" style="width: auto; margin-top: 0; padding: 10px 20px;">
                            <span>Salvar no Obsidian Vault</span>
                        </button>
                    </div>
                </div>
            `).join('');

            // Adiciona handlers de exportação
            document.querySelectorAll('.btn-export-obsidian').forEach(btn => {
                btn.addEventListener('click', async (evt) => {
                    const target = evt.currentTarget;
                    const id = target.getAttribute('data-id');
                    
                    target.disabled = true;
                    target.querySelector('span').textContent = 'Exportando...';

                    try {
                        const exportRes = await apiFetch(`/api/social-media/results/${id}/export`, { method: 'POST' });
                        target.style.background = 'var(--success-soft)';
                        target.style.color = 'var(--success)';
                        target.style.border = '1px solid rgba(52, 211, 153, 0.3)';
                        target.querySelector('span').textContent = 'Exportado para o Vault! ✓';
                        
                        const notification = document.createElement('div');
                        notification.style.cssText = 'font-size: 0.75rem; color: var(--success); margin-top: 6px; text-align: right;';
                        notification.textContent = `Arquivo criado: ${exportRes.file_path}`;
                        target.parentNode.appendChild(notification);
                    } catch (err) {
                        target.disabled = false;
                        target.querySelector('span').textContent = 'Salvar no Obsidian Vault';
                        alert('Falha ao exportar conceito: ' + err.message);
                    }
                });
            });

        } catch (err) {
            resultsList.innerHTML = `<div style="text-align: center; color: var(--error); padding: 20px;">❌ Erro ao carregar resultados: ${escapeHtml(err.message)}</div>`;
        }
    });

    // ============================================================
    // Lógica do Módulo Mentes Clones
    // ============================================================

    // Elementos DOM
    const clonesList = document.getElementById('clones-list');
    const btnShowCreateClone = document.getElementById('btn-show-create-clone');
    const panelCreateClone = document.getElementById('panel-create-clone');
    const panelChatClone = document.getElementById('panel-chat-clone');
    const panelEmptyClone = document.getElementById('panel-empty-clone');
    
    const cloneCreationForm = document.getElementById('clone-creation-form');
    const cloneNameInput = document.getElementById('clone-name-input');
    const cloneUrlInput = document.getElementById('clone-url-input');
    const cloneVideosLimit = document.getElementById('clone-videos-limit');
    const btnSubmitCloneText = document.getElementById('btn-submit-clone-text');
    const cloneCreationStatus = document.getElementById('clone-creation-status');

    const chatTitleName = document.getElementById('chat-title-name');
    const chatTitleStatus = document.getElementById('chat-title-status');
    const btnToggleBlueprint = document.getElementById('btn-toggle-blueprint');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const chatMessages = document.getElementById('chat-messages');
    const chatBlueprintPanel = document.getElementById('chat-blueprint-panel');
    const btnCloseBlueprint = document.getElementById('btn-close-blueprint');
    const chatBlueprintContent = document.getElementById('chat-blueprint-content');
    
    const chatSendForm = document.getElementById('chat-send-form');
    const chatUserInput = document.getElementById('chat-user-input');
    const btnChatSendText = document.getElementById('btn-chat-send-text');

    // Estado local
    let currentActiveClone = null;
    let cloneActiveBlueprint = null;
    let isSendingMessage = false;

    // Ações de exibição de painéis
    if (btnShowCreateClone) {
        btnShowCreateClone.addEventListener('click', () => {
            panelCreateClone.style.display = 'block';
            panelChatClone.style.display = 'none';
            panelEmptyClone.style.display = 'none';
            cloneCreationForm.reset();
            cloneCreationStatus.innerHTML = '';
            
            // Remove active class from list
            document.querySelectorAll('.clone-item').forEach(item => item.classList.remove('active'));
        });
    }

    if (btnCloseBlueprint) {
        btnCloseBlueprint.addEventListener('click', () => {
            chatBlueprintPanel.style.display = 'none';
        });
    }

    if (btnToggleBlueprint) {
        btnToggleBlueprint.addEventListener('click', () => {
            if (chatBlueprintPanel.style.display === 'none') {
                chatBlueprintPanel.style.display = 'flex';
                chatBlueprintContent.innerHTML = parseMarkdown(cloneActiveBlueprint || '*Nenhum modelo mental sintetizado ainda.*');
            } else {
                chatBlueprintPanel.style.display = 'none';
            }
        });
    }

    // Submissão do formulário de criação de clone
    if (cloneCreationForm) {
        cloneCreationForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = cloneNameInput.value.trim();
            const channel_url = cloneUrlInput.value.trim();
            const max_videos = parseInt(cloneVideosLimit.value) || 10;

            if (!name || !channel_url) return;

            btnSubmitCloneText.textContent = 'Iniciando...';
            cloneCreationStatus.innerHTML = '';

            try {
                await apiFetch('/api/clones', {
                    method: 'POST',
                    body: JSON.stringify({ name, channel_url, max_videos })
                });

                cloneCreationStatus.innerHTML = `
                    <div class="status-message status-success">
                        🧠 Clone mental <strong>${escapeHtml(name)}</strong> iniciado!<br>
                        <small>A transcrição e análise estão rodando em segundo plano. Acompanhe o status na barra lateral.</small>
                    </div>
                `;
                cloneCreationForm.reset();
                await loadClones();
            } catch (err) {
                cloneCreationStatus.innerHTML = `<div class="status-message status-error">❌ ${escapeHtml(err.message)}</div>`;
            } finally {
                btnSubmitCloneText.textContent = 'Iniciar Clonagem Mental';
            }
        });
    }

    // Carregar e listar clones mentais
    async function loadClones() {
        if (!clonesList) return;
        try {
            const clones = await apiFetch('/api/clones');
            renderClones(clones);

            // Se houver algum em andamento, inicia polling geral
            const needsPolling = clones.some(c => c.status === 'transcribing' || c.status === 'analyzing');
            if (needsPolling) {
                startClonesPolling();
            }
        } catch (err) {
            console.error('Erro ao carregar clones:', err);
            clonesList.innerHTML = `<div class="empty-state"><p>Erro ao carregar clones.</p></div>`;
        }
    }

    function renderClones(clones) {
        if (!clonesList) return;
        if (clones.length === 0) {
            clonesList.innerHTML = `
                <div class="empty-state">
                    <p style="font-size: 0.8rem;">Nenhum cérebro clonado.</p>
                </div>
            `;
            return;
        }

        clonesList.innerHTML = clones.map(c => {
            const isActive = currentActiveClone && currentActiveClone.id === c.id;
            let statusText = '';
            let statusClass = '';

            switch (c.status) {
                case 'transcribing':
                    statusText = 'Transcrevendo';
                    statusClass = 'status-transcribing';
                    break;
                case 'analyzing':
                    statusText = 'Analisando';
                    statusClass = 'status-analyzing';
                    break;
                case 'completed':
                    statusText = 'Pronto';
                    statusClass = 'status-completed';
                    break;
                case 'failed':
                    statusText = 'Falhou';
                    statusClass = 'status-failed';
                    break;
            }

            return `
                <div class="clone-item ${isActive ? 'active' : ''}" data-id="${c.id}">
                    <div class="clone-item-header">
                        <span class="clone-item-name">${escapeHtml(c.name)}</span>
                        <button class="clone-item-delete" data-id="${c.id}">✕</button>
                    </div>
                    <span class="clone-item-status ${statusClass}">${statusText}</span>
                </div>
            `;
        }).join('');

        // Listeners nos itens da lista
        document.querySelectorAll('.clone-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.classList.contains('clone-item-delete')) return;
                
                const id = parseInt(item.getAttribute('data-id'));
                const clone = clones.find(c => c.id === id);
                if (clone) selectClone(clone);
            });
        });

        // Listeners nos botões de deletar
        document.querySelectorAll('.clone-item-delete').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.getAttribute('data-id'));
                if (confirm('Tem certeza que deseja apagar permanentemente este clone e todo o histórico?')) {
                    try {
                        await apiFetch(`/api/clones/${id}`, { method: 'DELETE' });
                        if (currentActiveClone && currentActiveClone.id === id) {
                            currentActiveClone = null;
                            panelChatClone.style.display = 'none';
                            panelEmptyClone.style.display = 'flex';
                        }
                        loadClones();
                    } catch (err) {
                        alert('Erro ao excluir: ' + err.message);
                    }
                }
            });
        });
    }

    // Polling de atualização de status dos clones
    let clonesPollInterval = null;
    function startClonesPolling() {
        if (clonesPollInterval) return;

        clonesPollInterval = setInterval(async () => {
            try {
                const clones = await apiFetch('/api/clones');
                renderClones(clones);
                
                // Se o ativo estiver em andamento, atualiza status/blueprint
                if (currentActiveClone) {
                    const activeUpdate = clones.find(c => c.id === currentActiveClone.id);
                    if (activeUpdate) {
                        currentActiveClone = activeUpdate;
                        cloneActiveBlueprint = activeUpdate.blueprint;
                        chatTitleStatus.textContent = activeUpdate.status === 'completed' ? 'Pronto' : 'Atualizando';
                    }
                }

                const stillRunning = clones.some(c => c.status === 'transcribing' || c.status === 'analyzing');
                if (!stillRunning) {
                    clearInterval(clonesPollInterval);
                    clonesPollInterval = null;
                }
            } catch (err) {
                console.error(err);
            }
        }, 5000);
    }

    // Seleção de um clone para conversar
    async function selectClone(clone) {
        currentActiveClone = clone;
        cloneActiveBlueprint = clone.blueprint;
        
        // UI Selection Highlight
        document.querySelectorAll('.clone-item').forEach(item => {
            const itemId = parseInt(item.getAttribute('data-id'));
            if (itemId === clone.id) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        panelCreateClone.style.display = 'none';
        panelEmptyClone.style.display = 'none';
        panelChatClone.style.display = 'flex';
        chatBlueprintPanel.style.display = 'none';

        chatTitleName.textContent = clone.name;
        chatTitleStatus.textContent = clone.status === 'completed' ? 'Pronto' : 'Processando...';

        // Carrega histórico
        chatMessages.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Carregando conversa...</div>';
        
        try {
            const messages = await apiFetch(`/api/clones/${clone.id}/messages`);
            renderMessages(messages);
        } catch (err) {
            chatMessages.innerHTML = `<div style="text-align: center; color: var(--error); padding: 20px;">Erro ao carregar histórico: ${escapeHtml(err.message)}</div>`;
        }
    }

    function renderMessages(messages) {
        if (!chatMessages) return;
        if (messages.length === 0) {
            chatMessages.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 0.9rem;">
                    👋 Comece a conversar! Pergunte sobre a filosofia dele(a), ideias de vídeos ou peça conselhos de negócios.
                </div>
            `;
            return;
        }

        chatMessages.innerHTML = messages.map(msg => {
            const isUser = msg.role === 'user';
            const senderName = isUser ? 'Você' : currentActiveClone.name;
            return `
                <div class="chat-message ${isUser ? 'user' : 'assistant'}">
                    <span class="chat-message-sender">${escapeHtml(senderName)}</span>
                    <div class="chat-message-bubble">${escapeHtml(msg.content)}</div>
                </div>
            `;
        }).join('');

        // Scroll ao fim
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Enviar mensagem
    if (chatSendForm) {
        chatSendForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!currentActiveClone || isSendingMessage) return;

            const text = chatUserInput.value.trim();
            if (!text) return;

            chatUserInput.value = '';
            isSendingMessage = true;
            btnChatSendText.textContent = 'Pensando...';

            // 1. Renderiza mensagem do usuário localmente
            const userMsgHtml = `
                <div class="chat-message user">
                    <span class="chat-message-sender">Você</span>
                    <div class="chat-message-bubble">${escapeHtml(text)}</div>
                </div>
            `;
            if (chatMessages.querySelector('div[style*="text-align"]')) {
                chatMessages.innerHTML = '';
            }
            chatMessages.insertAdjacentHTML('beforeend', userMsgHtml);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // 2. Renderiza indicador de digitação (typing)
            const typingId = 'chat-typing-indicator';
            const typingHtml = `
                <div class="chat-message assistant" id="${typingId}">
                    <span class="chat-message-sender">${escapeHtml(currentActiveClone.name)}</span>
                    <div class="chat-message-bubble" style="opacity: 0.7;">✍️ Pensando...</div>
                </div>
            `;
            chatMessages.insertAdjacentHTML('beforeend', typingHtml);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                // 3. Envia para o backend
                const result = await apiFetch(`/api/clones/${currentActiveClone.id}/messages`, {
                    method: 'POST',
                    body: JSON.stringify({ content: text })
                });

                // 4. Remove typing e adiciona resposta real
                const typingEl = document.getElementById(typingId);
                if (typingEl) typingEl.remove();
                
                const replyHtml = `
                    <div class="chat-message assistant">
                        <span class="chat-message-sender">${escapeHtml(currentActiveClone.name)}</span>
                        <div class="chat-message-bubble">${escapeHtml(result.response)}</div>
                    </div>
                `;
                chatMessages.insertAdjacentHTML('beforeend', replyHtml);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            } catch (err) {
                const typingEl = document.getElementById(typingId);
                if (typingEl) typingEl.remove();
                
                const errorHtml = `
                    <div class="chat-message assistant" style="color: var(--error);">
                        <span class="chat-message-sender">Erro</span>
                        <div class="chat-message-bubble" style="border-color: rgba(248,113,113,0.3);">❌ Não foi possível obter resposta: ${escapeHtml(err.message)}</div>
                    </div>
                `;
                chatMessages.insertAdjacentHTML('beforeend', errorHtml);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            } finally {
                isSendingMessage = false;
                btnChatSendText.textContent = 'Enviar';
            }
        });
    }

    // Limpar histórico do chat
    if (btnClearChat) {
        btnClearChat.addEventListener('click', async () => {
            if (!currentActiveClone) return;
            if (confirm('Tem certeza que deseja apagar todo o histórico deste chat?')) {
                try {
                    await apiFetch(`/api/clones/${currentActiveClone.id}/messages`, { method: 'DELETE' });
                    chatMessages.innerHTML = '';
                    selectClone(currentActiveClone);
                } catch (err) {
                    alert('Erro ao limpar chat: ' + err.message);
                }
            }
        });
    }

    // Parser simples de markdown para exibir o Blueprint
    function parseMarkdown(md) {
        if (!md) return '';
        let html = md;
        
        // Escape HTML
        html = html
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        
        // Cabeçalhos
        html = html.replace(/^# (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*?)$/gm, '<h4>$1</h4>');
        html = html.replace(/^### (.*?)$/gm, '<h5>$1</h5>');
        
        // Negrito
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Listas simples
        html = html.replace(/^\- (.*?)$/gm, '<li>$1</li>');
        
        // Parágrafos
        html = html.split(/\n{2,}/).map(p => {
            if (p.trim().startsWith('<h') || p.trim().startsWith('<li')) {
                return p;
            }
            return `<p>${p.replace(/\n/g, '<br>')}</p>`;
        }).join('\n');
        
        return html;
    }

})();


