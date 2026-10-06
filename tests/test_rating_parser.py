import pytest

from concert_agent.rating_parser import parse_rating


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8", 8.0),
        ("8/10", 8.0),
        ("solid 9", 9.0),
        ("6.5 but might grow on me", 6.5),
        ("10/10 insane", 10.0),
        ("no rating yet", None),
        ("11/10", None),
    ],
)
def test_parse_rating(text, expected):
    assert parse_rating(text) == expected
