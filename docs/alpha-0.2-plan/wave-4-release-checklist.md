# Wave 4 Release Checklist

## Purpose

Use this checklist before declaring Wave 4 complete or preparing the final `alpha 0.2` release candidate.

The goal is to ensure the project is not only feature-complete on paper, but also:

1. can settle games correctly,
2. can browse history and replay context,
3. can support storyteller-side review,
4. and has a stable automated acceptance path.

---

## Core Acceptance Gates

- [ ] [gameover_acceptance.py](d:/鸦木布拉夫小镇/scripts/gameover_acceptance.py) passes
- [ ] [wave4_acceptance.py](d:/鸦木布拉夫小镇/scripts/wave4_acceptance.py) passes
- [ ] settlement / history / rematch API contracts remain green
- [ ] player-side game over overlay and rematch hooks remain green
- [ ] storyteller-side settlement and history review hooks remain green

---

## Backend Settlement

- [ ] settlement report is produced when the game reaches `GAME_OVER`
- [ ] settlement report includes:
  - `game_id`
  - `winning_team`
  - `victory_reason`
  - `duration_rounds`
  - `days_played`
  - `players`
  - `timeline`
  - `statistics`
- [ ] finished games can be saved and queried from SQLite
- [ ] shared-memory SQLite test path remains stable

---

## History / Replay Data

- [ ] `/api/game/history` returns recent games
- [ ] `/api/game/history/{game_id}` returns a full detail record
- [ ] `/api/game/history/player/{player_name}` returns per-player history
- [ ] record payloads are sufficient for later replay / review expansion

---

## Player Experience

- [ ] game over overlay opens when the game ends
- [ ] settlement content renders winner / roles / timeline / statistics
- [ ] rematch API and front-end hook still reopen a fresh game cleanly
- [ ] history overlay opens and shows list + detail
- [ ] invalid-action retry reminders still reach humans and do not silently stall the game

---

## Storyteller Experience

- [ ] storyteller console shows current settlement summary
- [ ] storyteller console shows history list
- [ ] storyteller console shows single-game review detail
- [ ] storyteller console remains compatible with grimoire and metrics views

---

## Final Manual Verification

- [ ] one player-side browser walkthrough of `game_over -> settlement -> history -> rematch`
- [ ] one storyteller-side browser walkthrough of `metrics -> settlement -> history detail`
- [ ] no blocking console errors during the walkthroughs

---

## Notes

- Long-running manual browser checks should still follow the `30s` progress inspection rule.
- If one acceptance script starts behaving unexpectedly slow, stop and inspect before waiting further.
