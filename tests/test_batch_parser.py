import pytest

from debate_ai.batch import BatchInputError, Entry, parse_motions, read_motions_file


def test_single_motions_pairs_blanks_and_comments():
    entries = parse_motions(
        "# Pets: a pair\n"
        "Cats are better | Dogs are better\n"
        "\n"
        "   \n"
        "Remote work is better\n"
        "  # an indented comment\n"
        "Second pair A|Second pair B\n"
    )
    assert entries == [
        Entry("Cats are better", pair=0, side="A"),
        Entry("Dogs are better", pair=0, side="B"),
        Entry("Remote work is better"),
        Entry("Second pair A", pair=1, side="A"),
        Entry("Second pair B", pair=1, side="B"),
    ]


def test_motions_are_trimmed_and_duplicates_are_kept():
    entries = parse_motions("  Same motion  \nSame motion\n")
    assert [e.motion for e in entries] == ["Same motion", "Same motion"]


@pytest.mark.parametrize("text,line", [
    ("ok\nA | B | C\n", 2),
    ("\n\nA || B\n", 3),
    ("fine\nA |\n", 2),
    ("| B\n", 1),
    ("fine\n|\n", 2),
    ("fine\nA |   \n", 2),
])
def test_malformed_lines_are_rejected_with_their_line_number(text, line):
    with pytest.raises(BatchInputError, match=rf"^Line {line}:"):
        parse_motions(text)


@pytest.mark.parametrize("text", ["", "   \n\n", "# only a comment\n# another\n\n"])
def test_a_file_with_no_usable_motions_is_rejected(text):
    with pytest.raises(BatchInputError, match="no motions"):
        parse_motions(text)


def test_the_first_malformed_line_is_reported_even_after_good_lines():
    with pytest.raises(BatchInputError, match="^Line 3:"):
        parse_motions("good\nalso good\nbad | | line\nlater bad |\n")


def test_reading_a_missing_file_is_a_clean_error(tmp_path):
    with pytest.raises(BatchInputError, match="Cannot read"):
        read_motions_file(tmp_path / "nope.txt")


def test_reading_a_file_from_disk(tmp_path):
    f = tmp_path / "motions.txt"
    f.write_text("A | B\nC\n", encoding="utf-8")
    assert len(read_motions_file(f)) == 3


def test_parsing_never_calls_a_model(monkeypatch):
    import debate_ai.run as run

    monkeypatch.setattr(run, "run_debate", lambda *a, **k: pytest.fail("model run"))
    parse_motions("A | B\n")
