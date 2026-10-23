"""Save each live page's <title> and meta description to import_cache/seo.json (Rank Math data is not in the REST API)."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand

CACHE = Path(settings.BASE_DIR) / "import_cache"


def head_for(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "ISU-ARMAC site migration"})
        soup = BeautifulSoup(r.text, "lxml")
        desc = soup.find("meta", attrs={"name": "description"})
        return url, {
            "status": r.status_code,
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "description": desc.get("content", "").strip() if desc else "",
        }
    except requests.RequestException as e:
        return url, {"status": 0, "error": str(e)}


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **opts):
        out = CACHE / "seo.json"
        seo = json.loads(out.read_text()) if out.exists() else {}
        urls = [p["link"] for kind in ("pages", "posts") for p in json.loads((CACHE / f"{kind}.json").read_text())]
        todo = [u for u in urls if seo.get(u, {}).get("status") != 200]
        with ThreadPoolExecutor(max_workers=20) as pool:
            for i, (url, data) in enumerate(pool.map(head_for, todo), 1):
                seo[url] = data
                if i % 100 == 0:
                    out.write_text(json.dumps(seo))
                    self.stdout.write(f"{i}/{len(todo)}")
        out.write_text(json.dumps(seo))
        bad = [u for u, d in seo.items() if d.get("status") != 200]
        self.stdout.write(f"done: {len(seo)} urls, {len(bad)} not OK")
