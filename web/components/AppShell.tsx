"use client";

import { useState } from "react";

import { BaseballDashboard } from "@/components/BaseballDashboard";
import { Dashboard } from "@/components/Dashboard";
import { NbaDashboard } from "@/components/NbaDashboard";
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
        <button
          type="button"
          className={`sport-tab${sport === "nba" ? " active" : ""}`}
          onClick={() => setSport("nba")}
        >
          NBA
        </button>
        <button
          type="button"
          className={`sport-tab${sport === "baseball" ? " active" : ""}`}
          onClick={() => setSport("baseball")}
        >
          Baseball
        </button>
      </div>

      {sport === "tennis" ? (
        <Dashboard embedded />
      ) : sport === "wnba" ? (
        <WnbaDashboard />
      ) : sport === "nba" ? (
        <NbaDashboard />
      ) : (
        <BaseballDashboard />
      )}
    </main>
  );
}
