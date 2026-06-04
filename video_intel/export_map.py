"""Build a standalone interactive map of every video that has a geocoded
location. Renders with the Google Maps JavaScript API when GOOGLE_MAPS_API_KEY
is set; otherwise falls back to Leaflet + OpenStreetMap (no key). Markers are
colored by platform; each popup links to the video and to Google Maps."""
import html
import json
from . import config, store

PLATFORM_COLORS = {
    "ig": "#c8472f", "tt": "#1f8f8a", "yt": "#cf2e2e", "fb": "#2f5fa8",
    "xx": "#1c1c1c", "rd": "#cf5a2e", "other": "#3f6b5c",
}

_STYLE = """
<style>
  :root{--paper:#f7f1e6;--paper2:#fdfaf3;--ink:#211d18;--ink-soft:#5c544a;--line:#e2d8c6;--persimmon:#c8472f;--serif:'Fraunces',Georgia,serif;--sans:'Hanken Grotesk',system-ui,sans-serif}
  *{box-sizing:border-box}html,body{margin:0;height:100%}
  body{font-family:var(--sans);color:var(--ink);background:var(--paper)}
  header{position:fixed;top:0;left:0;right:0;z-index:1000;background:var(--paper2);
    border-bottom:1.5px solid var(--line);padding:12px 18px;display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
  header h1{font-family:var(--serif);font-weight:600;font-size:1.25rem;margin:0}
  header .count{color:var(--ink-soft);font-size:.85rem;font-weight:600}
  header .links{margin-left:auto;font-size:.85rem}
  header .links a{color:var(--persimmon);font-weight:700;text-decoration:none}
  #map{position:absolute;top:52px;left:0;right:0;bottom:0}
  .leaflet-popup-content{font-family:var(--sans);margin:12px 14px;line-height:1.45}
  .pop{max-width:260px;font-family:var(--sans);line-height:1.45}
  .pop-creator{font-weight:800;font-size:.95rem}
  .pop-creator .at{color:var(--persimmon)}
  .pop-topic{display:inline-block;font-size:.62rem;font-weight:800;letter-spacing:.05em;
    text-transform:uppercase;color:var(--ink-soft);background:#efe7d6;border-radius:6px;padding:2px 7px;margin:5px 0}
  .pop-sum{font-size:.84rem;color:var(--ink);margin:5px 0}
  .pop-loc{font-size:.76rem;color:var(--ink-soft);margin:4px 0}
  .pop-links{margin-top:7px;display:flex;gap:10px;font-size:.8rem;font-weight:700}
  .pop-links a{text-decoration:none;color:var(--persimmon)}
  .pop-links a.map{color:#3f6b5c}
  .legend{background:var(--paper2);border:1.5px solid var(--line);border-radius:10px;padding:8px 10px;margin:10px;
    font-size:.76rem;line-height:1.7;box-shadow:0 2px 10px rgba(0,0,0,.08)}
  .legend .row{display:flex;align-items:center;gap:7px}
  .legend .dot{width:11px;height:11px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 0 1px #ccc}
  .empty{position:absolute;top:50%;left:0;right:0;text-align:center;color:var(--ink-soft);font-family:var(--serif);font-size:1.1rem;padding:0 20px}
</style>
"""

_HELPERS = """
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function gmap(loc){return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(loc);}
function popup(d){
  var links='<a href="'+esc(d.url)+'" target="_blank" rel="noopener">Watch &rarr;</a>'
          + '<a class="map" href="'+gmap(d.location)+'" target="_blank" rel="noopener">Google Maps</a>';
  return '<div class="pop"><div class="pop-creator"><span class="at">@</span>'+esc(d.creator)+'</div>'
    + '<span class="pop-topic">'+esc(d.topic)+'</span>'
    + (d.summary?'<div class="pop-sum">'+esc(d.summary)+'</div>':'')
    + '<div class="pop-loc">'+esc(d.location)+'</div>'
    + '<div class="pop-links">'+links+'</div></div>';
}
function legendHTML(used){
  var h=''; Object.keys(used).forEach(function(p){
    h+='<div class="row"><span class="dot" style="background:'+used[p]+'"></span>'+esc(p)+'</div>';
  }); return h;
}
"""


def _head(title, fonts, extra=""):
    return ('<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">'
            '<title>' + html.escape(title) + '</title><meta name="theme-color" content="#c8472f">'
            + fonts + extra + _STYLE + '</head>')


def _header_bar(title, count, guide_href="video_guide.html"):
    return ('<header><h1>' + html.escape(title) + '</h1><span class="count">'
            + str(count) + ' mapped</span>'
            '<span class="links"><a href="' + html.escape(guide_href) + '">&larr; Back to guide</a></span></header>')


def _leaflet_doc(rows, title, fonts, guide_href="video_guide.html"):
    extra = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>'
             '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')
    body = (
        '<body>' + _header_bar(title, len(rows), guide_href) + '<div id="map"></div><script>'
        'var DATA = ' + json.dumps(rows) + ';'
        'var COLORS = ' + json.dumps(PLATFORM_COLORS) + ';'
        + _HELPERS +
        "var map = L.map('map');"
        "L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',"
        "{maxZoom:19, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);"
        "if(!DATA.length){"
        "document.body.insertAdjacentHTML('beforeend','<div class=\\\"empty\\\">No mapped locations yet.</div>');"
        "map.setView([20,0],2);"
        "} else {"
        "var markers=[], used={};"
        "DATA.forEach(function(d){"
        "var color = COLORS[d.cls] || COLORS.other; used[d.platform]=color;"
        "var m = L.circleMarker([d.lat,d.lng],{radius:8,weight:2,color:'#fff',fillColor:color,fillOpacity:.95});"
        "m.bindPopup(popup(d),{maxWidth:280}); m.addTo(map); markers.push(m);"
        "});"
        "map.fitBounds(L.featureGroup(markers).getBounds().pad(0.15));"
        "setTimeout(function(){map.invalidateSize();},250);"
        "window.addEventListener('resize',function(){map.invalidateSize();});"
        "var legend = L.control({position:'bottomright'});"
        "legend.onAdd = function(){ var div=L.DomUtil.create('div','legend'); div.innerHTML=legendHTML(used); return div; };"
        "legend.addTo(map);"
        "}"
        '</script></body></html>'
    )
    return _head(title, fonts, extra) + body


def _google_doc(rows, title, fonts, key, guide_href="video_guide.html"):
    # NOTE: the Maps JS key is embedded in this local HTML file. Restrict it in
    # the Google Cloud console (API + quota limits) before sharing the file.
    body = (
        '<body>' + _header_bar(title, len(rows), guide_href) + '<div id="map"></div><script>'
        'var DATA = ' + json.dumps(rows) + ';'
        'var COLORS = ' + json.dumps(PLATFORM_COLORS) + ';'
        + _HELPERS +
        "function initMap(){"
        "var map = new google.maps.Map(document.getElementById('map'),"
        "{zoom:12, center:{lat:37.5563,lng:126.9920}, mapTypeControl:true, streetViewControl:true});"
        "if(!DATA.length){"
        "document.body.insertAdjacentHTML('beforeend','<div class=\\\"empty\\\">No mapped locations yet.</div>');"
        "map.setZoom(2); map.setCenter({lat:20,lng:0}); return;"
        "}"
        "var bounds = new google.maps.LatLngBounds();"
        "var info = new google.maps.InfoWindow();"
        "var used = {};"
        "DATA.forEach(function(d){"
        "var color = COLORS[d.cls] || COLORS.other; used[d.platform]=color;"
        "var marker = new google.maps.Marker({position:{lat:d.lat,lng:d.lng}, map:map, title:d.creator,"
        "icon:{path:google.maps.SymbolPath.CIRCLE, scale:8, fillColor:color, fillOpacity:0.95, strokeColor:'#fff', strokeWeight:2}});"
        "marker.addListener('click',function(){ info.setContent(popup(d)); info.open(map,marker); });"
        "bounds.extend(marker.getPosition());"
        "});"
        "if(DATA.length>1){ map.fitBounds(bounds); } else { map.setCenter(bounds.getCenter()); map.setZoom(15); }"
        "var legend = document.createElement('div'); legend.className='legend'; legend.innerHTML=legendHTML(used);"
        "map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(legend);"
        "}"
        "window.gm_authFailure = function(){"
        "document.body.insertAdjacentHTML('beforeend','<div class=\\\"empty\\\">Google Maps could not authenticate this key. "
        "Enable the <b>Maps JavaScript API</b> for this key (and the <b>Geocoding API</b> for lookups), then rebuild.</div>');"
        "};"
        '</script>'
        '<script async src="https://maps.googleapis.com/maps/api/js?key='
        + html.escape(key) + '&callback=initMap&loading=async"></script>'
        '</body></html>'
    )
    return _head(title, fonts) + body


def _gather(videos=None):
    rows = []
    for v in (store.all_videos() if videos is None else videos):
        lat, lng = v.get("lat"), v.get("lng")
        if lat in (None, "") or lng in (None, ""):
            continue
        rows.append({
            "lat": float(lat), "lng": float(lng),
            "creator": v.get("creator") or "Unknown",
            "topic": v.get("topic") or "Other",
            "platform": v.get("platform") or "Other",
            "cls": v.get("cls") or "other",
            "summary": v.get("summary") or "",
            "location": v.get("location") or "",
            "url": v.get("url") or "",
        })
    return rows


def build(path=None, title=None, rows=None, guide_href="video_guide.html", force_osm=False):
    from .guide_assets import FONTS
    path = str(path or config.MAP_PATH)
    title = title or (config.GUIDE_TITLE + " \u2014 Map")
    if rows is None:
        rows = _gather()

    if (not force_osm) and config.use_google_map() and config.GOOGLE_MAPS_API_KEY:
        doc = _google_doc(rows, title, FONTS, config.GOOGLE_MAPS_API_KEY, guide_href)
        provider = "google"
    else:
        doc = _leaflet_doc(rows, title, FONTS, guide_href)
        provider = "osm"

    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path, len(rows), provider
