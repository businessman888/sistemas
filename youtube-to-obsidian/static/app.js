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

        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            try {
                data = await response.json();
            } catch (e) {
                // Ignore parse errors, will use fallback detail
            }
        }

        if (!response.ok) {
            const errorMsg = (data && data.detail) || `Erro no servidor (status ${response.status}).`;
            const error = new Error(errorMsg);
            error.status = response.status;
            error.data = data || { detail: errorMsg };
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
    const navBrain = document.getElementById('nav-brain');
    const navOrchestrator = document.getElementById('nav-orchestrator');
    const navCreativeHub = document.getElementById('nav-creative-hub');
    const moduleYoutube = document.getElementById('module-youtube');
    const moduleSocialMedia = document.getElementById('module-social-media');
    const moduleClone = document.getElementById('module-clone');
    const moduleBrain = document.getElementById('module-brain');
    const moduleOrchestrator = document.getElementById('module-orchestrator');
    const moduleCreativeHub = document.getElementById('module-creative-hub');

    // Troca de módulo na Sidebar
    function switchModule(activeNav, activeModule) {
        [navYoutube, navSocialMedia, navClone, navBrain, navOrchestrator, navCreativeHub].forEach(nav => {
            if (nav) nav.classList.remove('active');
        });
        [moduleYoutube, moduleSocialMedia, moduleClone, moduleBrain, moduleOrchestrator, moduleCreativeHub].forEach(mod => {
            if (mod) mod.style.display = 'none';
        });
        activeNav.classList.add('active');
        if (activeModule === moduleOrchestrator) {
            activeModule.style.display = 'flex';
        } else {
            activeModule.style.display = 'block';
        }

        // Toggle wide layout for Orchestrator, Brain or Creative Hub
        const osContent = document.querySelector('.os-content');
        if (osContent) {
            if (activeModule === moduleOrchestrator || activeModule === moduleBrain || activeModule === moduleCreativeHub) {
                osContent.classList.add('wide-layout');
            } else {
                osContent.classList.remove('wide-layout');
            }
        }
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

    if (navBrain) {
        navBrain.addEventListener('click', () => {
            switchModule(navBrain, moduleBrain);
            initBrainModule();
        });
    }

    if (navOrchestrator) {
        navOrchestrator.addEventListener('click', () => {
            switchModule(navOrchestrator, moduleOrchestrator);
            loadProjects();
        });
    }

    if (navCreativeHub) {
        navCreativeHub.addEventListener('click', () => {
            switchModule(navCreativeHub, moduleCreativeHub);
        });
    }

    // --- Lógica do Modal do Creative Hub ---
    const creativeHubOverlay = document.getElementById('creative-hub-overlay');
    const creativeTemplates = document.getElementById('creative-templates');
    const creativeModalTitle = document.getElementById('creative-modal-title');
    const creativeModalMeta = document.getElementById('creative-modal-meta');
    const creativeModalBody = document.getElementById('creative-modal-body');

    window.openCreativeModal = function(id) {
        if (!creativeTemplates || !creativeModalTitle || !creativeModalMeta || !creativeModalBody || !creativeHubOverlay) return;
        const tpl = creativeTemplates.querySelector(`[data-tpl="${id}"]`);
        if (!tpl) return;

        creativeModalTitle.textContent = tpl.getAttribute('data-title') || '';
        creativeModalMeta.innerHTML = tpl.getAttribute('data-meta') || '';
        creativeModalBody.innerHTML = tpl.innerHTML;

        creativeHubOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    };

    window.closeCreativeModal = function() {
        if (!creativeHubOverlay) return;
        creativeHubOverlay.style.display = 'none';
        document.body.style.overflow = '';
    };

    // Fechar ao pressionar Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            window.closeCreativeModal();
        }
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
        let data;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            try {
                data = await response.json();
            } catch (e) {
                // Ignore parse errors, will use fallback detail
            }
        }
        if (!response.ok) {
            const errorMsg = (data && data.detail) || `Erro na requisição: ${response.status} ${response.statusText}`;
            throw new Error(errorMsg);
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
            panelCreateClone.style.display = 'flex';
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

    // ============================================================
    // Lógica do Módulo Orquestrador de Projetos
    // ============================================================

    let activeProjectId = null;
    let activeProjectData = null;
    let zoom = 1.0;
    let panX = 100;
    let panY = 100;
    let isPanning = false;
    let startPanX = 0;
    let startPanY = 0;
    let draggingNode = null;
    let dragStartNodeX = 0;
    let dragStartNodeY = 0;
    let dragStartMouseX = 0;
    let dragStartMouseY = 0;
    let isDraggingNode = false;
    let connectingFromId = null;
    let tempLine = null;
    let editingPhase = null;

    // --- DOM Elements ---
    const projectsList = document.getElementById('projects-list');
    const btnShowCreateProject = document.getElementById('btn-show-create-project');
    const panelCreateProject = document.getElementById('panel-create-project');
    const panelManageProject = document.getElementById('panel-manage-project');
    const panelEmptyProject = document.getElementById('panel-empty-project');
    
    const projectCreationForm = document.getElementById('project-creation-form');
    const projectNameInput = document.getElementById('project-name-input');
    const projectDescInput = document.getElementById('project-desc-input');
    const btnSubmitProject = document.getElementById('btn-submit-project');
    const projectCreationStatus = document.getElementById('project-creation-status');

    const projectTitleName = document.getElementById('project-title-name');
    const projectTitleDesc = document.getElementById('project-title-desc');
    const btnDeleteProject = document.getElementById('btn-delete-project');

    // Tabs
    const tabCanvas = document.getElementById('tab-canvas');
    const tabChecklist = document.getElementById('tab-checklist');
    const tabContentCanvas = document.getElementById('tab-content-canvas');
    const tabContentChecklist = document.getElementById('tab-content-checklist');

    // Canvas
    const canvasContainer = document.getElementById('canvas-container');
    const canvasViewport = document.getElementById('canvas-viewport');
    const canvasSvg = document.getElementById('canvas-svg');
    
    const btnCanvasAddNode = document.getElementById('btn-canvas-add-node');
    const btnCanvasZoomIn = document.getElementById('btn-canvas-zoom-in');
    const btnCanvasZoomOut = document.getElementById('btn-canvas-zoom-out');
    const btnCanvasZoomReset = document.getElementById('btn-canvas-zoom-reset');
    const btnCanvasSave = document.getElementById('btn-canvas-save');
    const canvasSaveStatus = document.getElementById('canvas-save-status');

    // Checklist
    const checklistItemsContainer = document.getElementById('checklist-items-container');
    const projectProgressBar = document.getElementById('project-progress-bar');
    const projectProgressPercentage = document.getElementById('project-progress-percentage');

    // Phase Modal
    const modalPhaseEdit = document.getElementById('modal-phase-edit');
    const phaseEditForm = document.getElementById('phase-edit-form');
    const phaseIdInput = document.getElementById('phase-id-input');
    const phaseTitleInput = document.getElementById('phase-title-input');
    const phaseDescInput = document.getElementById('phase-desc-input');
    const phaseStatusInput = document.getElementById('phase-status-input');
    const btnClosePhaseModal = document.getElementById('btn-close-phase-modal');
    const btnDeletePhase = document.getElementById('btn-delete-phase');
    const btnSavePhase = document.getElementById('btn-save-phase');
    const modalPhaseTitleAction = document.getElementById('modal-phase-title-action');

    // Subtasks Elements
    const modalSubtasksWrapper = document.getElementById('modal-subtasks-wrapper');
    const subtasksCount = document.getElementById('subtasks-count');
    const newSubtaskTitle = document.getElementById('new-subtask-title');
    const btnAddSubtask = document.getElementById('btn-add-subtask');
    const subtasksListContainer = document.getElementById('subtasks-list-container');

    async function loadProjects() {
        if (!projectsList) return;
        try {
            const projects = await apiFetch('/api/projects');
            renderProjects(projects);
        } catch (err) {
            console.error('Erro ao carregar projetos:', err);
            projectsList.innerHTML = `<div class="empty-state"><p>Erro ao carregar aplicativos.</p></div>`;
        }
    }

    function renderProjects(projects) {
        if (!projectsList) return;
        if (projects.length === 0) {
            projectsList.innerHTML = `<div class="empty-state"><p style="font-size: 0.8rem;">Nenhum app cadastrado.</p></div>`;
            return;
        }

        projectsList.innerHTML = projects.map(p => {
            const isActive = activeProjectId === p.id;
            return `
                <div class="project-item ${isActive ? 'active' : ''}" data-id="${p.id}">
                    <div class="project-item-name">${escapeHtml(p.name)}</div>
                    <div class="project-item-desc">${escapeHtml(p.description || 'Sem descrição')}</div>
                </div>
            `;
        }).join('');

        document.querySelectorAll('.project-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = parseInt(item.getAttribute('data-id'));
                selectProject(id);
            });
        });
    }

    async function selectProject(id) {
        activeProjectId = id;
        
        document.querySelectorAll('.project-item').forEach(item => {
            if (parseInt(item.getAttribute('data-id')) === id) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        panelEmptyProject.style.display = 'none';
        panelCreateProject.style.display = 'none';
        panelManageProject.style.display = 'flex';

        try {
            const data = await apiFetch(`/api/projects/${id}`);
            activeProjectData = data;
            
            projectTitleName.textContent = data.project.name;
            projectTitleDesc.textContent = data.project.description || 'Sem descrição cadastrada.';

            // Reset zoom/pan
            zoom = 1.0;
            panX = 50;
            panY = 50;
            updateCanvasTransform();

            // Explicitly sync/reset tab active state on select
            if (tabCanvas && tabChecklist && tabContentCanvas && tabContentChecklist) {
                tabCanvas.classList.add('active');
                tabChecklist.classList.remove('active');
                tabContentCanvas.style.display = 'flex';
                tabContentChecklist.style.display = 'none';
            }

            renderCanvas();
            renderChecklist();
        } catch (err) {
            console.error('Erro ao carregar detalhes do projeto:', err);
            alert('Falha ao abrir o projeto: ' + err.message);
        }
    }

    function screenToCanvasCoords(clientX, clientY) {
        const rect = canvasContainer.getBoundingClientRect();
        const x = (clientX - rect.left - panX) / zoom;
        const y = (clientY - rect.top - panY) / zoom;
        return { x, y };
    }

    function renderCanvas() {
        if (!activeProjectData || !canvasViewport) return;
        
        // Remove nodes antigos
        const oldNodes = canvasViewport.querySelectorAll('.canvas-node');
        oldNodes.forEach(node => node.remove());

        const phases = activeProjectData.phases;
        
        phases.forEach(phase => {
            const nodeEl = document.createElement('div');
            nodeEl.className = 'canvas-node';
            if (phase.status === 'completed') {
                nodeEl.classList.add('completed-node');
            }
            
            nodeEl.setAttribute('data-id', phase.id);
            nodeEl.style.left = phase.pos_x + 'px';
            nodeEl.style.top = phase.pos_y + 'px';
            
            const subCount = phase.subtasks ? phase.subtasks.length : 0;
            const subCompleted = phase.subtasks ? phase.subtasks.filter(s => s.status === 'completed').length : 0;
            const progressBadge = subCount > 0 ? `<span class="node-progress-badge">${subCompleted}/${subCount}</span>` : '';
            
            nodeEl.innerHTML = `
                <div class="node-header">
                    <div class="checklist-item-checkbox node-checkbox" title="Marcar como concluído">
                        ${phase.status === 'completed' ? '✓' : ''}
                    </div>
                    <div class="node-title-container">
                        <div class="node-title" title="${escapeHtml(phase.title)}">
                            ${escapeHtml(phase.title)}
                            ${progressBadge}
                        </div>
                    </div>
                    <button class="btn-node-edit" title="Editar ou Excluir">✏️</button>
                </div>
                <div class="node-desc">${escapeHtml(phase.description || 'Sem descrição')}</div>
                <div class="node-handle-out" title="Conectar a outra fase"></div>
            `;

            canvasViewport.appendChild(nodeEl);
            
            makeDraggable(nodeEl, phase);

            nodeEl.querySelector('.btn-node-edit').addEventListener('click', (e) => {
                e.stopPropagation();
                openPhaseModal(phase);
            });

            nodeEl.querySelector('.node-checkbox').addEventListener('click', async (e) => {
                e.stopPropagation();
                phase.status = phase.status === 'completed' ? 'pending' : 'completed';
                try {
                    await apiFetch(`/api/projects/${activeProjectId}/phases/${phase.id}`, {
                        method: 'PUT',
                        body: JSON.stringify(phase)
                    });
                    renderCanvas();
                    renderChecklist();
                } catch (err) {
                    console.error('Erro ao atualizar status do nó:', err);
                }
            });

            const handle = nodeEl.querySelector('.node-handle-out');
            handle.addEventListener('mousedown', (e) => {
                e.stopPropagation();
                e.preventDefault();
                
                connectingFromId = phase.id;
                
                const x1 = phase.pos_x + 220;
                const y1 = phase.pos_y + (nodeEl.offsetHeight / 2 || 40);
                
                tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                tempLine.setAttribute('x1', x1);
                tempLine.setAttribute('y1', y1);
                tempLine.setAttribute('x2', x1);
                tempLine.setAttribute('y2', y1);
                tempLine.setAttribute('class', 'connection-line-pending');
                tempLine.setAttribute('stroke', '#00C3FF');
                tempLine.setAttribute('stroke-width', '2.5');
                tempLine.setAttribute('stroke-dasharray', '4 4');
                
                canvasSvg.appendChild(tempLine);
            });
        });

        setTimeout(drawConnections, 0);
    }

    function makeDraggable(nodeEl, phase) {
        nodeEl.addEventListener('mousedown', (e) => {
            if (e.target.closest('.node-checkbox') || e.target.closest('.btn-node-edit') || e.target.closest('.node-handle-out')) {
                return;
            }
            e.stopPropagation();
            
            isDraggingNode = true;
            draggingNode = nodeEl;
            nodeEl.classList.add('dragging');
            
            dragStartNodeX = phase.pos_x;
            dragStartNodeY = phase.pos_y;
            dragStartMouseX = e.clientX;
            dragStartMouseY = e.clientY;
        });
    }

    function drawConnections() {
        if (!activeProjectData || !canvasSvg) return;
        
        const paths = canvasSvg.querySelectorAll('path');
        paths.forEach(p => p.remove());

        activeProjectData.connections.forEach(conn => {
            const fromPhase = activeProjectData.phases.find(p => p.id === conn.from_phase_id);
            const toPhase = activeProjectData.phases.find(p => p.id === conn.to_phase_id);
            
            if (!fromPhase || !toPhase) return;
            
            const fromNodeEl = document.querySelector(`.canvas-node[data-id="${conn.from_phase_id}"]`);
            const toNodeEl = document.querySelector(`.canvas-node[data-id="${conn.to_phase_id}"]`);
            
            const fromHeight = fromNodeEl ? fromNodeEl.offsetHeight : 80;
            const toHeight = toNodeEl ? toNodeEl.offsetHeight : 80;
            
            const x1 = fromPhase.pos_x + 220;
            const y1 = fromPhase.pos_y + fromHeight / 2;
            const x2 = toPhase.pos_x;
            const y2 = toPhase.pos_y + toHeight / 2;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            
            const controlOffset = Math.max(Math.abs(x2 - x1) / 2, 40);
            const d = `M ${x1} ${y1} C ${x1 + controlOffset} ${y1}, ${x2 - controlOffset} ${y2}, ${x2} ${y2}`;
            
            path.setAttribute('d', d);
            
            const isCompleted = fromPhase.status === 'completed';
            
            path.setAttribute('class', isCompleted ? 'connection-line-completed' : 'connection-line-pending');
            path.setAttribute('marker-end', isCompleted ? 'url(#arrow-completed)' : 'url(#arrow)');
            
            path.setAttribute('data-from', conn.from_phase_id);
            path.setAttribute('data-to', conn.to_phase_id);
            
            path.style.pointerEvents = 'stroke';
            path.style.cursor = 'pointer';
            path.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                if (confirm('Deseja remover esta conexão visual?')) {
                    activeProjectData.connections = activeProjectData.connections.filter(
                        c => !(c.from_phase_id === conn.from_phase_id && c.to_phase_id === conn.to_phase_id)
                    );
                    saveCanvasStateInBackground();
                    drawConnections();
                }
            });
            
            canvasSvg.appendChild(path);
        });
    }

    async function saveCanvasStateInBackground() {
        if (!activeProjectId || !activeProjectData) return;
        
        const payload = {
            positions: activeProjectData.phases.map(p => ({
                id: p.id,
                pos_x: p.pos_x,
                pos_y: p.pos_y
            })),
            connections: activeProjectData.connections.map(c => ({
                from_phase_id: c.from_phase_id,
                to_phase_id: c.to_phase_id
            }))
        };
        
        try {
            canvasSaveStatus.textContent = '💾 Salvando...';
            await apiFetch(`/api/projects/${activeProjectId}/canvas/sync`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            canvasSaveStatus.textContent = '✅ Canvas Salvo';
            setTimeout(() => { canvasSaveStatus.textContent = ''; }, 3000);
        } catch (err) {
            console.error('Erro ao sincronizar canvas:', err);
            canvasSaveStatus.textContent = '❌ Erro ao salvar';
        }
    }

    function updateCanvasTransform() {
        if (!canvasViewport) return;
        canvasViewport.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
    }

    function renderChecklist() {
        if (!activeProjectData || !checklistItemsContainer) return;
        
        const phases = activeProjectData.phases;
        const total = phases.length;
        const completed = phases.filter(p => p.status === 'completed').length;
        const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
        
        projectProgressBar.style.width = percentage + '%';
        projectProgressPercentage.textContent = percentage + '%';

        if (total === 0) {
            checklistItemsContainer.innerHTML = `
                <div class="empty-state">
                    <p style="font-size: 0.85rem;">Nenhuma fase cadastrada. Crie uma fase no Canvas Visual ou clique no botão abaixo.</p>
                    <button id="btn-checklist-add-phase" class="btn-import" style="width: auto; margin: 12px auto 0; padding: 8px 16px;">➕ Adicionar Primeira Fase</button>
                </div>
            `;
            const btnAdd = document.getElementById('btn-checklist-add-phase');
            if (btnAdd) {
                btnAdd.addEventListener('click', () => {
                    openPhaseModal(null, 150, 150);
                });
            }
            return;
        }

        checklistItemsContainer.innerHTML = phases.map(phase => {
            const isComp = phase.status === 'completed';
            
            const subCount = phase.subtasks ? phase.subtasks.length : 0;
            const subCompleted = phase.subtasks ? phase.subtasks.filter(s => s.status === 'completed').length : 0;
            const progressBadge = subCount > 0 ? `<span style="font-size: 0.75rem; color: var(--text-secondary); margin-left: 6px;">(${subCompleted}/${subCount})</span>` : '';

            const subtasksHtml = (phase.subtasks && phase.subtasks.length > 0) ? `
                <div class="checklist-subtasks-list">
                    ${phase.subtasks.map(sub => {
                        const subComp = sub.status === 'completed';
                        return `
                            <div class="checklist-subtask-item ${subComp ? 'completed' : ''}" data-sub-id="${sub.id}" data-phase-id="${phase.id}">
                                <div class="checklist-subtask-checkbox" title="Marcar subtarefa">
                                    ${subComp ? '✓' : ''}
                                </div>
                                <span class="checklist-subtask-title">${escapeHtml(sub.title)}</span>
                            </div>
                        `;
                    }).join('')}
                </div>
            ` : '';

            return `
                <div class="checklist-item ${isComp ? 'completed' : ''}" data-id="${phase.id}">
                    <div class="checklist-item-checkbox" title="Marcar status">
                        ${isComp ? '✓' : ''}
                    </div>
                    <div class="checklist-item-info">
                        <div class="checklist-item-title">${escapeHtml(phase.title)} ${progressBadge}</div>
                        <div class="checklist-item-desc">${escapeHtml(phase.description || 'Sem descrição')}</div>
                        ${subtasksHtml}
                    </div>
                    <button class="btn-node-edit btn-checklist-edit" title="Editar">✏️</button>
                </div>
            `;
        }).join('');

        document.querySelectorAll('.checklist-item').forEach(item => {
            const id = parseInt(item.getAttribute('data-id'));
            const phase = phases.find(p => p.id === id);
            
            const cb = item.querySelector('.checklist-item-checkbox');
            cb.addEventListener('click', async (e) => {
                e.stopPropagation();
                if (phase) {
                    phase.status = phase.status === 'completed' ? 'pending' : 'completed';
                    try {
                        await apiFetch(`/api/projects/${activeProjectId}/phases/${id}`, {
                            method: 'PUT',
                            body: JSON.stringify(phase)
                        });
                        renderCanvas();
                        renderChecklist();
                    } catch (err) {
                        console.error('Erro ao atualizar checklist:', err);
                    }
                }
            });

            // Listeners para as subtarefas do checklist
            item.querySelectorAll('.checklist-subtask-item').forEach(subItem => {
                const subId = parseInt(subItem.getAttribute('data-sub-id'));
                const phaseId = parseInt(subItem.getAttribute('data-phase-id'));
                const subCheckbox = subItem.querySelector('.checklist-subtask-checkbox');
                
                subCheckbox.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const parentPhase = phases.find(p => p.id === phaseId);
                    if (!parentPhase) return;
                    
                    const subtask = parentPhase.subtasks.find(s => s.id === subId);
                    if (!subtask) return;
                    
                    const newStatus = subtask.status === 'completed' ? 'pending' : 'completed';
                    
                    try {
                        const updatedSub = await apiFetch(`/api/projects/${activeProjectId}/phases/${phaseId}/subtasks/${subId}`, {
                            method: 'PUT',
                            body: JSON.stringify({
                                title: subtask.title,
                                status: newStatus
                            })
                        });
                        
                        // Atualizar localmente
                        subtask.status = updatedSub.status;
                        
                        // Re-renderizar canvas e checklist
                        renderCanvas();
                        renderChecklist();
                    } catch (err) {
                        console.error('Erro ao atualizar subtarefa no checklist:', err);
                        alert('Erro ao atualizar subtarefa: ' + err.message);
                    }
                });
            });

            const editBtn = item.querySelector('.btn-checklist-edit');
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openPhaseModal(phase);
            });
        });
    }

    function openPhaseModal(phase, defaultX = 100, defaultY = 100) {
        if (!modalPhaseEdit) return;
        modalPhaseEdit.style.display = 'flex';
        
        if (phase) {
            editingPhase = phase;
            modalPhaseTitleAction.textContent = 'Editar Fase';
            phaseIdInput.value = phase.id;
            phaseTitleInput.value = phase.title;
            phaseDescInput.value = phase.description || '';
            phaseStatusInput.value = phase.status;
            btnDeletePhase.style.display = 'block';
            phaseEditForm.dataset.x = phase.pos_x;
            phaseEditForm.dataset.y = phase.pos_y;
            
            // Subtasks
            if (modalSubtasksWrapper) modalSubtasksWrapper.style.display = 'block';
            renderModalSubtasks(phase);
        } else {
            editingPhase = null;
            modalPhaseTitleAction.textContent = 'Criar Nova Fase';
            phaseIdInput.value = '';
            phaseTitleInput.value = '';
            phaseDescInput.value = '';
            phaseStatusInput.value = 'pending';
            btnDeletePhase.style.display = 'none';
            phaseEditForm.dataset.x = defaultX;
            phaseEditForm.dataset.y = defaultY;
            
            // Subtasks (esconder na criação de fase)
            if (modalSubtasksWrapper) modalSubtasksWrapper.style.display = 'none';
        }
    }

    function renderModalSubtasks(phase) {
        if (!subtasksListContainer) return;
        
        newSubtaskTitle.value = '';
        const subtasks = phase.subtasks || [];
        const completedCount = subtasks.filter(s => s.status === 'completed').length;
        
        if (subtasksCount) {
            subtasksCount.textContent = `${completedCount} de ${subtasks.length} concluídas`;
        }
        
        if (subtasks.length === 0) {
            subtasksListContainer.innerHTML = '<div style="font-size: 0.8rem; color: var(--text-secondary); text-align: center; padding: 12px;">Nenhuma subtarefa adicionada.</div>';
            return;
        }
        
        subtasksListContainer.innerHTML = subtasks.map(sub => {
            const isComp = sub.status === 'completed';
            return `
                <div class="modal-subtask-item ${isComp ? 'completed' : ''}" data-sub-id="${sub.id}">
                    <div class="modal-subtask-checkbox" title="Alternar status">
                        ${isComp ? '✓' : ''}
                    </div>
                    <span class="modal-subtask-title">${escapeHtml(sub.title)}</span>
                    <button type="button" class="btn-delete-subtask" title="Excluir subtarefa">✕</button>
                </div>
            `;
        }).join('');
        
        // Listeners das subtarefas dentro do modal
        subtasksListContainer.querySelectorAll('.modal-subtask-item').forEach(item => {
            const subId = parseInt(item.getAttribute('data-sub-id'));
            const sub = subtasks.find(s => s.id === subId);
            
            // Alternar status
            item.querySelector('.modal-subtask-checkbox').addEventListener('click', async () => {
                const newStatus = sub.status === 'completed' ? 'pending' : 'completed';
                try {
                    const updated = await apiFetch(`/api/projects/${activeProjectId}/phases/${phase.id}/subtasks/${subId}`, {
                        method: 'PUT',
                        body: JSON.stringify({ title: sub.title, status: newStatus })
                    });
                    sub.status = updated.status;
                    renderModalSubtasks(phase);
                    renderCanvas();
                    renderChecklist();
                } catch (err) {
                    alert('Erro ao atualizar subtarefa: ' + err.message);
                }
            });
            
            // Remover subtarefa
            item.querySelector('.btn-delete-subtask').addEventListener('click', async () => {
                if (confirm(`Deseja remover a subtarefa "${sub.title}"?`)) {
                    try {
                        await apiFetch(`/api/projects/${activeProjectId}/phases/${phase.id}/subtasks/${subId}`, {
                            method: 'DELETE'
                        });
                        phase.subtasks = phase.subtasks.filter(s => s.id !== subId);
                        renderModalSubtasks(phase);
                        renderCanvas();
                        renderChecklist();
                    } catch (err) {
                        alert('Erro ao remover subtarefa: ' + err.message);
                    }
                }
            });
        });
    }

    async function handleAddSubtask() {
        if (!editingPhase) return;
        const title = newSubtaskTitle.value.trim();
        if (!title) return;
        
        try {
            const created = await apiFetch(`/api/projects/${activeProjectId}/phases/${editingPhase.id}/subtasks`, {
                method: 'POST',
                body: JSON.stringify({ title: title, status: 'pending' })
            });
            
            if (!editingPhase.subtasks) {
                editingPhase.subtasks = [];
            }
            editingPhase.subtasks.push(created);
            
            renderModalSubtasks(editingPhase);
            renderCanvas();
            renderChecklist();
        } catch (err) {
            alert('Erro ao adicionar subtarefa: ' + err.message);
        }
    }

    function createConnectionLocal(fromId, toId) {
        const exists = activeProjectData.connections.some(c => c.from_phase_id === fromId && c.to_phase_id === toId);
        if (!exists) {
            activeProjectData.connections.push({
                from_phase_id: fromId,
                to_phase_id: toId
            });
            saveCanvasStateInBackground();
            drawConnections();
        }
    }

    // --- Document Event Listeners (Drag & Pan & Temp connection drawing) ---
    document.addEventListener('mousemove', (e) => {
        if (isDraggingNode && draggingNode) {
            const dx = (e.clientX - dragStartMouseX) / zoom;
            const dy = (e.clientY - dragStartMouseY) / zoom;
            
            const newX = dragStartNodeX + dx;
            const newY = dragStartNodeY + dy;
            
            draggingNode.style.left = newX + 'px';
            draggingNode.style.top = newY + 'px';
            
            const id = parseInt(draggingNode.getAttribute('data-id'));
            const phase = activeProjectData.phases.find(p => p.id === id);
            if (phase) {
                phase.pos_x = newX;
                phase.pos_y = newY;
            }
            
            drawConnections();
        } else if (isPanning) {
            panX = e.clientX - startPanX;
            panY = e.clientY - startPanY;
            updateCanvasTransform();
        } else if (connectingFromId && tempLine) {
            const mouseCanvas = screenToCanvasCoords(e.clientX, e.clientY);
            tempLine.setAttribute('x2', mouseCanvas.x);
            tempLine.setAttribute('y2', mouseCanvas.y);
        }
    });

    document.addEventListener('mouseup', async (e) => {
        if (isDraggingNode && draggingNode) {
            draggingNode.classList.remove('dragging');
            isDraggingNode = false;
            
            const id = parseInt(draggingNode.getAttribute('data-id'));
            const phase = activeProjectData.phases.find(p => p.id === id);
            if (phase) {
                try {
                    await apiFetch(`/api/projects/${activeProjectId}/phases/${id}`, {
                        method: 'PUT',
                        body: JSON.stringify(phase)
                    });
                } catch (err) {
                    console.error('Erro ao salvar posição:', err);
                }
            }
            draggingNode = null;
        }
        
        isPanning = false;
        if (canvasContainer) {
            canvasContainer.classList.remove('grabbing');
        }
        
        if (connectingFromId) {
            const targetNodeEl = e.target.closest('.canvas-node');
            if (targetNodeEl) {
                const toId = parseInt(targetNodeEl.getAttribute('data-id'));
                if (toId !== connectingFromId) {
                    createConnectionLocal(connectingFromId, toId);
                }
            }
            
            if (tempLine) {
                tempLine.remove();
                tempLine = null;
            }
            connectingFromId = null;
        }
    });

    // Canvas Mouse Wheel & DblClick
    if (canvasContainer) {
        canvasContainer.addEventListener('mousedown', (e) => {
            if (e.target.closest('.canvas-node') || e.target.closest('.btn-toolbar-action') || e.target.closest('.os-modal-card')) {
                return;
            }
            isPanning = true;
            canvasContainer.classList.add('grabbing');
            startPanX = e.clientX - panX;
            startPanY = e.clientY - panY;
        });

        canvasContainer.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = 0.05;
            let newZoom = zoom + (e.deltaY < 0 ? zoomFactor : -zoomFactor);
            newZoom = Math.max(0.3, Math.min(2.0, newZoom));
            
            const rect = canvasContainer.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const localX = (mouseX - panX) / zoom;
            const localY = (mouseY - panY) / zoom;
            
            zoom = newZoom;
            panX = mouseX - localX * zoom;
            panY = mouseY - localY * zoom;
            
            updateCanvasTransform();
        });

        canvasContainer.addEventListener('dblclick', (e) => {
            if (e.target.closest('.canvas-node') || e.target.closest('.btn-toolbar-action')) {
                return;
            }
            const coords = screenToCanvasCoords(e.clientX, e.clientY);
            openPhaseModal(null, coords.x, coords.y);
        });
    }

    // Toolbar buttons
    if (btnCanvasAddNode) {
        btnCanvasAddNode.addEventListener('click', () => {
            const rect = canvasContainer.getBoundingClientRect();
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const coords = screenToCanvasCoords(rect.left + centerX, rect.top + centerY);
            openPhaseModal(null, coords.x, coords.y);
        });
    }
    if (btnCanvasZoomIn) {
        btnCanvasZoomIn.addEventListener('click', () => {
            zoom = Math.min(2.0, zoom + 0.1);
            updateCanvasTransform();
        });
    }
    if (btnCanvasZoomOut) {
        btnCanvasZoomOut.addEventListener('click', () => {
            zoom = Math.max(0.3, zoom - 0.1);
            updateCanvasTransform();
        });
    }
    if (btnCanvasZoomReset) {
        btnCanvasZoomReset.addEventListener('click', () => {
            zoom = 1.0;
            panX = 50;
            panY = 50;
            updateCanvasTransform();
        });
    }
    if (btnCanvasSave) {
        btnCanvasSave.addEventListener('click', () => {
            saveCanvasStateInBackground();
        });
    }

    // Modal Events
    if (btnClosePhaseModal) {
        btnClosePhaseModal.addEventListener('click', () => {
            modalPhaseEdit.style.display = 'none';
        });
    }

    if (phaseEditForm) {
        phaseEditForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = phaseIdInput.value;
            const title = phaseTitleInput.value.trim();
            const description = phaseDescInput.value.trim();
            const status = phaseStatusInput.value;
            const pos_x = parseFloat(phaseEditForm.dataset.x || 100);
            const pos_y = parseFloat(phaseEditForm.dataset.y || 100);

            if (!title) return;

            const payload = { title, description, status, pos_x, pos_y };

            try {
                if (id) {
                    const updated = await apiFetch(`/api/projects/${activeProjectId}/phases/${id}`, {
                        method: 'PUT',
                        body: JSON.stringify(payload)
                    });
                    
                    const idx = activeProjectData.phases.findIndex(p => p.id === parseInt(id));
                    if (idx !== -1) activeProjectData.phases[idx] = updated;
                } else {
                    const created = await apiFetch(`/api/projects/${activeProjectId}/phases`, {
                        method: 'POST',
                        body: JSON.stringify(payload)
                    });
                    
                    activeProjectData.phases.push(created);
                }

                modalPhaseEdit.style.display = 'none';
                renderCanvas();
                renderChecklist();
            } catch (err) {
                alert('Erro ao salvar fase: ' + err.message);
            }
        });
    }

    if (btnDeletePhase) {
        btnDeletePhase.addEventListener('click', async () => {
            const id = phaseIdInput.value;
            if (!id) return;
            if (confirm('Deseja realmente remover esta fase? (Todas as conexões associadas também serão apagadas)')) {
                try {
                    await apiFetch(`/api/projects/${activeProjectId}/phases/${id}`, {
                        method: 'DELETE'
                    });
                    
                    activeProjectData.phases = activeProjectData.phases.filter(p => p.id !== parseInt(id));
                    activeProjectData.connections = activeProjectData.connections.filter(c => c.from_phase_id !== parseInt(id) && c.to_phase_id !== parseInt(id));
                    
                    modalPhaseEdit.style.display = 'none';
                    renderCanvas();
                    renderChecklist();
                } catch (err) {
                    alert('Erro ao remover fase: ' + err.message);
                }
            }
        });
    }

    if (btnAddSubtask) {
        btnAddSubtask.addEventListener('click', (e) => {
            e.preventDefault();
            handleAddSubtask();
        });
    }

    if (newSubtaskTitle) {
        newSubtaskTitle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleAddSubtask();
            }
        });
    }

    // Projects list Sidebar and Forms
    if (projectCreationForm) {
        projectCreationForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const name = projectNameInput.value.trim();
            const description = projectDescInput.value.trim();
            
            if (!name) return;
            
            btnSubmitProject.disabled = true;
            projectCreationStatus.innerHTML = '';
            
            try {
                const created = await apiFetch('/api/projects', {
                    method: 'POST',
                    body: JSON.stringify({ name, description })
                });
                
                projectCreationStatus.innerHTML = `
                    <div class="status-message status-success">
                        ✅ Aplicativo <strong>${escapeHtml(name)}</strong> criado com sucesso!
                    </div>
                `;
                projectCreationForm.reset();
                await loadProjects();
                
                selectProject(created.id);
                
                setTimeout(() => { projectCreationStatus.innerHTML = ''; }, 5000);
            } catch (err) {
                projectCreationStatus.innerHTML = `<div class="status-message status-error">❌ ${escapeHtml(err.message)}</div>`;
            } finally {
                btnSubmitProject.disabled = false;
            }
        });
    }

    if (btnDeleteProject) {
        btnDeleteProject.addEventListener('click', async () => {
            if (!activeProjectId) return;
            if (confirm('Deseja realmente remover este aplicativo e todo o seu fluxo de desenvolvimento do Orquestrador?')) {
                try {
                    await apiFetch(`/api/projects/${activeProjectId}`, { method: 'DELETE' });
                    activeProjectId = null;
                    activeProjectData = null;
                    
                    panelManageProject.style.display = 'none';
                    panelCreateProject.style.display = 'none';
                    panelEmptyProject.style.display = 'flex';
                    
                    await loadProjects();
                } catch (err) {
                    alert('Erro ao excluir projeto: ' + err.message);
                }
            }
        });
    }

    if (btnShowCreateProject) {
        btnShowCreateProject.addEventListener('click', () => {
            activeProjectId = null;
            document.querySelectorAll('.project-item').forEach(item => item.classList.remove('active'));
            panelEmptyProject.style.display = 'none';
            panelManageProject.style.display = 'none';
            panelCreateProject.style.display = 'flex';
            projectCreationForm.reset();
            projectCreationStatus.innerHTML = '';
        });
    }

    // Tabs navigation
    if (tabCanvas) {
        tabCanvas.addEventListener('click', () => {
            tabCanvas.classList.add('active');
            tabChecklist.classList.remove('active');
            tabContentCanvas.style.display = 'flex';
            tabContentChecklist.style.display = 'none';
            renderCanvas();
        });
    }

    if (tabChecklist) {
        tabChecklist.addEventListener('click', () => {
            tabCanvas.classList.remove('active');
            tabChecklist.classList.add('active');
            tabContentCanvas.style.display = 'none';
            tabContentChecklist.style.display = 'flex';
            renderChecklist();
        });
    }

    // Close modails clicking outside card
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('os-modal-overlay')) {
            e.target.style.display = 'none';
        }
    });

    // ============================================================
    // Lógica de Integração do Módulo Mentes Clones com Anthropic
    // ============================================================
    const btnBuildBlueprintAction = document.getElementById('btn-build-blueprint-action');
    const btnConversarBrainAction = document.getElementById('btn-conversar-brain-action');

    if (btnBuildBlueprintAction) {
        btnBuildBlueprintAction.addEventListener('click', async () => {
            if (!currentActiveClone) return;
            const cloneId = currentActiveClone.id;
            
            btnBuildBlueprintAction.disabled = true;
            btnBuildBlueprintAction.innerHTML = '<span class="spinner"></span> Processando...';
            chatTitleStatus.textContent = 'Gerando Blueprint...';
            
            try {
                const res = await apiFetch(`/api/clones/${cloneId}/build_blueprint`, { method: 'POST' });
                alert('Blueprint de modelo mental gerado e salvo no Obsidian com sucesso! ✓');
                await loadClones();
                
                // Recarrega o clone atualizado
                const clones = await apiFetch('/api/clones');
                const updated = clones.find(c => c.id === cloneId);
                if (updated) {
                    selectClone(updated);
                }
            } catch (err) {
                alert('Erro ao gerar blueprint: ' + err.message);
                chatTitleStatus.textContent = 'Falhou';
            } finally {
                btnBuildBlueprintAction.disabled = false;
                btnBuildBlueprintAction.innerHTML = '<span class="material-symbols-outlined">construction</span> Gerar Blueprint';
            }
        });
    }

    if (btnConversarBrainAction) {
        btnConversarBrainAction.addEventListener('click', async () => {
            if (!currentActiveClone) return;
            const cloneId = currentActiveClone.id;
            const cloneName = currentActiveClone.name;
            
            // 1. Alterna para o Módulo Segundo Cérebro
            switchModule(navBrain, moduleBrain);
            
            // 2. Garante que carrega e exibe a subtab de Chat (RAG)
            const tabBrainChat = document.getElementById('subtab-brain-chat');
            if (tabBrainChat) {
                tabBrainChat.click();
            }
            
            // 3. Cria uma sessão de chat configurada para conversar apenas com essa persona (clone_only)
            try {
                const session = await apiFetch('/api/brain/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({
                        title: `Conversa com ${cloneName}`,
                        persona_id: cloneId,
                        is_clone_only: true
                    })
                });
                
                await initBrainModule();
                
                // Alterna a subtab ativa para Chat e seleciona a nova sessão
                if (tabBrainChat) tabBrainChat.click();
                selectBrainSession(session.id);
                
            } catch (err) {
                console.error("Erro ao iniciar conversa com clone:", err);
                alert("Erro ao iniciar chat: " + err.message);
            }
        });
    }


    // ============================================================
    // Lógica do Módulo Segundo Cérebro
    // ============================================================
    let activeBrainSessionId = null;
    let isSendingBrainMessage = false;

    // Elementos DOM do Segundo Cérebro
    const btnSidebarNewChat = document.getElementById('btn-sidebar-new-chat');
    const sessionsList = document.getElementById('sessions-list');
    const panelEmptyBrain = document.getElementById('panel-empty-brain');
    const panelChatBrain = document.getElementById('panel-chat-brain');
    const brainPersonaSelect = document.getElementById('brain-persona-select');
    const brainChatMessagesList = document.getElementById('brain-chat-messages-list');
    const brainChatSendForm = document.getElementById('brain-chat-send-form');
    const brainChatUserInput = document.getElementById('brain-chat-user-input');
    const btnBrainChatSend = document.getElementById('btn-brain-chat-send');
    const brainSourcesInspector = document.getElementById('brain-sources-inspector');
    const btnCloseSources = document.getElementById('btn-close-sources');
    const sourcesListContainer = document.getElementById('sources-list-container');

    // Síntese
    const synthesisEmptyState = document.getElementById('synthesis-empty-state');
    const btnGenerateSynthesisInitial = document.getElementById('btn-generate-synthesis-initial');
    const synthesisCardWrapper = document.getElementById('synthesis-card-wrapper');
    const synthesisGeneratedAt = document.getElementById('synthesis-generated-at');
    const synthesisVaultSize = document.getElementById('synthesis-vault-size');
    const synthesisContentView = document.getElementById('synthesis-content-view');
    const btnUpdateSynthesis = document.getElementById('btn-update-synthesis');

    // Modais
    const modalSynthesisConfirm = document.getElementById('modal-synthesis-confirm');
    const btnCloseSynthesisModal = document.getElementById('btn-close-synthesis-modal');
    const btnCancelSynthesis = document.getElementById('btn-cancel-synthesis');
    const btnConfirmSynthesis = document.getElementById('btn-confirm-synthesis');
    const synthesisEstimateNotes = document.getElementById('synthesis-estimate-notes');
    const synthesisEstimateTokens = document.getElementById('synthesis-estimate-tokens');
    const synthesisEstimateCost = document.getElementById('synthesis-estimate-cost');

    // Subtabs Segundo Cérebro
    const brainSubtabs = ['synthesis', 'brain-chat'];
    brainSubtabs.forEach(tab => {
        const btn = document.getElementById(`subtab-${tab}`);
        if (btn) {
            btn.addEventListener('click', () => {
                brainSubtabs.forEach(t => {
                    const el = document.getElementById(`subtab-${t}`);
                    if (el) el.classList.remove('active');
                    const cont = document.getElementById(`subcontent-${t}`);
                    if (cont) cont.style.display = 'none';
                });
                btn.classList.add('active');
                const targetContent = document.getElementById(`subcontent-${tab}`);
                if (targetContent) targetContent.style.display = 'block';

                if (tab === 'synthesis') loadSynthesisTab();
                if (tab === 'brain-chat') loadBrainChatTab();
            });
        }
    });

    // Inicializa o Módulo Brain
    async function initBrainModule() {
        // Carrega o uso do sistema (custos e chamadas)
        updateSystemUsage();
        
        // Ativa a aba padrão (Síntese)
        const tabSynthesis = document.getElementById('subtab-synthesis');
        if (tabSynthesis) tabSynthesis.click();
    }

    // Carrega aba Síntese
    async function loadSynthesisTab() {
        try {
            const data = await apiFetch('/api/brain/synthesize');
            synthesisEmptyState.style.display = 'none';
            synthesisCardWrapper.style.display = 'block';
            
            synthesisGeneratedAt.textContent = formatDateTime(data.generated_at);
            synthesisVaultSize.textContent = data.vault_size;
            synthesisContentView.innerHTML = parseMarkdown(data.synthesis);
        } catch (err) {
            // Nota não existe
            synthesisEmptyState.style.display = 'block';
            synthesisCardWrapper.style.display = 'none';
        }
    }

    // Modal de Confirmação da Síntese
    async function openSynthesisConfirmModal() {
        try {
            // Estimativa
            const estimate = await apiFetch('/api/brain/synthesize/estimate');
            synthesisEstimateNotes.textContent = estimate.total_notes;
            synthesisEstimateTokens.textContent = estimate.estimated_tokens.toLocaleString();
            synthesisEstimateCost.textContent = `$${estimate.estimated_cost_usd.toFixed(4)}`;
            
            modalSynthesisConfirm.style.display = 'flex';
        } catch (err) {
            alert("Erro ao obter estimativa de custo: " + err.message);
        }
    }

    if (btnGenerateSynthesisInitial) {
        btnGenerateSynthesisInitial.addEventListener('click', openSynthesisConfirmModal);
    }
    if (btnUpdateSynthesis) {
        btnUpdateSynthesis.addEventListener('click', openSynthesisConfirmModal);
    }
    if (btnCloseSynthesisModal) {
        btnCloseSynthesisModal.addEventListener('click', () => { modalSynthesisConfirm.style.display = 'none'; });
    }
    if (btnCancelSynthesis) {
        btnCancelSynthesis.addEventListener('click', () => { modalSynthesisConfirm.style.display = 'none'; });
    }

    if (btnConfirmSynthesis) {
        btnConfirmSynthesis.addEventListener('click', async () => {
            modalSynthesisConfirm.style.display = 'none';
            
            // Loading State no container
            synthesisEmptyState.style.display = 'none';
            synthesisCardWrapper.style.display = 'block';
            synthesisGeneratedAt.textContent = "Atualizando...";
            synthesisVaultSize.textContent = "Calculando...";
            synthesisContentView.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--accent);">
                    <div class="spinner" style="margin: 0 auto 16px auto; width: 32px; height: 32px;"></div>
                    <span>Sintetizando todo o vault do Obsidian via Claude 3.5 Sonnet...</span><br>
                    <small style="color: var(--text-muted);">Esse processo pode demorar entre 30 e 60 segundos.</small>
                </div>
            `;
            
            if (btnUpdateSynthesis) btnUpdateSynthesis.disabled = true;

            try {
                const res = await apiFetch('/api/brain/synthesize', { method: 'POST' });
                alert("Síntese gerada e salva com sucesso em seu Obsidian vault! ✓");
                await loadSynthesisTab();
                await updateSystemUsage();
            } catch (err) {
                alert("Falha ao gerar síntese: " + err.message);
                synthesisEmptyState.style.display = 'block';
                synthesisCardWrapper.style.display = 'none';
            } finally {
                if (btnUpdateSynthesis) btnUpdateSynthesis.disabled = false;
            }
        });
    }

    // Carrega aba Chat
    async function loadBrainChatTab() {
        await loadPersonaSelector();
        await loadBrainSessions();
    }

    // Carrega dropdown de personas (clones)
    async function loadPersonaSelector() {
        try {
            const clones = await apiFetch('/api/clones');
            const completedClones = clones.filter(c => c.status === 'completed');
            
            // Mantém "Neutro" e adiciona os prontos
            brainPersonaSelect.innerHTML = '<option value="">Oyto Brain (Neutro)</option>' + 
                completedClones.map(c => `<option value="${c.id}">Clone: ${escapeHtml(c.name)}</option>`).join('');
        } catch (err) {
            console.error("Erro ao carregar personas para selector:", err);
        }
    }

    // Carrega sessões de chat do Segundo Cérebro
    async function loadBrainSessions() {
        try {
            const sessions = await apiFetch('/api/brain/chat/sessions');
            renderBrainSessions(sessions);
        } catch (err) {
            console.error("Erro ao carregar sessões de chat:", err);
        }
    }

    function renderBrainSessions(sessions) {
        if (sessions.length === 0) {
            sessionsList.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 20px; font-size: 0.8rem;">
                    Nenhuma conversa recente.
                </div>
            `;
            return;
        }

        sessionsList.innerHTML = sessions.map(s => {
            const isActive = activeBrainSessionId === s.id;
            return `
                <div class="session-item ${isActive ? 'active' : ''}" data-id="${s.id}">
                    <div class="session-item-title">${escapeHtml(s.title)}</div>
                    <button class="btn-delete-session" data-id="${s.id}">
                        <span class="material-symbols-outlined" style="font-size: 1.1rem;">delete</span>
                    </button>
                </div>
            `;
        }).join('');

        // Clicks
        document.querySelectorAll('.session-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.btn-delete-session')) return;
                const id = parseInt(item.getAttribute('data-id'));
                selectBrainSession(id);
            });
        });

        // Deletar
        document.querySelectorAll('.btn-delete-session').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = parseInt(btn.getAttribute('data-id'));
                if (confirm('Deseja apagar permanentemente esta conversa?')) {
                    try {
                        await apiFetch(`/api/brain/chat/sessions/${id}`, { method: 'DELETE' });
                        if (activeBrainSessionId === id) {
                            activeBrainSessionId = null;
                            panelChatBrain.style.display = 'none';
                            panelEmptyBrain.style.display = 'flex';
                        }
                        await loadBrainSessions();
                    } catch (err) {
                        alert("Erro ao excluir conversa: " + err.message);
                    }
                }
            });
        });
    }

    // Criar nova sessão
    if (btnSidebarNewChat) {
        btnSidebarNewChat.addEventListener('click', async () => {
            try {
                const session = await apiFetch('/api/brain/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({
                        title: "Nova Conversa",
                        persona_id: brainPersonaSelect.value ? parseInt(brainPersonaSelect.value) : null,
                        is_clone_only: false
                    })
                });
                activeBrainSessionId = session.id;
                await loadBrainSessions();
                selectBrainSession(session.id);
            } catch (err) {
                alert("Erro ao criar conversa: " + err.message);
            }
        });
    }

    // Selecionar sessão de chat
    async function selectBrainSession(id) {
        activeBrainSessionId = id;
        
        // Highlight na sidebar
        document.querySelectorAll('.session-item').forEach(item => {
            if (parseInt(item.getAttribute('data-id')) === id) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });

        panelEmptyBrain.style.display = 'none';
        panelChatBrain.style.display = 'flex';
        brainSourcesInspector.classList.remove('visible'); // esconde inspetor por padrão
        
        // Carrega histórico
        brainChatMessagesList.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Carregando histórico...</div>';
        
        try {
            const messages = await apiFetch(`/api/brain/chat/sessions/${id}/messages`);
            
            // Sincroniza dropdown de persona da sessão no banco
            const sessions = await apiFetch('/api/brain/chat/sessions');
            const current = sessions.find(s => s.id === id);
            if (current) {
                brainPersonaSelect.value = current.persona_id ? current.persona_id.toString() : '';
            }

            renderBrainMessages(messages);
        } catch (err) {
            brainChatMessagesList.innerHTML = `<div style="text-align: center; color: var(--error); padding: 20px;">Erro: ${escapeHtml(err.message)}</div>`;
        }
    }

    // Seletor de persona no cabeçalho do chat do Segundo Cérebro
    if (brainPersonaSelect) {
        brainPersonaSelect.addEventListener('change', async () => {
            if (!activeBrainSessionId) return;
            const personaId = brainPersonaSelect.value ? parseInt(brainPersonaSelect.value) : null;
            
            // Atualiza no banco
            try {
                const selectedText = brainPersonaSelect.options[brainPersonaSelect.selectedIndex].text;
                alert(`Persona alterada para: ${selectedText}. As próximas perguntas usarão esta persona.`);
                
                await apiFetch('/api/brain/chat/sessions', {
                    method: 'POST',
                    body: JSON.stringify({
                        title: `Conversa com ${selectedText.replace('Clone: ', '')}`,
                        persona_id: personaId,
                        is_clone_only: false
                    })
                }).then(session => {
                    activeBrainSessionId = session.id;
                    loadBrainSessions().then(() => {
                        selectBrainSession(session.id);
                    });
                });
            } catch (err) {
                console.error("Erro ao alternar persona:", err);
            }
        });
    }

    function renderBrainMessages(messages) {
        if (messages.length === 0) {
            brainChatMessagesList.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 40px 20px; font-size: 0.9rem;">
                    💡 Faça uma pergunta sobre qualquer conteúdo importado! O RAG recuperará as notas e responderá referenciando as fontes.
                </div>
            `;
            return;
        }

        brainChatMessagesList.innerHTML = messages.map(msg => {
            const isUser = msg.role === 'user';
            const senderName = isUser ? 'Você' : 'Oyto Brain';
            
            // Botão de fontes se houver
            let sourcesMarkup = '';
            if (!isUser && msg.sources && msg.sources.length > 0) {
                const sourcesJsonEscaped = escapeHtml(JSON.stringify(msg.sources));
                sourcesMarkup = `
                    <div class="chat-msg-sources-bar">
                        <button class="btn-msg-inspect-sources" onclick="inspectMessageSources(this)" data-sources="${sourcesJsonEscaped}">
                            <span class="material-symbols-outlined" style="font-size: 1rem;">menu_book</span>
                            <span>Ver Fontes (${msg.sources.length})</span>
                        </button>
                    </div>
                `;
            }

            return `
                <div class="chat-msg-row ${isUser ? 'user' : 'assistant'}">
                    <span class="chat-msg-header">${senderName}</span>
                    <div class="chat-msg-body">${parseMarkdown(msg.content)}</div>
                    ${sourcesMarkup}
                </div>
            `;
        }).join('');

        brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;
    }

    // Função de clique global para inspecionar fontes
    window.inspectMessageSources = function(button) {
        const sourcesDataRaw = button.getAttribute('data-sources');
        const sources = JSON.parse(sourcesDataRaw);
        
        sourcesListContainer.innerHTML = sources.map(s => {
            const nameWithoutExt = s.title;
            const fileParam = encodeURIComponent(s.file_path);
            const obsidianUri = `obsidian://open?file=${fileParam}`;

            return `
                <div class="source-item">
                    <div class="source-item-title">${escapeHtml(nameWithoutExt)}</div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); word-break: break-all;">${escapeHtml(s.file_path)}</div>
                    <div class="source-item-score">
                        <span>Similaridade: ${(s.similarity_score * 100).toFixed(1)}%</span>
                        <a href="${obsidianUri}" style="color: var(--accent); text-decoration: underline;">Abrir no Obsidian ↗</a>
                    </div>
                </div>
            `;
        }).join('');
        
        brainSourcesInspector.classList.add('visible');
    };

    if (btnCloseSources) {
        btnCloseSources.addEventListener('click', () => {
            brainSourcesInspector.classList.remove('visible');
        });
    }

    // Enviar Mensagem via streaming (SSE / EventSource manual com Fetch)
    if (brainChatSendForm) {
        brainChatSendForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!activeBrainSessionId || isSendingBrainMessage) return;

            const text = brainChatUserInput.value.trim();
            if (!text) return;

            brainChatUserInput.value = '';
            isSendingBrainMessage = true;
            btnBrainChatSend.disabled = true;

            // 1. Renderiza mensagem do usuário localmente
            const userMsgHtml = `
                <div class="chat-msg-row user">
                    <span class="chat-msg-header">Você</span>
                    <div class="chat-msg-body">${escapeHtml(text)}</div>
                </div>
            `;
            if (brainChatMessagesList.querySelector('div[style*="text-align"]')) {
                brainChatMessagesList.innerHTML = '';
            }
            brainChatMessagesList.insertAdjacentHTML('beforeend', userMsgHtml);
            brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;

            // 2. Renderiza indicador de pesquisa (RAG)
            const indicatorId = 'chat-rag-indicator';
            const indicatorHtml = `
                <div class="chat-searching-indicator" id="${indicatorId}">
                    <span class="spinner" style="width: 14px; height: 14px;"></span>
                    <span>🔎 Consultando notas no seu vault do Obsidian...</span>
                </div>
            `;
            brainChatMessagesList.insertAdjacentHTML('beforeend', indicatorHtml);
            brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;

            // 3. Renderiza container para a resposta que vai chegar por stream
            const assistantId = 'brain-assistant-stream-' + Date.now();
            const assistantMsgHtml = `
                <div class="chat-msg-row assistant" id="${assistantId}" style="display: none;">
                    <span class="chat-msg-header">Oyto Brain</span>
                    <div class="chat-msg-body"></div>
                </div>
            `;
            brainChatMessagesList.insertAdjacentHTML('beforeend', assistantMsgHtml);
            const assistantEl = document.getElementById(assistantId);
            const assistantBody = assistantEl.querySelector('.chat-msg-body');

            let answerAccumulator = "";

            try {
                // 4. Executa requisição POST para obter stream SSE
                const response = await fetch(`/api/brain/chat/sessions/${activeBrainSessionId}/messages`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: text })
                });

                if (!response.ok) {
                    throw new Error("Erro na comunicação com a IA.");
                }

                // Remove indicador de pesquisa
                const indicatorEl = document.getElementById(indicatorId);
                if (indicatorEl) indicatorEl.remove();

                // Mostra container da resposta
                assistantEl.style.display = 'flex';

                // Lógica de leitura do Stream
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Mantém o que estiver incompleto

                    for (const line of lines) {
                        const trimmedLine = line.trim();
                        if (trimmedLine.startsWith('data: ')) {
                            const dataStr = trimmedLine.slice(6).trim();
                            if (dataStr) {
                                try {
                                    const event = JSON.parse(dataStr);
                                    
                                    if (event.status === 'searching') {
                                        // Apenas sinaliza busca ativa
                                    } else if (event.token) {
                                        // Delta de token recebido
                                        answerAccumulator += event.token;
                                        // Renderiza markdown em tempo real
                                        assistantBody.innerHTML = parseMarkdown(answerAccumulator);
                                        brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;
                                    } else if (event.message_id) {
                                        // Final da geração
                                        // Exibe botão de fontes se houver
                                        if (event.sources && event.sources.length > 0) {
                                            const sourcesJsonEscaped = escapeHtml(JSON.stringify(event.sources));
                                            const sourcesBar = `
                                                <div class="chat-msg-sources-bar">
                                                    <button class="btn-msg-inspect-sources" onclick="inspectMessageSources(this)" data-sources="${sourcesJsonEscaped}">
                                                        <span class="material-symbols-outlined" style="font-size: 1rem;">menu_book</span>
                                                        <span>Ver Fontes (${event.sources.length})</span>
                                                    </button>
                                                </div>
                                            `;
                                            assistantEl.insertAdjacentHTML('beforeend', sourcesBar);
                                            brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;
                                        }
                                        
                                        // Atualiza estatísticas na barra lateral
                                        await updateSystemUsage();
                                        await loadBrainSessions();
                                    }
                                } catch (e) {
                                    console.error("Erro no parse do JSON SSE:", e);
                                }
                            }
                        }
                    }
                }

            } catch (err) {
                // Remove indicador de pesquisa
                const indicatorEl = document.getElementById(indicatorId);
                if (indicatorEl) indicatorEl.remove();

                assistantEl.style.display = 'flex';
                assistantBody.innerHTML = `<span style="color: var(--error);">❌ Falha na resposta: ${escapeHtml(err.message)}</span>`;
                brainChatMessagesList.scrollTop = brainChatMessagesList.scrollHeight;
            } finally {
                isSendingBrainMessage = false;
                btnBrainChatSend.disabled = false;
            }
        });
    }

    // Atualiza custos na barra lateral
    async function updateSystemUsage() {
        try {
            const usage = await apiFetch('/api/system/usage');
            document.getElementById('usage-calls').textContent = usage.total_calls;
            document.getElementById('usage-tokens').textContent = usage.total_input_tokens + usage.total_output_tokens;
            document.getElementById('usage-cost').textContent = `$${usage.total_cost_usd.toFixed(4)}`;
        } catch (err) {
            console.error("Erro ao carregar custos do sistema:", err);
        }
    }

    // Inicializa carregamento do custo ao abrir a página
    updateSystemUsage();

})();


