Verify the project is demo-ready:

1. `cd ml && python -m pytest -q` — must pass.
2. If `frontend/` has a package.json: `cd frontend && npm run build` and `npm run lint` — must be clean.
3. Start the API on port 8000 and check that `/api/crew` returns 4 crew with statuses RED, RED, YELLOW, GREEN.
4. Grep `frontend/src` for hard-coded thresholds or medical rules (e.g. `spo2 <`, `38.0`, `> 3`) — there must be none; status comes from the API.
5. Check the disclaimer and the "synthetic data" note are visible.
6. Report each item as PASS / FAIL with the fix for any failure.
