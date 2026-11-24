# Safety review and automatic approval

Every deployment request gets a safety review before anything is built. A request that passes completes with no one clicking Approve.

## Who decides

* **Rules decide.** A deterministic scan of exactly the files that would be published produces findings: `block` (never deploy), `review` (a person must look), `warn` and `info` (shown, no effect).
* **The AI can only make the outcome stricter.** It reads the flagged material and may add concerns. A *high* concern becomes a `review` finding; it can never clear or lower anything the rules found, because repository text is untrusted and can simply claim "this is safe". It never sees secret values.
* **If an AI provider is configured but fails or answers with junk, the request goes to a person** instead of being approved without the second opinion. With no provider configured, the rules alone decide.
* **Only a plain static site that passes is approved automatically.** Anything that would run code, or whose review could not be completed, is sent to an operator. Static requests fail closed: no review, no deployment.

## What the rules look for (static sites)

| Finding | Effect |
| --- | --- |
| Specific token formats (private keys, AWS, GitHub, Slack, Stripe, Google, OpenAI) in a file that would be published | block |
| No `index.html` at the root, `public/`, `dist/` or `build/` (so it is not a static site) | block |
| Paths that escape the archive, or more than one top-level folder | block |
| Generic `password = "..."`-style strings, in-browser miners, scripts that decode and run hidden code, huge encoded blobs, password forms posting to another site, hidden iframes, scripts over plain HTTP, scripts inside SVG, repositories over the size limits | review |
| Secret-looking files that are not published (`.env`, keys), other sites' scripts | warn / info |

Projects that would run code always need an operator, and the report lists install hooks, `curl | sh` in a Dockerfile and containers that never drop root.

## Reviewed is published

The same rules run again on the exact archive the publisher downloads. A branch changed after review fails the build if it now has a blocking finding, or (for automatically approved requests) any finding that would have needed a person.

## Where you see it

* Deployments → New: *Analyse repository* shows the decision before you submit.
* The deployment page shows the report, who approved it, and the AI's summary.
* A finding never contains a secret value: only the kind, file and line.

## Limits

A clean review means "no known issues found", not "safe". It cannot judge intent, and the rules are heuristics that will miss novel attacks and sometimes flag harmless code. That is why it only auto-approves static assets served from their own origin, and why running code needs the isolated worker as well.
