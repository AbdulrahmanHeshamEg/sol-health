// Eye exam: your fundus photos, measured against your own baseline photo. Any image can be uploaded; the engine
// says when a photo cannot be read. The measurements are classical image measurements, not a trained model.
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Camera, Images, ScanEye, Upload as UploadIcon } from "lucide-react";
import { api, photoUrl } from "../api/client";
import { useEyeExams, useMe, useMeta } from "../api/hooks";
import type { EyeExam } from "../api/types";
import { useReplay } from "../state/replay";
import { Card, ErrorNote, LEVEL_INK, LEVEL_SOFT, PageHeader, Skeleton, SourceBadge, StatusBadge, StatusIcon, fmt, when } from "../components/ui";

function Photo({ exam, title }: { exam: EyeExam; title: string }) {
  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span><span className="font-semibold">{title}</span> <span className="text-ink-3">· sol {exam.mission_day}, {when(exam.date)}</span></span>
        <SourceBadge source={exam.source} />
      </figcaption>
      <img src={photoUrl(exam.url)} alt={`Fundus photo from sol ${exam.mission_day}`} className="block aspect-square w-full rounded-2xl bg-[#05070d] object-contain" />
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
      <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line-strong bg-surface-2 p-8 text-center transition-colors hover:border-brand">
        <span className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-soft text-brand-ink"><UploadIcon size={22} aria-hidden="true" /></span>
        <span className="font-semibold">{busy ? "Checking the photo…" : "Upload a fundus photo"}</span>
        <span className="max-w-[48ch] text-sm text-ink-3">Any image is accepted. If it is not a readable retina photo, the check tells you what to fix.</span>
        <input type="file" accept="image/*" className="sr-only" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      </label>
      {error && <p role="alert" className="mt-3 rounded-xl border border-line bg-surface-2 p-3 text-sm">{error}</p>}
      {result && (
        <div className="mt-3 flex items-start gap-3 rounded-xl p-4" style={{ background: LEVEL_SOFT[result.result.level] }} aria-live="polite">
          <StatusIcon level={result.result.level} />
          <p className="text-sm" style={{ color: LEVEL_INK[result.result.level] }}>{result.result.reason}</p>
        </div>
      )}
    </div>
  );
}

function Ratio({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-xl bg-surface-2 p-4">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="m-0 mt-1 tnum text-2xl font-bold">{value}</dd>
      {note && <dd className="m-0 mt-1 text-xs text-ink-3">{note}</dd>}
    </div>
  );
}

/** The monthly eye exam. Shown as a tab of My body (`embedded`) or on its own at /eyes. */
export function Eyes({ embedded = false }: { embedded?: boolean }) {
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
      {embedded
        ? <p className="max-w-[80ch] text-sm text-ink-2">Once a month you photograph the back of your eye. In weightlessness the optic disc can swell (SANS), which blurs its edge. The app compares each photo with your first one. It measures the image and makes no diagnosis, and your flight surgeon sees every photo that changed.</p>
        : <PageHeader title="Eye exam" subtitle="Once a month you photograph the back of your eye. In weightlessness the optic disc can swell (SANS), which blurs its edge. The app compares each photo with your first one. It measures the image and makes no diagnosis, and your flight surgeon sees every photo that changed." />}

      {latest && baseline && (
        <Card title="Latest photo against your baseline" icon={<ScanEye size={18} />} aside={<StatusBadge level={latest.result.level} />}>
          <div className="grid gap-6 md:grid-cols-2">
            <Photo exam={baseline} title="Baseline" />
            <Photo exam={latest} title="Latest" />
          </div>
          <div className="mt-5 flex items-start gap-3 rounded-xl p-4" style={{ background: LEVEL_SOFT[latest.result.level] }}>
            <StatusIcon level={latest.result.level} />
            <p className="text-sm" style={{ color: LEVEL_INK[latest.result.level] }}>{latest.result.reason}</p>
          </div>
          {latest.result.ratios && (
            <dl className="m-0 mt-4 grid gap-3 sm:grid-cols-3">
              <Ratio label="Disc edge sharpness vs baseline" value={pct(latest.result.ratios.margin_sharpness)} note={lim && `below ${pct(lim.eye_margin_watch)} is watch, below ${pct(lim.eye_margin_act)} act now`} />
              <Ratio label="Disc size vs baseline" value={pct(latest.result.ratios.disc_area)} note={lim && `above ${pct(lim.eye_disc_growth_act)} is act now`} />
              <Ratio label="Vessels visible at the edge" value={pct(latest.result.ratios.vessel_visibility)} note="swelling hides them" />
            </dl>
          )}
        </Card>
      )}

      <Card title="Add a photo" icon={<Camera size={18} />}><Upload astronautId={me.data.astronaut_id} /></Card>

      <Card title="All your eye photos" icon={<Images size={18} />} aside={`${list.length} photo${list.length === 1 ? "" : "s"}`}>
        {list.length === 0 ? <p className="text-sm text-ink-2">No eye photos yet. Your first one becomes your baseline.</p> : (
          <ol className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
            {[...list].reverse().map((e) => (
              <li key={e.date} className="text-sm">
                <img src={photoUrl(e.url)} alt={`Fundus photo from sol ${e.mission_day}`} className="block aspect-square w-full rounded-xl bg-[#05070d] object-contain" />
                <p className="mt-2 flex items-center justify-between gap-2"><span className="font-semibold">Sol {e.mission_day}</span><StatusBadge level={e.result.level} size="sm" /></p>
                <p className="mt-0.5 text-xs text-ink-3">Edge sharpness {fmt(e.measurements.disc.margin_sharpness, 2)}{e.measurements.usable ? "" : " · photo not readable"}</p>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
