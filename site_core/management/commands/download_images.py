"""Download every WordPress upload the imported content uses into media/uploads/ (skips files already present)."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

CACHE = Path(settings.BASE_DIR) / "import_cache"
DEST = Path(settings.MEDIA_ROOT) / "uploads"


def fetch(url):
    rel = unquote(urlparse(url).path).split("/wp-content/uploads/", 1)[-1]
    target = DEST / rel
    if target.exists() and target.stat().st_size:
        return url, "exists"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "ISU-ARMAC site migration"})
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
            return url, f"HTTP {r.status_code}"
        target.write_bytes(r.content)
        return url, "ok"
    except requests.RequestException as e:
        return url, str(e)


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **opts):
        urls = json.loads((CACHE / "images.json").read_text())
        failed = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for url, status in pool.map(fetch, urls):
                if status not in ("ok", "exists"):
                    failed[url] = status
        (CACHE / "image_failures.json").write_text(json.dumps(failed, indent=1))
        self.stdout.write(f"{len(urls)} images, {len(failed)} failed")
