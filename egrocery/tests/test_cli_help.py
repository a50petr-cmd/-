import pytest

from egrocery.__main__ import main


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    with pytest.raises(SystemExit) as exc2:
        main(["search", "--help"])
    assert exc2.value.code == 0
