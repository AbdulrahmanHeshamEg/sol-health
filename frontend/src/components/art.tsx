// Hand-drawn SVG artwork for Sol Health. Everything is vector, so it stays sharp at any size,
// and the illustrations read the theme tokens, so they switch with light and dark mode.
import { useId } from "react";

/** The Sol Health mark: a new sol rising. The sun comes up over a horizon that is a heartbeat. */
const LOGO_PULSE = "M9 39h13.5l3.5-7.5 4.5 13 4-10 2.5 4.5H55";
export function LogoMark({ size = 40 }: { size?: number }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" style={{ flex: "none" }}>
      <defs>
        <linearGradient id={`${id}sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1e2c55" />
          <stop offset="1" stopColor="#0b1126" />
        </linearGradient>
        <linearGradient id={`${id}sun`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd27a" />
          <stop offset="1" stopColor="#ff6b3d" />
        </linearGradient>
        <clipPath id={`${id}above`}><rect width="64" height="39" /></clipPath>
      </defs>
      <rect width="64" height="64" rx="15" fill={`url(#${id}sky)`} />
      <g clipPath={`url(#${id}above)`}>
        <circle cx="32" cy="39" r="21" fill="#ff7a45" opacity="0.16" />
        <circle cx="32" cy="39" r="13.5" fill={`url(#${id}sun)`} />
      </g>
      <path d={LOGO_PULSE} fill="none" stroke="#fff" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Mars, lit from the upper left, with a polar cap, craters and Valles-style scarring. */
export function MarsGlobe({ size = 40 }: { size?: number }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" style={{ flex: "none" }}>
      <defs>
        <radialGradient id={`${id}body`} cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="#f6b48a" />
          <stop offset="0.45" stopColor="#d96a3b" />
          <stop offset="1" stopColor="#7a2c14" />
        </radialGradient>
        <radialGradient id={`${id}shade`} cx="0.3" cy="0.25" r="0.95">
          <stop offset="0.55" stopColor="#000" stopOpacity="0" />
          <stop offset="1" stopColor="#1a0904" stopOpacity="0.55" />
        </radialGradient>
        <clipPath id={`${id}clip`}><circle cx="32" cy="32" r="30" /></clipPath>
      </defs>
      <circle cx="32" cy="32" r="30" fill={`url(#${id}body)`} />
      <g clipPath={`url(#${id}clip)`}>
        <path d="M6 36c8-3 15 2 24-1s16-6 30-1" fill="none" stroke="#9c3d1c" strokeWidth="3" strokeLinecap="round" opacity=".55" />
        <path d="M14 46c6-2 12 1 18-1" fill="none" stroke="#9c3d1c" strokeWidth="2" strokeLinecap="round" opacity=".45" />
        <ellipse cx="22" cy="24" rx="4" ry="3" fill="#b04a22" opacity=".55" />
        <ellipse cx="42" cy="44" rx="5" ry="3.5" fill="#a0421d" opacity=".5" />
        <ellipse cx="44" cy="20" rx="2.4" ry="1.8" fill="#b04a22" opacity=".5" />
        <ellipse cx="30" cy="5.5" rx="13" ry="4.5" fill="#fbe7dc" opacity=".8" />
        <circle cx="32" cy="32" r="30" fill={`url(#${id}shade)`} />
      </g>
    </svg>
  );
}

/** A friendly floating astronaut, line art in the theme colours, waving, with a heartbeat on the chest panel. */
export function AstronautArt({ width = 150 }: { width?: number }) {
  const id = useId();
  const line = "var(--color-ink-2)";
  const fill = "var(--color-surface)";
  // A limb is drawn twice: a wide outline stroke, then a narrower fill stroke on top, which reads as an outlined tube.
  const Tube = ({ d, w = 11 }: { d: string; w?: number }) => (
    <>
      <path d={d} fill="none" stroke={line} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
      <path d={d} fill="none" stroke={fill} strokeWidth={w - 3.6} strokeLinecap="round" strokeLinejoin="round" />
    </>
  );
  return (
    <svg width={width} viewBox="0 0 160 140" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}visor`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#3b82f6" />
          <stop offset="1" stopColor="#1e1b4b" />
        </linearGradient>
      </defs>
      {/* stars */}
      <g fill="var(--color-brand)" opacity=".7">
        <path d="M24 30l1.4 3.4 3.4 1.4-3.4 1.4L24 39.6l-1.4-3.4-3.4-1.4 3.4-1.4z" />
        <path d="M136 22l1 2.4 2.4 1-2.4 1-1 2.4-1-2.4-2.4-1 2.4-1z" />
        <path d="M140 96l1.2 2.8 2.8 1.2-2.8 1.2-1.2 2.8-1.2-2.8-2.8-1.2 2.8-1.2z" />
        <circle cx="18" cy="86" r="1.6" /><circle cx="124" cy="58" r="1.4" /><circle cx="40" cy="12" r="1.2" />
      </g>
      {/* tether curl */}
      <path d="M104 82c14 4 22 14 18 24s-16 8-14-2 18-10 26 2" fill="none" stroke={line} strokeWidth="1.6" strokeDasharray="3 4" strokeLinecap="round" opacity=".6" />
      {/* legs */}
      <Tube d="M70 100l-6 18" />
      <Tube d="M88 100l8 16" />
      <rect x="55" y="114" width="16" height="10" rx="5" fill={fill} stroke={line} strokeWidth="1.8" transform="rotate(10 63 119)" />
      <rect x="90" y="112" width="16" height="10" rx="5" fill={fill} stroke={line} strokeWidth="1.8" transform="rotate(-20 98 117)" />
      {/* backpack + antenna */}
      <path d="M100 52l8-16" stroke={line} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="108" cy="35" r="2.6" fill="var(--color-bad)" />
      <rect x="52" y="54" width="56" height="46" rx="11" fill="var(--color-surface-3)" stroke={line} strokeWidth="1.8" />
      {/* back arm (down) */}
      <Tube d="M98 70l12 12 2 12" />
      <circle cx="112" cy="96" r="5.5" fill={fill} stroke={line} strokeWidth="1.8" />
      {/* torso */}
      <rect x="58" y="58" width="44" height="46" rx="14" fill={fill} stroke={line} strokeWidth="1.8" />
      <rect x="68" y="74" width="24" height="15" rx="4" fill="var(--color-surface-2)" stroke={line} strokeWidth="1.5" />
      <path d="M71 82h4l2-4 3 7 2-3h7" fill="none" stroke="var(--color-ok)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="74" cy="95" r="1.8" fill="var(--color-brand)" /><circle cx="80" cy="95" r="1.8" fill="var(--color-warn)" /><circle cx="86" cy="95" r="1.8" fill="var(--color-ok)" />
      {/* front arm (waving) */}
      <Tube d="M62 70l-16-10-4-16" />
      <circle cx="42" cy="40" r="6" fill={fill} stroke={line} strokeWidth="1.8" />
      <path d="M33 30c-2-2-2-5 0-7M29 33c-4-3-4-9 0-12" fill="none" stroke="var(--color-brand)" strokeWidth="1.6" strokeLinecap="round" opacity=".7" />
      {/* helmet */}
      <circle cx="80" cy="40" r="25" fill={fill} stroke={line} strokeWidth="1.8" />
      <rect x="64" y="60" width="32" height="7" rx="3.5" fill="var(--color-surface-3)" stroke={line} strokeWidth="1.6" />
      <rect x="62" y="27" width="36" height="27" rx="13.5" fill={`url(#${id}visor)`} />
      <path d="M68 36c2-4 6-5 10-5" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" opacity=".75" />
      <circle cx="90" cy="47" r="2" fill="#fff" opacity=".45" />
    </svg>
  );
}

/** Crew avatar: a helmet with the person's initials on the visor, on their own colour. */
export function HelmetAvatar({ name, size = 40, color }: { name: string; size?: number; color: string }) {
  const id = useId();
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" style={{ flex: "none", display: "block" }}>
      <defs>
        <clipPath id={`${id}c`}><circle cx="20" cy="20" r="20" /></clipPath>
        <linearGradient id={`${id}bg`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={color} />
          <stop offset="1" stopColor={color} stopOpacity=".72" />
        </linearGradient>
        <linearGradient id={`${id}v`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1e293b" />
          <stop offset="1" stopColor="#0b1020" />
        </linearGradient>
      </defs>
      <g clipPath={`url(#${id}c)`}>
        <rect width="40" height="40" fill={`url(#${id}bg)`} />
        <path d="M5 41c0-8 6.5-12.5 15-12.5S35 33 35 41z" fill="#eef2f8" />
        <path d="M14 30.5h12" stroke="#c7d0de" strokeWidth="1.4" />
        <circle cx="20" cy="17.5" r="11.5" fill="#f8fafc" />
        <rect x="11.5" y="11.5" width="17" height="12.5" rx="6.25" fill={`url(#${id}v)`} />
        <path d="M14 15c.8-1.5 2.3-2 3.8-2" fill="none" stroke="#fff" strokeOpacity=".55" strokeWidth="1.1" strokeLinecap="round" />
        <text x="20" y="20.6" textAnchor="middle" fontSize="6.6" fontWeight="700" fill="#fff" fontFamily="Inter Variable, system-ui, sans-serif" letterSpacing=".2">{initials}</text>
      </g>
    </svg>
  );
}

/** Empty state: a calm planet with a check badge. */
export function AllClearArt({ size = 96 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 96 96" aria-hidden="true">
      <circle cx="48" cy="48" r="44" fill="var(--color-ok-soft)" />
      <circle cx="48" cy="48" r="32" fill="none" stroke="var(--color-ok)" strokeOpacity=".25" strokeWidth="1.5" strokeDasharray="3 5" />
      <circle cx="48" cy="48" r="20" fill="var(--color-surface)" stroke="var(--color-ok)" strokeWidth="2" />
      <path d="M39 48.5l6 6 12-12.5" fill="none" stroke="var(--color-ok)" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="80" cy="34" r="4" fill="var(--color-brand)" opacity=".8" />
      <path d="M18 24l1.2 2.8 2.8 1.2-2.8 1.2L18 32l-1.2-2.8L14 28l2.8-1.2z" fill="var(--color-ok)" />
      <circle cx="20" cy="70" r="2" fill="var(--color-ok)" opacity=".6" />
    </svg>
  );
}
