// Eye exam: your fundus photos, measured against your own baseline photo. Any image can be uploaded; the engine
// says when a photo cannot be read. The measurements are classical image measurements, not a trained model.
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, photoUrl } from "../api/client";
import { useEyeExams, useMe, useMeta } from "../api/hooks";
import type { EyeExam } from "../api/types";
import { useReplay } from "../state/replay";
import { ErrorNote, LEVEL_COLOR, Panel, Skeleton, SourceBadge, StatusChip, fmt, when } from "../components/ui";

function Photo({ exam, title }: { exam: EyeExam; title: string }) {
  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span><span className="display">{title}</span> <span className="text-dust-dim">sol {exam.mission_day}, {when(exam.date)}</span></span>
        <SourceBadge source={exam.source} />
      </figcaption>
      <img src={photoUrl(exam.url)} alt={`Fundus photo from sol ${exam.mission_day}`} className="block aspect-square w-full rounded-sm bg-basalt object-contain" />
    </figure>
  );
}

const pct = (r: number | undefined) => (r === undefined ? "–" : `${Math.round(r * 100)}%`);

function Upload({ astronautId }: { astronautId: string }) {
  const { at } = useReplay();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EyeExam | null>(null);

  async function onFile(file: File) {
    setBusy(true); setError(null); setResult(null);
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result));
        r.onerror = () => reject(new Error("The file could not be read."));
        r.readAsDataURL(file);
      });
      const out = await api.eyePhoto(astronautId, b64, file.name, at);
      setResult(out.exam);
      await queryClient.invalidateQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The photo was not checked.");
    } finally { setBusy(false); }
  }

  return (
    <div>
      <label className="btn inline-block cursor-pointer">
        {busy ? "Checking the photo" : "Upload a fundus photo"}
        <input type="file" accept="image/*" className="sr-only" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      </label>
      <p className="mt-2 max-w-[64ch] text-sm text-dust-dim">Any image is accepted. If it is not a readable retina photo, the check tells you what to fix.</p>
      {error && <p role="alert" className="mt-3 max-w-[70ch] rounded-sm border border-line p-3 text-sm">{error}</p>}
      {result && (
        <div className="mt-3 rounded-sm bg-basalt p-4" aria-live="polite">
          <StatusChip level={result.result.level} />
          <p className="mt-1 max-w-[70ch] text-base">{result.result.reason}</p>
        </div>
      )}
    </div>
  );
}

export function Eyes() {
  const me = useMe();
  const exams = useEyeExams(me.data?.astronaut_id);
  const lim = useMeta().data?.limits;
  if (me.isError) return <ErrorNote error={me.error} retry={() => me.refetch()} />;
  if (exams.isError) return <ErrorNote error={exams.error} retry={() => exams.refetch()} />;
  if (!me.data || !exams.data) return <Skeleton lines={8} height={28} />;
  const list = exams.data;
  const baseline = list.find((e) => e.measurements.usable);
  const latest = list[list.length - 1];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl">Eye exam</h1>
        <p className="mt-1 max-w-[72ch] text-base text-dust-dim">
          Once a month you photograph the back of your eye. In weightlessness the optic disc can swell (SANS); a swollen disc has a blurrier edge.
          Each photo is measured and compared with your first photo. This is an image measurement, not a diagnosis: your flight surgeon sees every changed photo.
        </p>
      </div>

      {latest && baseline && (
        <Panel title="Your latest photo against your baseline">
          <div className="grid gap-6 md:grid-cols-2">
            <Photo exam={baseline} title="Baseline" />
            <Photo exam={latest} title="Latest" />
          </div>
          <div className="mt-5 rounded-sm p-4" style={{ borderLeft: `6px solid ${LEVEL_COLOR[latest.result.level]}`, background: "var(--color-basalt)" }}>
            <StatusChip level={latest.result.level} />
            <p className="mt-1 max-w-[72ch] text-base">{latest.result.reason}</p>
          </div>
          {latest.result.ratios && (
            <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-3">
              <div><dt className="text-dust-dim">Disc edge sharpness, vs baseline</dt><dd className="numeral text-2xl">{pct(latest.result.ratios.margin_sharpness)}</dd>{lim && <dd className="text-dust-dim">below {pct(lim.eye_margin_watch)} is watch, below {pct(lim.eye_margin_act)} act now</dd>}</div>
              <div><dt className="text-dust-dim">Disc size, vs baseline</dt><dd className="numeral text-2xl">{pct(latest.result.ratios.disc_area)}</dd>{lim && <dd className="text-dust-dim">above {pct(lim.eye_disc_growth_act)} is act now</dd>}</div>
              <div><dt className="text-dust-dim">Vessels visible at the edge, vs baseline</dt><dd className="numeral text-2xl">{pct(latest.result.ratios.vessel_visibility)}</dd><dd className="text-dust-dim">swelling hides them</dd></div>
            </dl>
          )}
        </Panel>
      )}

      <Panel title="Add a photo"><Upload astronautId={me.data.astronaut_id} /></Panel>

      <Panel title="All your eye photos">
        {list.length === 0 ? <p className="text-base">No eye photos yet. Your first one becomes your baseline.</p> : (
          <ol className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {[...list].reverse().map((e) => (
              <li key={e.date} className="text-sm">
                <img src={photoUrl(e.url)} alt={`Fundus photo from sol ${e.mission_day}`} className="block aspect-square w-full rounded-sm bg-basalt object-contain" />
                <p className="mt-1"><span className="display">Sol {e.mission_day}</span> <StatusChip level={e.result.level} /></p>
                <p className="text-dust-dim">Edge sharpness {fmt(e.measurements.disc.margin_sharpness, 2)}{e.measurements.usable ? "" : "; photo not readable"}</p>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}
