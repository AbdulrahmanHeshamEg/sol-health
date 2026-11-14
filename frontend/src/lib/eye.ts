// The eye exam is a monthly check, so it lives on My body > Eye exam and stays off the daily screens.
// These helpers only decide where an item is shown. The engine still assesses, reports and escalates it.
import type { Action, Alert, Question } from "../api/types";

const EYE_CONDITIONS = new Set(["optic_disc_change"]);
const EYE_FIELDS = new Set(["vision_change"]);

export const isEyeAlert = (a: Alert) => a.kind === "eye_exam" || EYE_CONDITIONS.has(a.condition);
export const isEyeAction = (a: Action) => EYE_CONDITIONS.has(a.condition);
export const isEyeQuestion = (q: Question) => q.type === "photo" || EYE_FIELDS.has(q.field);
