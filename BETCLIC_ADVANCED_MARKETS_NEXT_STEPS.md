# Betclic advanced markets: current state

## What is confirmed

- The public match page `ng-state` contains an `app-context` object with:
  - `grpcOfferingUrl = https://offering.begmedia.com/web/offering.access.api`
  - `grpcGordonTier2Url = https://gordon-kplfs.begmedia.com`
  - `grpcGordonTier3Url = https://gordon-spcjo.begmedia.com`
- The same public page sets an anonymous `BC-TOKEN` cookie.
- The SSR payload for match `1163187647176704` exposes:
  - `openMarketCount = 93`
  - only `7-9` preloaded markets in `subCategories`
  - category tabs:
    - `ca_ten_top`
    - `ca_ten_rslt`
    - `ca_ten_sts`
    - `ca_ten_gms`
    - `ca_ten_ptss` (`Points & Service`)
- The front JS defines:
  - `offering.access.api.MatchService`
  - `GetMatchWithNotification`
  - request fields `match_id`, `language`, optional `category_id`, `supported_features`
- The grpc-web transport builds URLs as:
  - ``${baseUrl}/${service.typeName}/${method.name}``
- The grpc-web transport defaults to `application/grpc-web-text`.

## Why this is still blocked

- Reconstructed direct POST calls to the Offering endpoint still return `404` from Python:
  - both binary and text grpc-web modes were tried
  - several path suffix variants were tried
  - the anonymous `BC-TOKEN` bearer token was included
- A direct `/kong/api/v3/handshake` replay outside the browser still returns `403`.

## Most likely explanation

The missing Betclic advanced markets are very likely loaded on demand per category, probably via:

- `GetMatchWithNotification(match_id, category_id="ca_ten_ptss")`

but one of these still differs from the browser reality:

- exact endpoint path
- exact grpc-web request formatting
- required browser headers / fetch mode / cookies
- a second token or correlation header added by runtime code

## Concrete next step

Capture one real browser request for the `Points & Service` tab and diff it against the current probe:

1. Open a Betclic tennis match page in a real browser.
2. Open DevTools Network.
3. Click the `Points & Service` tab.
4. Capture the exact request:
   - URL
   - method
   - request headers
   - content-type
   - body encoding
   - response content-type
5. Replay that request in Python.

If one real request is captured, the remaining work is mechanical:

1. implement `get_event_markets_by_category(category_id)`
2. fetch all categories for each Betclic match
3. normalize `aces`, `breaks`, `tie-break`, `service` families
4. rerun `compare_tennis_books.py`
5. export advanced-only reports

## Useful probe files already added

- `probe_betclic_transport.py`
- `probe_betclic_gordon_service.py`
- `probe_betclic_grpc_url.py`
- `probe_betclic_offering.py`
- `replay_betclic_captured_request.py`

## Useful reporting files

- `export_unibet_advanced_gaps.py`
