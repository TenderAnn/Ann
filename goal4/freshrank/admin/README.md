# Freshrank Admin & Observability Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/rerank?regulatory=on/off` | POST | Main rerank API. Query string or `X-Regulatory` header can force regulatory weighting on/off per request (body field `regulatory` is the default). |
| `/admin/reload-config` | POST | Hot-reloads `ranking_rules.yaml`, `weights.yaml` and the regulatory tag index without restarting the service. Returns reload timestamp. |
| `/metrics/regulatory` | GET | Exposes running tag hit counts and histograms of `w_regulatory` values for the most recent 1,000 scored documents. Useful for drift/coverage monitoring. |

## Usage Notes
1. **Hot reload**: update YAML/lexicon files, then call `/admin/reload-config` before serving traffic.
2. **Gray release**: set `X-Regulatory: off` on a subset of traffic (or `?regulatory=off`) to compare behaviors without redeploying.
3. **Monitoring**: scrape `/metrics/regulatory` to feed dashboards/alerts (e.g., unexpected drop of ESG hits or spike in zero `w_regulatory`).
