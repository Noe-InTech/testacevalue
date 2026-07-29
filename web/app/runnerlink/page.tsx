import type { Metadata } from "next";

import { RunnerStatus } from "@/components/RunnerStatus";

export const metadata: Metadata = {
  title: "Runner link",
  robots: {
    index: false,
    follow: false,
  },
};

export default function RunnerLinkPage() {
  return (
    <main className="page runnerlink-page">
      <header className="hero">
        <p className="eyebrow">Privé</p>
        <h1>Lien runner</h1>
        <p className="lead">
          Page non liée depuis l’accueil. Code secret requis. Tu peux aussi mettre à jour le runner
          depuis ici.
        </p>
      </header>
      <RunnerStatus standalone />
    </main>
  );
}
