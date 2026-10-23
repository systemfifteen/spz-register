#!/usr/bin/env python3
"""Grafana dashboard „SPZ – registrácia vozidiel“ (uid adtgcdz) → spz.json.
Prevádzka appky z /metrics (prometheus-fastapi-instrumentator). Návštevnosť rieši Umami (stats.system15.win).
Voliteľne (--stats): súhrny používateľov a stav zálohy z textfile metrík spz_* (node_exporter)."""
import json, sys
DS = {"type": "prometheus", "uid": sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "eff0zxq6sk64gc"}
WITH_STATS = "--stats" in sys.argv
S = 'job="spz"'
REAL = f'{S},handler!~"/metrics|/health"'
panels, pid = [], [0]
def nid(): pid[0] += 1; return pid[0]
def th(*s):
    out = [{"color": s[0], "value": None}]
    for i in range(1, len(s), 2): out.append({"color": s[i + 1], "value": s[i]})
    return {"mode": "absolute", "steps": out}
def tgt(expr, legend="__auto", ref="A", instant=False, interval=None):
    t = {"refId": ref, "expr": expr, "legendFormat": legend, "datasource": DS}
    if instant: t.update(instant=True, range=False)
    if interval: t["interval"] = interval
    return t
def row(title, y):
    panels.append({"type": "row", "id": nid(), "title": title, "collapsed": False, "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})
def stat(title, x, y, w, targets, unit="none", thr=None, mappings=None, desc="", decimals=None, h=4, text="auto"):
    d = {"unit": unit, "color": {"mode": "thresholds"}, "thresholds": thr or th("blue")}
    if mappings: d["mappings"] = mappings
    if decimals is not None: d["decimals"] = decimals
    panels.append({"type": "stat", "id": nid(), "title": title, "description": desc, "datasource": DS,
                   "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
                   "fieldConfig": {"defaults": d, "overrides": []},
                   "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                               "colorMode": "value", "graphMode": "none", "textMode": text,
                               "justifyMode": "center", "orientation": "auto", "wideLayout": True}})
def ts(title, x, y, w, h, targets, unit, bars=False, stack=False, desc="", overrides=None, interval=None, minv=0):
    custom = {"drawStyle": "bars" if bars else "line", "lineWidth": 2, "fillOpacity": 80 if bars else 15,
              "gradientMode": "none" if bars else "opacity", "showPoints": "never", "spanNulls": True,
              "stacking": {"mode": "normal" if stack else "none", "group": "A"}, "barAlignment": 0}
    p = {"type": "timeseries", "id": nid(), "title": title, "description": desc, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
         "fieldConfig": {"defaults": dict({"unit": unit, "min": minv, "custom": custom, "color": {"mode": "palette-classic"}}, **({"decimals": 0} if bars else {})),
                         "overrides": overrides or []},
         "options": {"legend": {"displayMode": "list", "placement": "bottom", "calcs": ["sum"] if bars else []},
                     "tooltip": {"mode": "multi", "sort": "desc"}}}
    if interval: p["interval"] = interval
    panels.append(p)
def ov(name, display=None, color=None):
    props = []
    if display: props.append({"id": "displayName", "value": display})
    if color: props.append({"id": "color", "value": {"mode": "fixed", "fixedColor": color}})
    return {"matcher": {"id": "byName", "options": name}, "properties": props}

# ── Stav ────────────────────────────────────────────────────────────────
row("Stav appky (spz.poetika.online)", 0)
stat("Appka", 0, 1, 4, [tgt(f'max(up{{{S}}}) or vector(0)', instant=True)], thr=th("red", 1, "green"),
     mappings=[{"type": "value", "options": {"1": {"text": "BEŽÍ", "color": "green"}, "0": {"text": "NEBEŽÍ", "color": "red"}}}],
     desc="Či Prometheus zastihol appku pri poslednom zbere (každých 15 s).")
stat("Beží bez reštartu", 4, 1, 4, [tgt(f'time() - process_start_time_seconds{{{S}}}', instant=True)], unit="dtdurations",
     desc="Reštartuje sa pri každom deployi.")
stat("Požiadavky za 24 h", 8, 1, 4, [tgt(f'round(sum(increase(http_requests_total{{{REAL}}}[24h])))', instant=True)],
     desc="Bez interných /metrics a /health. Návštevnosť podrobne v Umami (stats.system15.win).")
stat("Chyby servera za 24 h", 12, 1, 4, [tgt(f'round(sum(increase(http_requests_total{{{S},status="5xx"}}[24h]))) or vector(0)', instant=True)],
     thr=th("green", 1, "red"), desc="Odpovede 5xx = chyba v appke. Má byť 0.")
stat("Neúspešné prihlásenia za 24 h", 16, 1, 4,
     [tgt(f'round(sum(increase(http_requests_total{{{S},handler="/token",status="4xx"}}[24h]))) or vector(0)', instant=True)],
     thr=th("green", 5, "orange", 20, "red"),
     desc="Zlé heslo alebo zablokované rate-limitom (5 pokusov/min). Veľa = niekto skúša heslá.")
stat("Odozva p95 za 24 h", 20, 1, 4,
     [tgt(f'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{{REAL}}}[24h])))', instant=True)],
     unit="s", decimals=0, thr=th("green", 0.5, "orange", 2, "red"),
     desc="95 % požiadaviek bolo vybavených rýchlejšie než táto hodnota.")

# ── Prevádzka ───────────────────────────────────────────────────────────
row("Prevádzka", 5)
ts("Požiadavky podľa adresy (za hodinu)", 0, 6, 12, 8,
   [tgt(f'sum by (handler) (increase(http_requests_total{{{REAL}}}[$__interval]))', "{{handler}}", interval="1h")],
   "short", bars=True, stack=True, interval="1h",
   overrides=[ov("none", "neznáma adresa (skenery, 404)", "red"), ov("/", "úvodná stránka", "blue")],
   desc="Bez interných /metrics a /health. „neznáma adresa“ = požiadavky na neexistujúce URL, väčšinou boty.")
ts("Prihlásenia (za hodinu)", 12, 6, 12, 8,
   [tgt(f'sum(increase(http_requests_total{{{S},handler="/token",status="2xx"}}[$__interval])) or vector(0)', "úspešné", "A", interval="1h"),
    tgt(f'sum(increase(http_requests_total{{{S},handler="/token",status="4xx"}}[$__interval])) or vector(0)', "neúspešné", "B", interval="1h")],
   "short", bars=True, stack=True, interval="1h", overrides=[ov("úspešné", color="green"), ov("neúspešné", color="orange")])
ts("Odozva", 0, 14, 12, 7,
   [tgt(f'histogram_quantile(0.5, sum by (le) (rate(http_request_duration_seconds_bucket{{{REAL}}}[1h])))', "medián", "A"),
    tgt(f'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{{{REAL}}}[1h])))', "p95", "B")],
   "s", overrides=[ov("medián", color="green"), ov("p95", color="orange")],
   desc="Kĺzavé okno 1 h. Pri malej návštevnosti môžu byť medzery.")
ts("Zdroje appky", 12, 14, 12, 7,
   [tgt(f'process_resident_memory_bytes{{{S}}}', "pamäť (RAM)", "A")],
   "bytes", overrides=[ov("pamäť (RAM)", color="purple")], desc="Limit kontajnera 256 MB.")

y = 21
if WITH_STATS:
    N = 'job="node"'
    row("Používatelia a záloha (z nočnej zálohy, len počty)", y); y += 1
    stat("Používatelia", 0, y, 4, [tgt(f'sum(spz_users{{{N}}})', instant=True)])
    stat("Admini", 4, y, 3, [tgt(f'spz_users{{{N},role="admin"}}', instant=True)])
    stat("Vozidlá (ŠPZ)", 7, y, 3, [tgt(f'spz_vehicles{{{N}}}', instant=True)])
    stat("S povolením vjazdu", 10, y, 4, [tgt(f'spz_users_with_permission{{{N}}}', instant=True)])
    stat("Aktívni za 30 dní", 14, y, 4, [tgt(f'spz_users_active_30d{{{N}}}', instant=True)], desc="Prihlásili sa aspoň raz za posledných 30 dní.")
    stat("Nikdy neprihlásení", 18, y, 6, [tgt(f'spz_users_never_logged_in{{{N}}}', instant=True)], thr=th("text"),
         desc="Účty, ktoré vznikli (napr. importom), ale ešte sa neprihlásili.")
    y += 4
    stat("Posledná záloha", 0, y, 6, [tgt(f'time() - spz_backup_last_timestamp_seconds{{{N}}}', instant=True)], unit="dtdurations",
         thr=th("green", 93600, "orange", 180000, "red"), desc="Záloha beží každú noc o 3:00. Viac ako 26 h = posledná nočná záloha neprebehla.")
    stat("Počet záloh", 6, y, 4, [tgt(f'spz_backup_count{{{N}}}', instant=True)], desc="Uchováva sa 7 dní.")
    stat("Veľkosť DB", 10, y, 4, [tgt(f'spz_backup_size_bytes{{{N}}}', instant=True)], unit="bytes")
    ts("Prihlásenia za deň (zo zálohy)", 14, y, 10, 6,
       [tgt(f'clamp_min(delta(spz_logins_total{{{N}}}[1d]), 0)', "prihlásenia za 24 h", interval="1d")],
       "short", bars=True, interval="1d", overrides=[ov("prihlásenia za 24 h", color="blue")])

dash = {"uid": "adtgcdz", "title": "SPZ – registrácia vozidiel", "tags": ["spz", "app"],
        "description": "Prevádzka spz.poetika.online. Návštevnosť: Umami.",
        "links": [{"title": "Návštevnosť v Umami", "url": "https://stats.system15.win", "type": "link",
                   "icon": "external link", "targetBlank": True}],
        "timezone": "browser", "refresh": "1m", "time": {"from": "now-7d", "to": "now"},
        "graphTooltip": 1, "editable": True, "schemaVersion": 41, "panels": panels,
        "templating": {"list": []}, "annotations": {"list": []}}
json.dump(dash, sys.stdout, ensure_ascii=False, indent=1)
