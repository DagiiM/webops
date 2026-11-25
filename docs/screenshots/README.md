# Screenshots

The images in this folder are used by the main [README](../../README.md). Everything on screen is **fictional demo
data** (the `acme` organisation, its repositories, the demo user and keys). They were captured from a throw-away
database, never from a real installation.

Two things in them are not live data, and the captions say so where it matters:

* The *new deployment* safety review is a mocked response, because the demo repository does not exist. It has exactly the
  shape the panel produces (`apps/deployments/services/ai_assist.py`).
* The managed databases are real (PostgreSQL, Redis, SQLite instances started for the capture), so their *Running*
  badges are genuine.

## Regenerate them

You need the repository's development environment (see the main README), PostgreSQL and Redis installed, Node with
Playwright (`npm i -g playwright`, then `playwright install chromium`) and a **non-root** user to run the server
(PostgreSQL and Redis refuse to run as root).

```bash
# 1. An empty database that only this recipe will ever touch
createdb woshots
export DATABASE_URL=postgresql://USER:PASS@127.0.0.1:5432/woshots WEBOPS_INSTALL_PATH=/some/writable/dir
cd control-panel && python manage.py migrate
python manage.py shell < ../docs/screenshots/tools/seed_demo.py      # refuses to run on a database that has users

# 2. Run the server as the non-root user, in the modes the screenshots show
WEBOPS_RUNTIME=supervisor WEBOPS_WORKLOAD_POLICY=restricted python manage.py runserver 127.0.0.1:8767 --noreload

# 3. Capture (webops.example is mapped to 127.0.0.1 by the browser, so URLs on screen look neutral)
export WEBOPS_SHELL_CMD="python manage.py shell < %s"                 # runs tools/ids.py inside the panel's Django shell
cd ../docs/screenshots/tools && node capture.js http://webops.example:8767 ..
```

The capture deploys three real managed databases through the real page, loads each page once (the panel's own
rate limiter counts every request), hides toast notifications, and writes `NN-name.png` files. Reduce the size
afterwards with a palette quantiser (about 70% smaller, visually identical for flat UI):

```python
from PIL import Image
Image.open(f).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
```

`tools/` holds the seed data (`seed_demo.py`), the helper that refreshes the demo worker's heartbeat (`ids.py`) and the
capture script (`capture.js`). They are documentation tooling only: nothing in the product depends on them, and the
frontend itself still has no build step.
