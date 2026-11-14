import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "./styles.css";
import { Layout } from "./components/Layout";
import { ReplayProvider } from "./state/replay";
import { CheckInProvider } from "./state/checkin";
import { Skeleton } from "./components/ui";

// Pages (and the charting library most of them use) load when opened.
const Today = lazy(() => import("./pages/Today").then((m) => ({ default: m.Today })));
const Body = lazy(() => import("./pages/Body").then((m) => ({ default: m.Body })));
const Eyes = lazy(() => import("./pages/Eyes").then((m) => ({ default: m.Eyes })));
const Cabin = lazy(() => import("./pages/Cabin").then((m) => ({ default: m.Cabin })));
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));
const Learn = lazy(() => import("./pages/Learn").then((m) => ({ default: m.Learn })));
const About = lazy(() => import("./pages/About").then((m) => ({ default: m.About })));
const page = (el: React.ReactNode) => <Suspense fallback={<Skeleton lines={6} height={28} />}>{el}</Suspense>;

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ReplayProvider>
          <CheckInProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={page(<Today />)} />
              <Route path="body" element={page(<Body />)} />
              <Route path="eyes" element={page(<Eyes />)} />
              <Route path="cabin" element={page(<Cabin />)} />
              <Route path="doctor" element={page(<Reports />)} />
              <Route path="settings" element={page(<Settings />)} />
              <Route path="learn" element={page(<Learn />)} />
              <Route path="about" element={page(<About />)} />
              <Route path="*" element={<p className="text-ink-2">That page does not exist. Go back to Today.</p>} />
            </Route>
          </Routes>
          </CheckInProvider>
        </ReplayProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
