"""Build a publishable site for the curated (shared=1) subset.

Output goes to ./docs so it can be served by GitHub Pages directly:
  docs/index.html       -> the guide (landing page)
  docs/video_map.html   -> the map (OpenStreetMap, no API key)
  docs/.nojekyll        -> tell Pages to serve files as-is

The map is always rendered with OpenStreetMap here, so the published files
never contain a Google Maps key.
"""
import os
from . import config, store, export_guide, export_map


def build(title=None, only_shared=True):
    title = title or (config.GUIDE_TITLE)
    os.makedirs(config.SHARE_DIR, exist_ok=True)

    videos = store.shared_videos() if only_shared else store.all_videos()

    index_path = os.path.join(config.SHARE_DIR, "index.html")
    map_path = os.path.join(config.SHARE_DIR, "video_map.html")

    # guide -> index.html, its map button points at the sibling map file
    export_guide.build(path=index_path, title=title, rows=videos, map_href="video_map.html")

    # map -> OSM forced, back-link points at index.html
    points = export_map._gather(videos)
    _, mapped, provider = export_map.build(
        path=map_path, title=title + " \u2014 Map", rows=points,
        guide_href="index.html", force_osm=True,
    )

    # serve as static files on GitHub Pages
    open(os.path.join(config.SHARE_DIR, ".nojekyll"), "w").close()

    return {
        "dir": str(config.SHARE_DIR),
        "index": index_path,
        "map": map_path,
        "videos": len(videos),
        "mapped": mapped,
        "provider": provider,
    }
