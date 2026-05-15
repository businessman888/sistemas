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
})();
