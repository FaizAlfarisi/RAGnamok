"""Unit tests for seed_demo parser utilities — pure functions, no infra needed."""

from pathlib import Path

from scripts.seed_demo import _unescape, parse_copy_line, parse_dump


# ---------------------------------------------------------------------------
# _unescape
# ---------------------------------------------------------------------------


class TestUnescape:
    def test_plain_text_passthrough(self):
        assert _unescape("hello") == "hello"

    def test_null_field(self):
        assert _unescape(r"\N") is None

    def test_newline(self):
        val = _unescape("line1\\nline2")
        assert val == "line1\nline2"

    def test_tab(self):
        val = _unescape("col1\\tcol2")
        assert val == "col1\tcol2"

    def test_backslash(self):
        val = _unescape("path\\\\to\\\\file")
        assert val == "path\\to\\file"

    def test_carriage_return(self):
        val = _unescape("line1\\rline2")
        assert val == "line1\rline2"

    def test_mixed_escapes(self):
        val = _unescape("a\\tb\\nc\\\\d")
        assert val == "a\tb\nc\\d"

    def test_empty_string(self):
        assert _unescape("") == ""

    def test_only_backslash_n(self):
        assert _unescape("\\N") is None


# ---------------------------------------------------------------------------
# parse_copy_line
# ---------------------------------------------------------------------------


class TestParseCopyLine:
    def test_simple_fields(self):
        fields = parse_copy_line("a\tb\tc")
        assert fields == ["a", "b", "c"]

    def test_single_field(self):
        fields = parse_copy_line("justone")
        assert fields == ["justone"]

    def test_empty_field(self):
        fields = parse_copy_line("a\t\tc")
        assert fields == ["a", "", "c"]

    def test_with_null(self):
        fields = parse_copy_line("a\t\\N\tc")
        assert fields == ["a", None, "c"]

    def test_with_escaped_tab(self):
        line = "a\\tb" + "\t" + "c"
        fields = parse_copy_line(line)
        assert fields == ["a\tb", "c"]

    def test_with_escaped_newline(self):
        line = "hello\\nworld\tnext"
        fields = parse_copy_line(line)
        assert fields == ["hello\nworld", "next"]

    def test_leading_trailing_tabs(self):
        fields = parse_copy_line("\ta\t")
        assert fields == ["", "a", ""]


# ---------------------------------------------------------------------------
# parse_dump
# ---------------------------------------------------------------------------


class TestParseDump:
    def test_single_table(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "COPY public.documents (id, filename) FROM stdin;\n"
            "doc-1\ttest.pdf\n"
            "doc-2\tdata.pdf\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        assert len(sections) == 1
        assert sections[0]["table"] == "documents"
        assert sections[0]["columns"] == ["id", "filename"]
        assert sections[0]["rows"] == [["doc-1", "test.pdf"], ["doc-2", "data.pdf"]]

    def test_multiple_tables(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "COPY public.documents (id, filename) FROM stdin;\n"
            "d1\tf1.pdf\n"
            "\\.\n"
            "COPY public.tasks (id, task_name) FROM stdin;\n"
            "t1\tindex\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        assert len(sections) == 2
        assert sections[0]["table"] == "documents"
        assert sections[1]["table"] == "tasks"

    def test_empty_table(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "COPY public.empty_table (id) FROM stdin;\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        assert len(sections) == 1
        assert sections[0]["rows"] == []

    def test_handles_escaped_data_in_dump(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "COPY public.chunk_summaries (id, summary_text, embedding) FROM stdin;\n"
            "c1\tsome\\nsummary\\ttext\t[0.1,0.2]\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        row = sections[0]["rows"][0]
        assert row[0] == "c1"
        assert row[1] == "some\nsummary\ttext"
        assert row[2] == "[0.1,0.2]"

    def test_no_copy_statements(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text("-- just a comment\nSELECT 1;\n")
        sections = parse_dump(str(dump))
        assert sections == []

    def test_ignores_non_copy_lines(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "-- schema header\n"
            "SET statement_timeout = 0;\n"
            "COPY public.foo (id) FROM stdin;\n"
            "42\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        assert len(sections) == 1
        assert sections[0]["rows"] == [["42"]]

    def test_newline_in_data(self, tmp_path: Path):
        dump = tmp_path / "dump.sql"
        dump.write_text(
            "COPY public.foo (col1) FROM stdin;\n"
            "multi\\nline\n"
            "\\.\n"
        )
        sections = parse_dump(str(dump))
        assert sections[0]["rows"][0][0] == "multi\nline"
