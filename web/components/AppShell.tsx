"use client";

import { useState } from "react";

import { Dashboard } from "@/components/Dashboard";
import { WnbaDashboard } from "@/components/WnbaDashboard";
import type { SportKey } from "@/lib/types";

export function AppShell() {
  const [sport, setSport] = useState<SportKey>("tennis");

  return (
    <main className="page">
      <div className="sport-tabs">
        <button
          type="button"
          className={`sport-tab${sport === "tennis" ? " active" : ""}`}
          onClick={() => setSport("tennis")}
        >
          Tennis
        </button>
        <button
          type="button"
          className={`sport-tab${sport === "wnba" ? " active" : ""}`}
          onClick={() => setSport("wnba")}
        >
          WNBA
        </button>
      </div>

      {sport === "tennis" ? <Dashboard embedded /> : <WnbaDashboard />}
    </main>
  );
}
