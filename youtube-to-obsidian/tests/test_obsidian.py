"""Testes para o serviço do Obsidian: geração de markdown e gerenciamento de arquivos."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.video import TranscriptResult, TranscriptSegment, VideoMetadata
from app.modules.youtube.obsidian import (
    _build_markdown,
    _group_transcript_blocks,
    check_existing_video,
    list_imported_videos,
    save_video_markdown,
)
from app.core.utils.slugify import slugify, slugify_tag
from app.core.utils.timestamp import seconds_to_timestamp, timestamp_to_seconds


# --- Fixtures ---

@pytest.fixture
def sample_metadata():
    return VideoMetadata(
        video_id="abc123XYZ",
        title="Como Construir um Segundo Cérebro",
        channel="Nome do Canal",
        channel_url="https://www.youtube.com/@canal",
        upload_date="20240812",
        duration=754,
        description="Descrição do vídeo\nCom múltiplas linhas",
        thumbnail="https://i.ytimg.com/vi/abc123XYZ/maxresdefault.jpg",
    )


@pytest.fixture
def sample_transcript():
    segments = [
        TranscriptSegment(text="Olá, bem-vindos ao canal.", start=0.0, duration=5.0),
        TranscriptSegment(text="Hoje vamos falar sobre", start=5.0, duration=4.0),
        TranscriptSegment(text="como construir um segundo cérebro.", start=9.0, duration=6.0),
        TranscriptSegment(text="Primeiro, vamos entender o conceito.", start=15.0, duration=5.0),
        TranscriptSegment(text="Um segundo cérebro é um sistema", start=20.0, duration=4.0),
        TranscriptSegment(text="de organização de conhecimento.", start=24.0, duration=5.0),
        TranscriptSegment(text="Agora, no próximo bloco...", start=31.0, duration=4.0),
        TranscriptSegment(text="Vamos ver como aplicar.", start=35.0, duration=3.0),
    ]
    return TranscriptResult(segments=segments, language="pt")


# --- Tests: Slugify ---

class TestSlugify:

    def test_basic(self):
        assert slugify("Como Construir um Segundo Cérebro") == "Como Construir um Segundo Cérebro"

    def test_removes_forbidden_chars(self):
        result = slugify('Título: "Com Aspas" e <Sinais>')
        assert '"' not in result
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

    def test_max_length(self):
        long_title = "A" * 200
        assert len(slugify(long_title, max_length=100)) <= 100


class TestSlugifyTag:

    def test_basic(self):
        assert slugify_tag("Nome do Canal") == "nome-do-canal"

    def test_with_accents(self):
        assert slugify_tag("Café com Código") == "cafe-com-codigo"


# --- Tests: Timestamp ---

class TestTimestamp:

    def test_seconds_to_short(self):
        assert seconds_to_timestamp(90) == "01:30"

    def test_seconds_to_long(self):
        assert seconds_to_timestamp(3661) == "1:01:01"

    def test_timestamp_to_seconds_short(self):
        assert timestamp_to_seconds("01:30") == 90

    def test_timestamp_to_seconds_long(self):
        assert timestamp_to_seconds("1:01:01") == 3661


# --- Tests: Transcript Grouping ---

class TestGroupTranscriptBlocks:

    def test_groups_into_30s_blocks(self, sample_transcript):
        blocks = _group_transcript_blocks(sample_transcript, "abc123XYZ")
        # Should have headers with timestamps
        headers = [b for b in blocks if b.startswith("### [")]
        assert len(headers) >= 2

    def test_first_block_starts_at_zero(self, sample_transcript):
        blocks = _group_transcript_blocks(sample_transcript, "abc123XYZ")
        assert blocks[0].startswith("### [00:00]")

    def test_contains_deep_links(self, sample_transcript):
        blocks = _group_transcript_blocks(sample_transcript, "abc123XYZ")
        assert any("&t=0s" in b for b in blocks)


# --- Tests: Markdown Generation ---

class TestBuildMarkdown:

    def test_contains_frontmatter(self, sample_metadata, sample_transcript):
        now = datetime(2026, 5, 15, 14, 32, 11)
        md = _build_markdown(sample_metadata, sample_transcript, now)

        assert md.startswith("---\n")
        assert 'video_id: "abc123XYZ"' in md
        assert 'title: "Como Construir um Segundo Cérebro"' in md
        assert "source: youtube" in md
        assert "status: imported" in md

    def test_contains_transcript_section(self, sample_metadata, sample_transcript):
        now = datetime(2026, 5, 15, 14, 32, 11)
        md = _build_markdown(sample_metadata, sample_transcript, now)

        assert "## 📜 Transcrição" in md
        assert "Olá, bem-vindos ao canal." in md

    def test_contains_description(self, sample_metadata, sample_transcript):
        now = datetime(2026, 5, 15, 14, 32, 11)
        md = _build_markdown(sample_metadata, sample_transcript, now)

        assert "## 💬 Descrição Original" in md
        assert "> Descrição do vídeo" in md

    def test_contains_placeholder_sections(self, sample_metadata, sample_transcript):
        now = datetime(2026, 5, 15, 14, 32, 11)
        md = _build_markdown(sample_metadata, sample_transcript, now)

        assert "## 📝 Resumo" in md
        assert "## 🔑 Pontos-Chave" in md
        assert "## 🗒️ Notas Pessoais" in md

    def test_contains_channel_tag(self, sample_metadata, sample_transcript):
        now = datetime(2026, 5, 15, 14, 32, 11)
        md = _build_markdown(sample_metadata, sample_transcript, now)

        assert "canal/nome-do-canal" in md


# --- Tests: File Operations ---

class TestCheckExistingVideo:

    def test_finds_existing(self, sample_metadata, sample_transcript):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.modules.youtube.obsidian.settings") as mock_settings:
                mock_settings.youtube_output_dir = Path(tmpdir)

                # Write a file with known video_id in frontmatter
                test_file = Path(tmpdir) / "test.md"
                test_file.write_text(
                    '---\nvideo_id: "abc123XYZ"\ntitle: "Test"\n---\n# Test\n',
                    encoding="utf-8",
                )

                result = check_existing_video("abc123XYZ")
                assert result is not None
                assert "abc123XYZ" in Path(result).read_text(encoding="utf-8")

    def test_returns_none_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.modules.youtube.obsidian.settings") as mock_settings:
                mock_settings.youtube_output_dir = Path(tmpdir)

                result = check_existing_video("nonexistent")
                assert result is None


class TestSaveVideoMarkdown:

    def test_creates_file(self, sample_metadata, sample_transcript):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.modules.youtube.obsidian.settings") as mock_settings:
                mock_settings.youtube_output_dir = Path(tmpdir)

                path = save_video_markdown(sample_metadata, sample_transcript)

                assert Path(path).exists()
                content = Path(path).read_text(encoding="utf-8")
                assert 'video_id: "abc123XYZ"' in content

    def test_filename_format(self, sample_metadata, sample_transcript):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.modules.youtube.obsidian.settings") as mock_settings:
                mock_settings.youtube_output_dir = Path(tmpdir)

                path = save_video_markdown(sample_metadata, sample_transcript)

                filename = Path(path).name
                assert filename.startswith("2024-08-12 - ")
                assert filename.endswith(".md")
