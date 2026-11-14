// Whether the daily check-in is open. Any page can open it; the layout draws it.
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

interface CheckInState { open: boolean; show: () => void; hide: () => void }
const Ctx = createContext<CheckInState | null>(null);

export function CheckInProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({ open, show: () => setOpen(true), hide: () => setOpen(false) }), [open]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCheckIn(): CheckInState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCheckIn must be used inside CheckInProvider");
  return ctx;
}
