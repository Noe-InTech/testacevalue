type Search = {
  o?: string | string[];
  u?: string | string[];
};

function one(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return (value[0] || "").trim();
  }
  return (value || "").trim();
}

function withOutcomeIds(matchUrl: string, outcomeId: string): string {
  try {
    const url = new URL(matchUrl);
    url.searchParams.set("outcomeIds", outcomeId);
    return url.toString();
  } catch {
    const join = matchUrl.includes("?") ? "&" : "?";
    return `${matchUrl}${join}outcomeIds=${encodeURIComponent(outcomeId)}`;
  }
}

export default async function GoUnibetPage({
  searchParams,
}: {
  searchParams: Promise<Search> | Search;
}) {
  const params = await Promise.resolve(searchParams);
  const outcomeId = one(params.o);
  const matchUrl = one(params.u);
  const valid = Boolean(outcomeId && /^\d+$/.test(outcomeId));
  // /sport is NOT in Unibet iOS Universal Links — stays in the browser SPA so
  // deeplinksService can read ?outcomeIds= and addSelections(). Match paths open the app and drop it.
  const sportUrl = valid
    ? `https://www.unibet.fr/sport?outcomeIds=${encodeURIComponent(outcomeId)}`
    : "https://www.unibet.fr/sport";
  const matchWithBet =
    valid && matchUrl ? withOutcomeIds(matchUrl, outcomeId) : matchUrl || sportUrl;

  const bootScript = valid
    ? `(function(){var k=${JSON.stringify(`uni-go:${outcomeId}`)};var sport=${JSON.stringify(sportUrl)};var match=${JSON.stringify(matchWithBet)};try{if(sessionStorage.getItem(k)){location.replace(match||sport);return;}sessionStorage.setItem(k,"1");}catch(e){}location.replace(sport);})();`
    : "";

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 520 }}>
      <h1 style={{ fontSize: "1.25rem", marginBottom: "0.75rem" }}>Unibet</h1>
      <p style={{ marginBottom: "1rem" }}>
        {valid
          ? "Ouverture du pari Unibet (ajout au panier)…"
          : "Lien Unibet invalide (identifiant de sélection manquant)."}
      </p>
      <p style={{ marginBottom: "0.75rem" }}>
        <a href={sportUrl}>Ajouter le pari au panier</a>
      </p>
      {matchUrl ? (
        <p>
          <a href={matchWithBet}>Ouvrir la page match</a>
        </p>
      ) : null}
      {bootScript ? <script dangerouslySetInnerHTML={{ __html: bootScript }} /> : null}
    </main>
  );
}
