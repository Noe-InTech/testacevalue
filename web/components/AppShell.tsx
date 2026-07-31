"use client";

import { useState } from "react";

import { BaseballDashboard } from "@/components/BaseballDashboard";
import { Dashboard } from "@/components/Dashboard";
import { NbaDashboard } from "@/components/NbaDashboard";
import { WnbaDashboard } from "@/components/WnbaDashboard";
import type { SportKey } from "@/lib/types";

/** Foot temporairement désactivé (scrape trop lourd pour la VM). */
const ENABLED_SPORTS: SportKey[] = ["tennis", "wnba", "nba", "baseball"];

export function AppShell() {
  const [sport, setSport] = useState<SportKey>("tennis");
  const activeSport = ENABLED_SPORTS.includes(sport) ? sport : "tennis";

  return (
    <main className="page">
      <div className="sport-tabs">
        <button
          type="button"
          className={`sport-tab${activeSport === "tennis" ? " active" : ""}`}
          onClick={() => setSport("tennis")}
        >
          Tennis
        </button>
        <button
          type="button"
          className={`sport-tab${activeSport === "wnba" ? " active" : ""}`}
          onClick={() => setSport("wnba")}
        >
          WNBA
        </button>
        <button
          type="button"
          className={`sport-tab${activeSport === "nba" ? " active" : ""}`}
          onClick={() => setSport("nba")}
        >
          NBA
        </button>
        <button
          type="button"
          className={`sport-tab${activeSport === "baseball" ? " active" : ""}`}
          onClick={() => setSport("baseball")}
        >
          Baseball
        </button>
      </div>

      {activeSport === "tennis" ? (
        <Dashboard embedded />
      ) : activeSport === "wnba" ? (
        <WnbaDashboard />
      ) : activeSport === "nba" ? (
        <NbaDashboard />
      ) : (
        <BaseballDashboard />
      )}
    </main>
  );
}
