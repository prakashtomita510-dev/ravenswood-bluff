# Frontend Acceptance Flow

This repository now has two layers of acceptance for the player and storyteller UI:

1. A repeatable repo-local contract check:
   - `.\.venv\Scripts\python.exe scripts\frontend_acceptance.py`
   - `.\.venv\Scripts\python.exe -m pytest tests\test_orchestrator\test_frontend_acceptance.py -q`

2. A browser-level MCP/Playwright smoke test:
   - Start the app locally on `http://127.0.0.1:8000`
   - Open `http://127.0.0.1:8000/ui/index.html`
   - Connect as a player
   - Confirm first-night private info appears
   - Confirm `聊天室` stays on chat and `状态页` stays on state
   - Confirm the nomination panel shows current stage, nominator, nominee, vote count, and result
   - Confirm player mode cannot access `/api/game/grimoire`
   - Repeat as storyteller mode and confirm grimoire access is allowed

## Expected Browser Checks

- Player mode:
  - The grimoire button must not expose full grimoire contents.
  - Private info should appear in the state page or private panel.
  - Nomination status should remain visible through nomination, defense, voting, and result.
  - Chat tab should not be forced back to the state tab.

- Storyteller mode:
  - `/api/game/grimoire` should be accessible.
  - The state payload should include full player identity fields.
  - The storyteller panel should expose the night-step and judgement logging workflow.

## Notes

- `playwright` is not currently installed as a Python dependency in this repo.
- The browser smoke is therefore run through MCP/Playwright tooling, while the repo-local script and pytest case keep the acceptance contract executable inside the workspace.
