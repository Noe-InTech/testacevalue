type Search = {
  match?: string | string[];
  b?: string | string[];
  o?: string | string[];
};

function one(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return (value[0] || "").trim();
  }
  return (value || "").trim();
}

export default async function GoWinamaxPage({
  searchParams,
}: {
  searchParams: Promise<Search> | Search;
}) {
  const params = await Promise.resolve(searchParams);
  const match = one(params.match);
  const bet = one(params.b);
  const odd = one(params.o);
  const valid = Boolean(match && bet && odd);
  const wam = valid ? `wam://betting?target=match-${match}&b=${bet}&o=${odd}` : "";
  const web = valid
    ? `https://www.winamax.fr/paris-sportifs/match/${match}#b=${bet}&o=${odd}`
    : "https://www.winamax.fr/paris-sportifs";

  const bootScript = valid
    ? `window.location.href=${JSON.stringify(wam)};setTimeout(function(){window.location.href=${JSON.stringify(web)};},900);`
    : "";

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 520 }}>
      <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Winamax</h1>
      <p style={{ marginBottom: "1rem" }}>
        {valid ? "Ouverture du pari Winamax…" : "Lien Winamax invalide (match / b / o manquants)."}
      </p>
      <p>
        <a href={web}>Continuer sur Winamax</a>
      </p>
      {bootScript ? <script dangerouslySetInnerHTML={{ __html: bootScript }} /> : null}
    </main>
  );
}
