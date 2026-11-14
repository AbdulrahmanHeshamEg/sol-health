// Everyday wording for alerts. The astronaut is not a doctor or a data scientist, so the main screens say what is
// going on in plain words. Built only from the alert's own fields (kind, signal, value, and the duration in its
// reason); it adds no judgement of its own. The engine's exact wording stays one tap away ("More detail").
import type { Alert } from "../api/types";

const NAME: Record<string, string> = {
  mood: "Your mood", stress: "Your stress level", fatigue: "Your energy", resting_hr: "Your resting heart rate",
  heart_rate: "Your heart rate", sleep_minutes: "Your sleep", sleep_hours: "Your sleep", spo2: "Your blood oxygen",
  core_temp: "Your temperature", systolic_bp: "Your blood pressure", diastolic_bp: "Your blood pressure",
  blood_glucose_mg_dl: "Your blood sugar", hrv_rmssd: "Your heart rhythm", pvt_reaction_ms: "Your reaction time",
  resp_rate: "Your breathing rate",
};
const SHORT: Record<string, string> = { stress: "stress", mood: "mood", fatigue: "energy", sleep: "sleep", resting: "resting heart rate", heart: "heart rate" };

/** "for 7 days" → 7. */
const daysIn = (text: string) => { const m = text.match(/for (\d+) days?/); return m ? Number(m[1]) : null; };
const forDays = (n: number | null) => (n === null ? "" : n === 1 ? " today" : ` for ${n} days`);

/** The readings named in "(stress score +2.7 SD, mood score +1.9 SD; ...)", in plain words. */
function readingsIn(reason: string): string[] {
  const inside = reason.match(/\(([^)]*)\)/)?.[1] ?? "";
  return [...inside.matchAll(/([a-z]+)[a-z ]*?[+−-]\d/g)].map((m) => SHORT[m[1]] ?? m[1]).filter((x, i, all) => all.indexOf(x) === i);
}
const list = (xs: string[]) => (xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

export function plainAlert(a: Alert): { title: string; body: string } {
  const who = (a.signal && NAME[a.signal]) ?? "One of your readings";
  const days = daysIn(a.reason);
  switch (a.kind) {
    case "combination": {
      const names = readingsIn(a.reason);
      return {
        title: "A few things shifted together",
        body: `${names.length === 2 ? `Your ${list(names)} both` : names.length ? `Your ${list(names)} all` : "A few of your readings"} moved the wrong way a little at the same time${forDays(days)}. None of them is far off on its own.`,
      };
    }
    case "spike":
      return { title: `${who} is unusual for you`, body: `${who} is well away from your usual level${forDays(days)}.` };
    case "drift": {
      const dir = /below/.test(a.reason) ? "below" : "above";
      return { title: `${who} is slowly ${dir === "above" ? "creeping up" : "dropping"}`, body: `${who} has been ${dir} your usual level${forDays(days)}.` };
    }
    case "mood":
      return { title: "Your mood has been low", body: `Your mood has been lower than usual${forDays(days)}.` };
    case "hard_limit":
      return { title: `${who} is outside the safe range`, body: a.value !== undefined ? `It is ${a.value.toFixed(1)} right now.` : a.reason };
    case "environmental_gate":
      return { title: "The cabin air is stuffy", body: "There is more CO2 in the cabin than there should be. A headache or tiredness right now is probably the air. Air out the cabin first." };
    case "spe":
      return { title: "Solar storm: go to the shelter now", body: a.value !== undefined ? `Radiation is about ${Math.round(a.value)} times higher than usual.` : a.reason };
    case "fitness_trend":
      return { title: "Your fitness is slipping a little", body: "Your heart is working a bit harder in the same workouts than it used to." };
    case "eye_exam":
      return { title: "Your eye photo changed a little", body: "The back of your eye looks slightly blurrier than in your first photo. Your flight surgeon will look at it." };
    default:
      return { title: a.message, body: a.reason };
  }
}
