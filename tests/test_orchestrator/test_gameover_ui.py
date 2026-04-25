from pathlib import Path


INDEX_HTML = Path("public/index.html").read_text(encoding="utf-8")


def test_settlement_overlay_hooks_exist():
    assert 'id="settlementOverlay"' in INDEX_HTML
    assert "async function fetchAndShowSettlement()" in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/settlement`)' in INDEX_HTML
    assert "if (gameState.phase === 'game_over' && settlementShownFor !== gameState.game_id)" in INDEX_HTML
    assert "showSettlementOverlay(data);" in INDEX_HTML


def test_rematch_frontend_contract_is_wired():
    assert "async function requestRematch()" in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/rematch`, { method: \'POST\' })' in INDEX_HTML
    assert "closeSettlementOverlay();" in INDEX_HTML
    assert "clearSessionArtifacts(data.new_game_id);" in INDEX_HTML
    assert "data.type === 'game_rematch'" in INDEX_HTML
    assert "clearSessionArtifacts(data.new_game_id);" in INDEX_HTML
    assert "function resetSetupOverlay()" in INDEX_HTML
    assert "if (gameState.setup_required && ws)" in INDEX_HTML
    assert "if (!gameState.setup_required && gameState.phase !== 'setup')" in INDEX_HTML


def test_history_overlay_contract_is_wired():
    assert 'id="historyOverlay"' in INDEX_HTML
    assert 'id="historyBtn"' in INDEX_HTML
    assert "async function toggleHistoryOverlay(forceOpen = null)" in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/history?limit=20`)' in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/history/player/${encodeURIComponent(currentUserId)}`)' in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/history/${encodeURIComponent(gameId)}`)' in INDEX_HTML
    assert "function openHistoryFromSettlement()" in INDEX_HTML
    assert "const storytellerJudgements = data.storyteller_judgements || {}" in INDEX_HTML
    assert 'id="historyJudgementBox"' in INDEX_HTML
    assert "说书人裁量摘要" in INDEX_HTML


def test_rules_overlay_includes_night_order_rulebook_contract():
    assert "async function showRuleTab(tab)" in INDEX_HTML
    assert 'fetch(`${backendHttpOrigin()}/api/game/night-order`)' in INDEX_HTML
    assert "Trouble Brewing 夜晚顺序" in INDEX_HTML
    assert "tie_strategy" in INDEX_HTML
