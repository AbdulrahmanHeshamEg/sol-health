Verify the project is demo-ready:

1. `cd ml && python -m pytest -q` — must pass.
2. If `frontend/` has a package.json: `cd frontend && npm run build` and `npm run lint` — must be clean.
3. Start the API on port 8000 and check that `/api/me` names one astronaut, that `/api/crew/UH-01/assessment` is RED now with `escalation.status == "sent"` (the solar storm is under way), and that the same call with `at=2026-09-15T12:00:00` is GREEN.
4. Grep `frontend/src` for hard-coded thresholds or medical rules (e.g. `spo2 <`, `38.0`, `> 3`) — there must be none; status comes from the API.
5. Check the disclaimer and the "simulated astronaut" note are visible, and that values carry a real / simulated source badge.
6. Report each item as PASS / FAIL with the fix for any failure.
