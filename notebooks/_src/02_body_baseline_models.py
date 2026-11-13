# %% [markdown]
# # 02 · Body baseline models: is today abnormal for *this* person?
#
# **Questions**
# 1. Which detector raises the fewest false alarms on real people and still catches a planted change fastest?
# 2. Do the methods complement each other (spikes vs slow drifts vs odd combinations)?
# 3. Which single signals carry the detection value?
# 4. Which **combination** should the engine use, and at which parameters?
#
# **Inputs:** `data/processed/pmdata_daily.parquet` (real PMData, 14 usable people; notebook 01).
# **Outputs:** comparison tables, trade-off figures `reports/figures/02_*.png`, and the chosen body-model parameters in `models/engine_config.json`.
#
# **Protocol** (shared, `docs/NOTEBOOKS.md`): false alarms per person-month on the real series (14-day warm-up, injury days ±2 excluded,
# consecutive alert days = one episode) and detection delay on changes planted into the real series (200 per change type, missed if not caught within 14 days).
# Target: **at most 1 false alarm per person-month**.
#
# **Conventions fixed after notebook 01** (agreed with the team in chat):
# - All signals are flipped into *badness* units, so a positive z always means worse (PMSys self-reports are 5 = best).
# - The self-reports are 1–5 integers whose MAD is usually 0, so their robust scale falls back to the mean absolute deviation, with a floor of half a scale point.
# - A planted change counts as detected only by an alert the untouched series did not already have.

# %%
import sys
sys.path.insert(0, "../ml")
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from joblib import Parallel, delayed
from scipy import stats
from sol_ml.nbutil import *
from sol_ml.detectors import body, evaluation
from sol_ml.detectors.baseline import BODY_SIGNALS, zscores
from sol_ml.detectors.evaluation import INJECTIONS

rng = setup()
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
warnings.filterwarnings("ignore")
TARGET_FA = 1.0
N_INJECTIONS = 200
CASES = list(INJECTIONS)

daily = pd.read_parquet(PROCESSED / "pmdata_daily.parquet")
names = [p for p in sorted(daily.person.unique()) if p not in ("p12", "p13")]
people = evaluation.load_people(daily, names)
sites = {name: evaluation.sample_sites(people, name, N_INJECTIONS, rng) for name in CASES}
months = sum(p.mask.sum() for p in people) / 30
print(len(people), "people,", round(months, 1), "evaluated person-months,", N_INJECTIONS, "planted changes per case")
pd.DataFrame([p.scales for p in people], index=names, columns=BODY_SIGNALS).round(2).T

# %% [markdown]
# ## 1. What the planted changes look like

# %%
p = people[0]
start = 90
fig, axes = plt.subplots(1, 4, figsize=(16, 3.2))
for ax, case in zip(axes, CASES):
    planted = evaluation.inject(p.X, case, start, p.scales, np.random.default_rng(SEED))
    cols = INJECTIONS[case][0]
    for j in cols:
        sign = 1 if BODY_SIGNALS[j] == "resting_hr" else -1
        z_clean, z_new = (p.X[:, j] - np.nanmedian(p.X[:, j])) / p.scales[j], (planted[:, j] - np.nanmedian(p.X[:, j])) / p.scales[j]
        ax.plot(range(start - 20, start + 20), z_clean[start - 20:start + 20], color="grey", lw=0.8)
        ax.plot(range(start, start + 14), z_new[start:start + 14], marker="o", ms=3, label=BODY_SIGNALS[j])
    ax.axvline(start, color="k", ls="--", lw=0.8)
    ax.set(title=case, xlabel="day", ylabel="badness (personal SDs)")
    ax.legend(fontsize=7)
fig.suptitle(f"Planted changes on {p.name}'s real series (grey = untouched)")
savefig("02_planted_changes");

# %% [markdown]
# ## 2. Are personal z-scores well behaved on real data?
# Limits such as "alert at z > 3" assume roughly normal, independent z-scores. Check that on the untouched data.

# %%
rows = []
for window in (7, 14, 28):
    Z = np.vstack([zscores(p.X, window)[p.mask] for p in people])
    for j, s in enumerate(BODY_SIGNALS):
        z = Z[:, j][~np.isnan(Z[:, j])]
        rows.append({"window": window, "signal": s, "sd_of_z": z.std(), "share_z>3": (z > 3).mean(), "share_z<-3": (z < -3).mean(),
                     "normal_would_be": stats.norm.sf(3)})
tails = pd.DataFrame(rows).set_index(["window", "signal"]).round(4)
tails

# %% [markdown]
# ## 3. Sweep every candidate

# %%
specs = []
for sided in ("worse", "both"):
    specs += [dict(kind="population_z", thr=t, sided=sided) for t in (2.0, 2.5, 3.0, 3.5, 4.0, 5.0)]
    specs += [dict(kind="personal_z", window=w, thr=t, sided=sided) for w in (7, 14, 28) for t in (2.5, 3.0, 3.5, 4.0, 5.0, 6.0)]
specs += [dict(kind="cusum", window=w, k=k, h=h) for w in (14, 28) for k in (0.5, 1.0, 1.5) for h in (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 14.0)]
specs += [dict(kind="ewma", window=w, lam=l, L=L) for w in (14, 28) for l in (0.1, 0.2, 0.3) for L in (2.5, 3.0, 3.5, 4.0, 5.0, 6.0)]
RATES = (0.005, 0.01, 0.02, 0.05, 0.1, 0.2)
specs += [dict(kind=kind, mode=mode, window=14, rate=r) for kind in ("iforest", "mahalanobis") for mode in ("pooled", "rolling") for r in RATES]
specs += [dict(kind="lof", mode="pooled", window=14, rate=r) for r in RATES]
print(len(specs), "configurations x", len(CASES) * N_INJECTIONS, "planted runs each")

def run_all(spec_list):
    return pd.DataFrame(Parallel(n_jobs=-1)(delayed(body.run_spec)(s, people, sites, SEED) for s in spec_list))

sweep = cached("nb02_sweep", [specs, sites], lambda: run_all(specs))
sweep["family"] = sweep.kind + np.where(sweep["mode"].notna(), " (" + sweep["mode"].fillna("") + ")", "") \
    + np.where(sweep.sided.eq("both"), " two-sided", "")
sweep.groupby("family").false_alarms.agg(["count", "min", "max"]).round(2)

# %%
LETTER = {"population_z": "A", "personal_z": "B", "cusum": "C", "ewma": "D", "iforest": "E", "mahalanobis": "F", "lof": "G"}
PARAMS = ["window", "thr", "sided", "k", "h", "lam", "L", "mode", "rate"]

def describe(row):
    return ", ".join(f"{k}={row[k]:g}" if isinstance(row[k], float) else f"{k}={row[k]}" for k in PARAMS
                     if k in row and pd.notna(row[k]) and not (k == "sided" and row[k] == "worse"))

def best_under(df, budget=TARGET_FA):
    ok = df[df.false_alarms <= budget]
    return ok.sort_values(["mean_delay", "mean_miss", "false_alarms"]).iloc[0] if len(ok) else None

rows = []
for family, g in sweep.groupby("family"):
    b = best_under(g)
    if b is None:
        rows.append({"model": LETTER[g.kind.iloc[0]], "family": family, "setting": "no setting reaches the target",
                     "false_alarms": g.false_alarms.min()})
        continue
    rows.append({"model": LETTER[b.kind], "family": family, "setting": describe(b), "false_alarms": b.false_alarms,
                 **{f"{c} (days / miss)": f"{b[c + '_delay_hit']:.0f} / {b[c + '_miss']:.0%}" for c in CASES},
                 "mean_delay": b.mean_delay, "mean_miss": b.mean_miss})
best = pd.DataFrame(rows).sort_values(["mean_delay", "mean_miss"]).reset_index(drop=True)
print("Fastest setting of each family with at most", TARGET_FA, "false alarm per person-month.")
print("days = median delay of the caught cases; miss = share not caught within 14 days; mean_delay counts a miss as 14 days.")
best.round(2)

# %%
fig, axes = plt.subplots(1, 5, figsize=(21, 4.2), sharex=True)
families = [f for f in sweep.family.unique() if "two-sided" not in f]
palette = dict(zip(families, sns.color_palette("tab10", len(families))))
for ax, col, title in zip(axes, ["mean_miss"] + [c + "_miss" for c in CASES], ["mean of the four cases"] + CASES):
    for family in families:
        g = sweep[sweep.family == family].sort_values("false_alarms")
        frontier = g[g[col] <= g[col].cummin()]                 # best miss rate at each false-alarm level
        ax.plot(frontier.false_alarms, frontier[col], marker="o", ms=3, lw=1.2, color=palette[family], label=family)
    ax.axvline(TARGET_FA, color="k", ls="--", lw=0.8)
    ax.set(title=title, xlabel="false alarms per person-month (real PMData)", xscale="log", ylim=(-0.03, 1.03))
axes[0].set_ylabel("share of planted changes missed within 14 days")
axes[0].legend(fontsize=7)
fig.suptitle("Trade-off: false alarms vs missed planted changes (lower-left is better; dashed = target)")
savefig("02_tradeoff_miss");

# %%
fig, axes = plt.subplots(1, 5, figsize=(21, 4.2), sharex=True)
for ax, col, title in zip(axes, ["mean_delay"] + [c + "_delay" for c in CASES], ["mean of the four cases"] + CASES):
    for family in families:
        g = sweep[sweep.family == family].sort_values("false_alarms")
        frontier = g[g[col] <= g[col].cummin()]
        ax.plot(frontier.false_alarms, frontier[col], marker="o", ms=3, lw=1.2, color=palette[family], label=family)
    ax.axvline(TARGET_FA, color="k", ls="--", lw=0.8)
    ax.set(title=title, xlabel="false alarms per person-month (real PMData)", xscale="log", ylim=(-0.5, 14.5))
axes[0].set_ylabel("median delay in days (a miss counts as 14)")
axes[0].legend(fontsize=7)
fig.suptitle("Trade-off: false alarms vs detection delay")
savefig("02_tradeoff_delay");

# %% [markdown]
# ## 4. One-sided or two-sided, and does the personal baseline beat the population one?

# %%
cmp = sweep[sweep.kind.isin(["personal_z", "population_z"])].copy()
cmp["sided"] = cmp.sided.fillna("worse")
rows = []
for (kind, sided), g in cmp.groupby(["kind", "sided"]):
    b = best_under(g)
    rows.append({"kind": kind, "sided": sided, "setting": describe(b) if b is not None else "-",
                 "false_alarms": b.false_alarms if b is not None else g.false_alarms.min(),
                 **({c + "_miss": b[c + "_miss"] for c in CASES} if b is not None else {}),
                 "mean_delay": b.mean_delay if b is not None else np.nan})
pd.DataFrame(rows).round(2)

# %% [markdown]
# ## 5. Do the methods complement each other?
# Each family at its own best setting under the target: which planted changes does it miss?

# %%
points = {f: best_under(g) for f, g in sweep[~sweep.family.str.contains("two-sided")].groupby("family")}
points = {f: b for f, b in points.items() if b is not None}
miss = pd.DataFrame({f: [b[c + "_miss"] for c in CASES] for f, b in points.items()}, index=CASES).T
fig, ax = plt.subplots(figsize=(7, 4.2))
sns.heatmap(miss, annot=True, fmt=".0%", cmap="rocket_r", vmin=0, vmax=1, ax=ax, cbar_kws={"label": "missed within 14 days"})
ax.set_title(f"Miss rate per planted change, each family at ≤ {TARGET_FA:g} false alarm / person-month")
savefig("02_complementarity");
miss.round(2)

# %% [markdown]
# ## 6. Which single signals carry the detection value? (ablation)
# The best univariate settings are re-run on one signal at a time.

# %%
def spec_of(row, **extra):
    spec = {"kind": row.kind}
    for k in PARAMS:
        if k in row and pd.notna(row[k]):
            spec[k] = int(row[k]) if k == "window" else row[k]
    spec.update(extra)
    return spec

abl_specs, labels = [], []
for family in ("personal_z", "cusum", "ewma"):
    if family not in points:
        continue
    for j, s in enumerate(BODY_SIGNALS):
        abl_specs.append(spec_of(points[family], cols=[j])); labels.append((family, s))
    abl_specs.append(spec_of(points[family], cols=list(range(5)))); labels.append((family, "all five"))
abl = cached("nb02_ablation", [abl_specs, sites], lambda: run_all(abl_specs))
abl.index = pd.MultiIndex.from_tuples(labels, names=["detector", "signal"])
abl[["false_alarms"] + [c + "_miss" for c in CASES]].round(2)

# %% [markdown]
# ## 7. Combinations
# The team's plan is **B for spikes + C for drifts + E for odd combinations**. The whole combination has to stay under the target,
# so each member gets a share of the false-alarm budget. Every family contributes its fastest setting under several budgets, and all unions are evaluated.

# %%
BUDGETS = (0.15, 0.3, 0.5, 0.8)
def options(family):
    g = sweep[sweep.family == family]
    out = {}
    for b in BUDGETS:
        row = best_under(g, b)
        if row is not None:
            out[json.dumps(spec_of(row), sort_keys=True)] = spec_of(row)
    return list(out.values())

spike_opts = options("personal_z")
drift_opts = options("cusum") + options("ewma")
combo_opts = options("mahalanobis (pooled)") + options("iforest (pooled)")
members = []
for s in spike_opts:
    for d in drift_opts:
        members.append([s, d])
        members += [[s, d, m] for m in combo_opts]
members += [[d, m] for d in drift_opts for m in combo_opts]
combo_specs = [dict(kind="any_of", members=m) for m in members]
print(len(spike_opts), "spike x", len(drift_opts), "drift x", len(combo_opts), "combination options ->", len(combo_specs), "unions")
combos = cached("nb02_combos", [combo_specs, sites], lambda: run_all(combo_specs))
combos["members"] = [" + ".join(LETTER[m["kind"]] for m in ms) for ms in members]
combos["spec"] = [json.dumps(ms) for ms in members]
rows = []
for shape, g in combos.groupby("members"):
    b = best_under(g)
    if b is not None:
        rows.append({"combination": shape, "false_alarms": b.false_alarms,
                     **{f"{c} (days / miss)": f"{b[c + '_delay_hit']:.0f} / {b[c + '_miss']:.0%}" for c in CASES},
                     "mean_delay": b.mean_delay, "mean_miss": b.mean_miss, "spec": b.spec})
combo_best = pd.DataFrame(rows).sort_values(["mean_delay", "mean_miss"]).reset_index(drop=True)
combo_best.drop(columns="spec").round(2)

# %%
chosen = combo_best.iloc[0]
single = best.iloc[0]
print("best single family :", single.family, "|", single.setting, "| FA %.2f, mean delay %.1f, mean miss %.0f%%" % (single.false_alarms, single.mean_delay, 100 * single.mean_miss))
print("best combination   :", chosen.combination, "| FA %.2f, mean delay %.1f, mean miss %.0f%%" % (chosen.false_alarms, chosen.mean_delay, 100 * chosen.mean_miss))
chosen_members = json.loads(chosen.spec)
for m in chosen_members:
    print("  ", m)

fig, ax = plt.subplots(figsize=(8, 4.5))
for family in families:
    g = sweep[sweep.family == family].sort_values("false_alarms")
    f = g[g.mean_miss <= g.mean_miss.cummin()]
    ax.plot(f.false_alarms, f.mean_miss, lw=1, color=palette[family], alpha=0.6, label=family)
g = combos.sort_values("false_alarms")
f = g[g.mean_miss <= g.mean_miss.cummin()]
ax.plot(f.false_alarms, f.mean_miss, color="k", lw=2.2, marker="o", ms=4, label="best combinations")
ax.scatter([chosen.false_alarms], [chosen.mean_miss], s=160, facecolor="none", edgecolor="red", lw=2, zorder=5, label="chosen")
ax.axvline(TARGET_FA, color="k", ls="--", lw=0.8)
ax.set(xscale="log", xlabel="false alarms per person-month (real PMData)", ylabel="mean miss rate over the four cases",
       title="Combinations vs single detectors")
ax.legend(fontsize=7)
savefig("02_combination_vs_single");

# %% [markdown]
# ## 8. How robust is the chosen combination across people?

# %%
detector = body.build(dict(kind="any_of", members=chosen_members), people)
rows = []
for p in people:
    alerts = detector(p, p.X)
    rows.append({"person": p.name, "evaluated_days": int(p.mask.sum()), "alert_episodes": evaluation.count_episodes(alerts & p.mask),
                 "alert_days": int((alerts & p.mask).sum())})
per_person = pd.DataFrame(rows).set_index("person")
per_person["false_alarms_per_month"] = (per_person.alert_episodes / (per_person.evaluated_days / 30)).round(2)
print("pooled: %.2f per person-month | worst person: %.2f | people above the target: %d of %d" % (
    per_person.alert_episodes.sum() / (per_person.evaluated_days.sum() / 30), per_person.false_alarms_per_month.max(),
    (per_person.false_alarms_per_month > TARGET_FA).sum(), len(per_person)))
per_person.T

# %% [markdown]
# ## 9. What the astronaut would read
# Every alert has to explain itself in one sentence: the signal, how far from normal, and for how long.

# %%
LABEL = {"resting_hr": "resting heart rate", "sleep_minutes": "sleep", "fatigue": "fatigue score", "mood": "mood score", "stress": "stress score"}
WORSE = {"resting_hr": "above", "sleep_minutes": "below", "fatigue": "worse than", "mood": "worse than", "stress": "worse than"}

def reason(X, day, window):
    z = zscores(X, window)
    j = int(np.nanargmax(z[day]))
    run = 0
    while day - run >= 0 and (z[day - run, j] > 1 or np.isnan(z[day - run, j])):
        run += 1
    return (f"{LABEL[BODY_SIGNALS[j]].capitalize()} is {z[day, j]:.1f} robust SD {WORSE[BODY_SIGNALS[j]]} your {window}-day normal"
            f" and has been off for {max(run, 1)} day{'s' if run > 1 else ''}.")

window = int(chosen_members[0].get("window", 14))
for case in CASES:
    i, s = sites[case][0]
    p = people[i]
    planted = evaluation.inject(p.X, case, s, p.scales, np.random.default_rng(SEED))
    new = detector(p, planted, start=s) & ~detector(p, p.X, start=s)
    hit = np.flatnonzero(new[s:s + 14])
    print(f"{case:<12} on {p.name}: " + (f"alert on day {hit[0]} -> {reason(planted, s + hit[0], window)}" if len(hit) else "not caught within 14 days"))

# %%
config_path = MODELS / "engine_config.json"
config = json.loads(config_path.read_text()) if config_path.exists() else {}
config["body"] = {
    "source_notebook": "02_body_baseline_models",
    "signals": BODY_SIGNALS,
    "scale": {"continuous": "1.4826*MAD", "ordinal": "1.2533*mean_abs_dev, floor 0.5 point", "direction": "badness (positive z = worse)"},
    "members": chosen_members,
    "false_alarms_per_person_month_pmdata": round(float(chosen.false_alarms), 3),
    "target_false_alarms_per_person_month": TARGET_FA,
    "detection": {c: {"median_delay_days": float(combos.loc[combos.spec == chosen.spec, c + "_delay_hit"].iloc[0]),
                      "miss_rate": round(float(combos.loc[combos.spec == chosen.spec, c + "_miss"].iloc[0]), 3)} for c in CASES},
}
config_path.write_text(json.dumps(config, indent=2))
print(json.dumps(config["body"], indent=2))

# %% [markdown]
# DECISION_PLACEHOLDER
