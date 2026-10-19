import { BetclicGoClient } from "./BetclicGoClient";

type Search = {
  url?: string | string[];
  u?: string | string[];
  s?: string | string[];
  m?: string | string[];
  k?: string | string[];
};

function one(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return (value[0] || "").trim();
  }
  return (value || "").trim();
}

export default async function GoBetclicPage({
  searchParams,
}: {
  searchParams: Promise<Search> | Search;
}) {
  const params = await Promise.resolve(searchParams);
  const shareUrl = one(params.url);
  const matchUrl = one(params.u);
  const selectionId = one(params.s);
  const matchId = one(params.m);
  const marketId = one(params.k);

  return (
    <BetclicGoClient
      shareUrl={shareUrl}
      matchUrl={matchUrl}
      selectionId={selectionId}
      matchId={matchId}
      marketId={marketId}
    />
  );
}
