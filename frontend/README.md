# Frontend

The React + TypeScript + Vite dashboard is implemented in `src/`.

```bash
npm ci
npm run dev
```

The dev server runs at `http://localhost:5173` and proxies `/api` to `http://localhost:8000`. Start the FastAPI service from `../ml` with `uvicorn api.main:app --reload --port 8000`.

`npm run dev` and `npm run build` synchronize the saved API snapshots from `../data/demo/api_snapshots/` into `public/mock/`. To force offline mode, set `VITE_USE_MOCK=true` before starting Vite. The mock mode can serve only saved moments.

See `../docs/PROJECT_GUIDE_AR.md` for the application map, model explanations, and data provenance.
