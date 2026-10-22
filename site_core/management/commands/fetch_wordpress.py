"""Download pages, posts, categories and media metadata from the live WordPress site into import_cache/."""
import json
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

API = "https://isu-armac.com/wp-json/wp/v2"
CACHE = Path(settings.BASE_DIR) / "import_cache"


class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **opts):
        CACHE.mkdir(exist_ok=True)
        session = requests.Session()
        session.headers["User-Agent"] = "ISU-ARMAC site migration"
        for kind, params in [
            ("pages", {"_fields": "id,slug,link,parent,title,content,excerpt,date,modified,menu_order,featured_media,status"}),
            ("posts", {"_fields": "id,slug,link,title,content,excerpt,date,modified,categories,featured_media,status"}),
            ("categories", {"_fields": "id,name,slug,count"}),
            ("media", {"_fields": "id,source_url,alt_text,media_details.width,media_details.height"}),
        ]:
            items, page = [], 1
            while True:
                r = session.get(f"{API}/{kind}", params={**params, "per_page": 100, "page": page}, timeout=60)
                r.raise_for_status()
                batch = r.json()
                items.extend(batch)
                if page >= int(r.headers.get("X-WP-TotalPages", 1)):
                    break
                page += 1
            (CACHE / f"{kind}.json").write_text(json.dumps(items))
            self.stdout.write(f"{kind}: {len(items)}")
