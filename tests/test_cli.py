import pytest

from yaounde_analyzer.cli import main


def test_cli_exposes_fixed_scope(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--scope"]) == 0
    assert capsys.readouterr().out.strip() == "cameroon_francanglais"


def test_cli_does_not_offer_a_language_switch() -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--language", "english"])
    assert raised.value.code == 2


def test_cli_reports_unimplemented_analyzer(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "not implemented yet" in capsys.readouterr().out