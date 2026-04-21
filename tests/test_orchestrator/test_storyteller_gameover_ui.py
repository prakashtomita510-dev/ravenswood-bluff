from pathlib import Path


STORYTELLER_HTML = Path("public/storyteller.html").read_text(encoding="utf-8")


def test_storyteller_console_has_settlement_and_history_panels():
    assert "当前结算 / 封盘结果" in STORYTELLER_HTML
    assert 'id="settlementSummary"' in STORYTELLER_HTML
    assert "历史对局 / 复盘入口" in STORYTELLER_HTML
    assert 'id="historyList"' in STORYTELLER_HTML
    assert 'id="historyDetail"' in STORYTELLER_HTML


def test_storyteller_console_fetches_settlement_and_history_contracts():
    assert 'fetchJson("/api/game/settlement")' in STORYTELLER_HTML
    assert 'fetchJson("/api/game/history?limit=20")' in STORYTELLER_HTML
    assert 'fetchJson(`/api/game/history/${gameId}`)' in STORYTELLER_HTML
    assert "async function loadSettlement()" in STORYTELLER_HTML
    assert "async function loadHistory()" in STORYTELLER_HTML
    assert "async function loadHistoryDetail(gameId)" in STORYTELLER_HTML


def test_storyteller_console_requests_grimoire_with_storyteller_identity():
    assert 'id="storytellerPlayerId"' in STORYTELLER_HTML
    assert "function appendPlayerId(path)" in STORYTELLER_HTML
    assert 'fetchJson(appendPlayerId("/api/game/state"))' in STORYTELLER_HTML
    assert 'fetchJson(appendPlayerId("/api/game/grimoire?view=full"))' in STORYTELLER_HTML
