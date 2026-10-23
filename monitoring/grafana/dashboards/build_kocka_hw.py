#!/usr/bin/env python3
"""Generuje Grafana dashboard „Kocka – hardvér“ (uid kocka-hw) → kocka-hw.json.
Dáta: prometheus-node-exporter (Debian) + textfile zberače smartmon/nvme/apt, job="node"."""
import json, sys
DS = {"type": "prometheus", "uid": sys.argv[1] if len(sys.argv) > 1 else "eff0zxq6sk64gc"}
J = 'job="node"'
panels, pid = [], [0]

def nid():
    pid[0] += 1; return pid[0]

def th(*steps):
    out = [{"color": steps[0], "value": None}]
    for i in range(1, len(steps), 2):
        out.append({"color": steps[i + 1], "value": steps[i]})
    return {"mode": "absolute", "steps": out}

def tgt(expr, legend="", ref="A", instant=False, fmt=None):
    t = {"refId": ref, "expr": expr, "legendFormat": legend or "__auto", "datasource": DS}
    if instant: t["instant"] = True; t["range"] = False
    if fmt: t["format"] = fmt
    return t

def row(title, y):
    panels.append({"type": "row", "id": nid(), "title": title, "collapsed": False,
                   "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})

def stat(title, x, y, w, targets, unit="none", thresholds=None, decimals=None, spark=False,
         mappings=None, desc="", minmax=None, overrides=None, text="auto", h=4):
    d = {"unit": unit, "color": {"mode": "thresholds"},
         "thresholds": thresholds or th("blue")}
    if decimals is not None: d["decimals"] = decimals
    if mappings: d["mappings"] = mappings
    if minmax: d["min"], d["max"] = minmax
    panels.append({"type": "stat", "id": nid(), "title": title, "description": desc, "datasource": DS,
                   "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
                   "fieldConfig": {"defaults": d, "overrides": overrides or []},
                   "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                               "colorMode": "value", "graphMode": "area" if spark else "none",
                               "textMode": text, "justifyMode": "center", "orientation": "auto",
                               "wideLayout": True, "showPercentChange": False}})

def ts(title, x, y, w, h, targets, unit, stack=False, desc="", overrides=None, minv=None, maxv=None,
       fill=18, softmax=None):
    custom = {"drawStyle": "line", "lineWidth": 2, "fillOpacity": fill, "gradientMode": "opacity",
              "showPoints": "never", "spanNulls": True, "lineInterpolation": "smooth",
              "stacking": {"mode": "normal" if stack else "none", "group": "A"},
              "axisBorderShow": False, "axisCenteredZero": False}
    if softmax is not None: custom["axisSoftMax"] = softmax
    d = {"unit": unit, "custom": custom, "color": {"mode": "palette-classic"}}
    if minv is not None: d["min"] = minv
    if maxv is not None: d["max"] = maxv
    panels.append({"type": "timeseries", "id": nid(), "title": title, "description": desc, "datasource": DS,
                   "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
                   "fieldConfig": {"defaults": d, "overrides": overrides or []},
                   "options": {"legend": {"displayMode": "list", "placement": "bottom", "calcs": []},
                               "tooltip": {"mode": "multi", "sort": "desc"}}})

def color(name, c):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}

def neg(regex):
    return {"matcher": {"id": "byRegexp", "options": regex},
            "properties": [{"id": "custom.transform", "value": "negative-Y"}]}

def dashed(name, c):
    return {"matcher": {"id": "byName", "options": name},
            "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}},
                           {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [10, 10]}},
                           {"id": "custom.fillOpacity", "value": 0},
                           {"id": "custom.stacking", "value": {"mode": "none", "group": "A"}}]}

CORES = f'scalar(count(count by (cpu) (node_cpu_seconds_total{{{J}}})))'
FS = f'{J},fstype=~"ext4|vfat|xfs|btrfs"'
NV = f'{J},device="nvme0n1"'

# ── Prehľad ────────────────────────────────────────────────────────────────
row("Prehľad", 0)
stat("Beží bez reštartu", 0, 1, 3, [tgt(f'time() - node_boot_time_seconds{{{J}}}', instant=True)],
     unit="dtdurations", desc="Čas od posledného štartu kocky.")
stat("CPU", 3, 1, 4, [tgt(f'100 * (1 - avg(rate(node_cpu_seconds_total{{{J},mode="idle"}}[$__rate_interval])))')],
     unit="percent", decimals=1, spark=True, thresholds=th("green", 70, "orange", 90, "red"), minmax=(0, 100))
stat("Pamäť RAM", 7, 1, 4, [tgt(f'100 * (1 - node_memory_MemAvailable_bytes{{{J}}} / node_memory_MemTotal_bytes{{{J}}})')],
     unit="percent", decimals=1, spark=True, thresholds=th("green", 80, "orange", 90, "red"), minmax=(0, 100),
     desc="Skutočne používaná pamäť (bez cache, ktorú si systém vie kedykoľvek uvoľniť). Spolu 32 GB.")
stat("Disk /", 11, 1, 4, [tgt(f'100 * (node_filesystem_size_bytes{{{J},mountpoint="/"}} - node_filesystem_free_bytes{{{J},mountpoint="/"}}) / (node_filesystem_size_bytes{{{J},mountpoint="/"}} - node_filesystem_free_bytes{{{J},mountpoint="/"}} + node_filesystem_avail_bytes{{{J},mountpoint="/"}})')],
     unit="percent", decimals=1, spark=True, thresholds=th("green", 80, "orange", 90, "red"), minmax=(0, 100),
     desc="Zaplnenie hlavnej partície (LVM root, ~885 GB), rovnako ako df.")
stat("Záťaž (1 min)", 15, 1, 3, [tgt(f'node_load1{{{J}}}')], decimals=2, spark=True,
     thresholds=th("green", 6, "orange", 8, "red"), desc="Load average. Kocka má 8 jadier – do 8 je to v poriadku.")
stat("Swap", 18, 1, 3, [tgt(f'100 * (1 - node_memory_SwapFree_bytes{{{J}}} / node_memory_SwapTotal_bytes{{{J}}})')],
     unit="percent", decimals=1, thresholds=th("green", 30, "orange", 60, "red"), minmax=(0, 100))
stat("Zlyhané služby", 21, 1, 3, [tgt(f'count(node_systemd_unit_state{{{J},state="failed"}} == 1) or vector(0)', instant=True)],
     thresholds=th("green", 1, "red"), desc="Počet systemd služieb v stave failed. Detail: systemctl --failed")

stat("Teplota CPU", 0, 5, 4, [tgt(f'node_hwmon_temp_celsius{{{J},chip="platform_coretemp_0",sensor="temp1"}}')],
     unit="celsius", decimals=0, spark=True, thresholds=th("green", 75, "orange", 90, "red"),
     desc="Intel Core 3 N355 – celý čip (Package). Throttling okolo 100 °C.")
stat("Teplota NVMe disku", 4, 5, 4, [tgt(f'node_hwmon_temp_celsius{{{J},chip="nvme_nvme0",sensor="temp1"}}')],
     unit="celsius", decimals=0, spark=True, thresholds=th("green", 60, "orange", 70, "red"),
     desc="Fanxiang S500Pro 1TB – Composite teplota.")
stat("Teplota RAM", 8, 5, 4, [tgt(f'node_hwmon_temp_celsius{{{J},chip=~"i2c_.*"}}')],
     unit="celsius", decimals=0, spark=True, thresholds=th("green", 65, "orange", 80, "red"),
     desc="Senzor na module DDR5 (SPD5118).")
stat("Zdravie disku (SMART)", 12, 5, 4, [tgt(f'min(smartmon_device_smart_healthy{{{J}}})', instant=True)],
     thresholds=th("red", 1, "green"),
     mappings=[{"type": "value", "options": {"1": {"text": "OK", "color": "green"},
                                              "0": {"text": "PROBLÉM", "color": "red"}}}],
     desc="SMART self-assessment NVMe disku (smartctl, každých 15 min).")
stat("Opotrebenie NVMe", 16, 5, 4, [tgt(f'nvme_percentage_used_ratio{{{J}}}', instant=True)],
     unit="percentunit", decimals=0, thresholds=th("green", 0.5, "orange", 0.8, "red"),
     desc="Koľko % zápisovej životnosti disku je spotrebovanej (výrobcom udávané). 100 % = koniec záruky životnosti.")
stat("Aktualizácie", 20, 5, 4,
     [tgt(f'sum(apt_upgrades_pending{{{J}}}) or vector(0)', "Balíky", "A", True),
      tgt(f'max(node_reboot_required{{{J}}})', "Reštart", "B", True)],
     thresholds=th("blue"), text="value_and_name",
     overrides=[{"matcher": {"id": "byName", "options": "Reštart"},
                 "properties": [{"id": "mappings", "value": [{"type": "value", "options": {
                     "0": {"text": "netreba", "color": "green"}, "1": {"text": "treba", "color": "orange"}}}]}]}],
     desc="Čakajúce apt aktualizácie (bezpečnostné sa inštalujú samé cez unattended-upgrades) a či systém potrebuje reštart.")

# ── CPU a pamäť ────────────────────────────────────────────────────────────
row("CPU a pamäť", 9)
modes = {"user": ("Aplikácie (user)", "blue"), "system": ("Systém (kernel)", "orange"),
         "iowait": ("Čakanie na disk", "red"), "softirq": ("Prerušenia (softirq)", "purple"),
         "irq": ("Prerušenia (irq)", "dark-purple"), "nice": ("Nízka priorita (nice)", "green"),
         "steal": ("Steal", "yellow")}
ts("Využitie CPU podľa typu", 0, 10, 12, 8,
   [tgt(f'sum by (mode) (rate(node_cpu_seconds_total{{{J},mode!="idle"}}[$__rate_interval])) / {CORES} * 100', "{{mode}}")],
   "percent", stack=True, minv=0, softmax=100,
   overrides=[{"matcher": {"id": "byName", "options": m},
               "properties": [{"id": "displayName", "value": n}, {"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
              for m, (n, c) in modes.items()],
   desc="Priemer cez všetkých 8 jadier, 100 % = všetky jadrá naplno.")
ts("Pamäť", 12, 10, 12, 8,
   [tgt(f'node_memory_MemTotal_bytes{{{J}}} - node_memory_MemAvailable_bytes{{{J}}}', "Používaná", "A"),
    tgt(f'node_memory_MemAvailable_bytes{{{J}}} - node_memory_MemFree_bytes{{{J}}}', "Cache (uvoľniteľná)", "B"),
    tgt(f'node_memory_MemFree_bytes{{{J}}}', "Voľná", "C"),
    tgt(f'node_memory_SwapTotal_bytes{{{J}}} - node_memory_SwapFree_bytes{{{J}}}', "Swap", "D")],
   "bytes", stack=True, minv=0,
   overrides=[color("Používaná", "blue"), color("Cache (uvoľniteľná)", "yellow"), color("Voľná", "green"),
              dashed("Swap", "red")],
   desc="Používaná + cache + voľná = 32 GB. Cache si Linux vezme na zrýchlenie disku a uvoľní ju, keď treba.")
ts("Záťaž (load average)", 0, 18, 8, 8,
   [tgt(f'node_load1{{{J}}}', "1 min", "A"), tgt(f'node_load5{{{J}}}', "5 min", "B"),
    tgt(f'node_load15{{{J}}}', "15 min", "C"), tgt(f'count(count by (cpu) (node_cpu_seconds_total{{{J}}}))', "Počet jadier", "D")],
   "none", minv=0, fill=8, overrides=[dashed("Počet jadier", "red")])
ts("Teploty", 8, 18, 8, 8,
   [tgt(f'node_hwmon_temp_celsius{{{J},chip="platform_coretemp_0",sensor="temp1"}}', "CPU", "A"),
    tgt(f'max(node_hwmon_temp_celsius{{{J},chip="platform_coretemp_0",sensor!="temp1"}})', "CPU najteplejšie jadro", "B"),
    tgt(f'node_hwmon_temp_celsius{{{J},chip="nvme_nvme0",sensor="temp1"}}', "NVMe disk", "C"),
    tgt(f'node_hwmon_temp_celsius{{{J},chip=~"i2c_.*"}}', "RAM", "D")],
   "celsius", fill=0, overrides=[color("CPU", "orange"), color("CPU najteplejšie jadro", "red"),
                                 color("NVMe disk", "blue"), color("RAM", "green")])
ts("Čakanie na zdroje (PSI)", 16, 18, 8, 8,
   [tgt(f'rate(node_pressure_cpu_waiting_seconds_total{{{J}}}[$__rate_interval]) * 100', "CPU", "A"),
    tgt(f'rate(node_pressure_memory_waiting_seconds_total{{{J}}}[$__rate_interval]) * 100', "Pamäť", "B"),
    tgt(f'rate(node_pressure_io_waiting_seconds_total{{{J}}}[$__rate_interval]) * 100', "Disk", "C")],
   "percent", minv=0, fill=8, overrides=[color("CPU", "orange"), color("Pamäť", "yellow"), color("Disk", "red")],
   desc="Pressure Stall Information: koľko % času procesy čakali, lebo niečoho bolo málo. Trvalo nad ~10 % = kocka nestíha.")

# ── Disk ───────────────────────────────────────────────────────────────────
row("Disk a partície", 26)
panels.append({"type": "bargauge", "id": nid(), "title": "Zaplnenie partícií", "datasource": DS,
               "gridPos": {"x": 0, "y": 27, "w": 8, "h": 7},
               "targets": [tgt(f'100 * (node_filesystem_size_bytes{{{FS}}} - node_filesystem_free_bytes{{{FS}}}) / (node_filesystem_size_bytes{{{FS}}} - node_filesystem_free_bytes{{{FS}}} + node_filesystem_avail_bytes{{{FS}}})', "{{mountpoint}}", instant=True)],
               "fieldConfig": {"defaults": {"unit": "percent", "decimals": 0, "min": 0, "max": 100,
                                            "color": {"mode": "thresholds"},
                                            "thresholds": th("green", 80, "orange", 90, "red")}, "overrides": []},
               "options": {"displayMode": "gradient", "orientation": "horizontal", "showUnfilled": True,
                           "valueMode": "color", "namePlacement": "top", "sizing": "auto",
                           "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}})
panels.append({"type": "table", "id": nid(), "title": "Partície", "datasource": DS,
               "gridPos": {"x": 8, "y": 27, "w": 8, "h": 7},
               "targets": [tgt(f'max by (mountpoint, device, fstype) (node_filesystem_size_bytes{{{FS}}})', ref="A", instant=True, fmt="table"),
                           tgt(f'max by (mountpoint, device, fstype) (node_filesystem_size_bytes{{{FS}}} - node_filesystem_free_bytes{{{FS}}})', ref="B", instant=True, fmt="table"),
                           tgt(f'max by (mountpoint, device, fstype) (node_filesystem_avail_bytes{{{FS}}})', ref="C", instant=True, fmt="table")],
               "transformations": [
                   {"id": "merge", "options": {}},
                   {"id": "organize", "options": {
                       "excludeByName": {"Time": True, "instance": True, "job": True, "machine": True,
                                         "device_error": True, "__name__": True},
                       "indexByName": {"mountpoint": 0, "device": 1, "fstype": 2, "Value #A": 3, "Value #B": 4, "Value #C": 5},
                       "renameByName": {"mountpoint": "Pripojenie", "device": "Zariadenie", "fstype": "Typ",
                                        "Value #A": "Veľkosť", "Value #B": "Použité", "Value #C": "Voľné"}}},
                   {"id": "sortBy", "options": {"sort": [{"field": "Pripojenie"}]}}],
               "fieldConfig": {"defaults": {"unit": "bytes", "decimals": 1,
                                            "custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
                               "overrides": []},
               "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}})
stat("NVMe disk – životné údaje", 16, 27, 8,
     [tgt(f'nvme_data_units_written_total{{{J}}} * 512000', "Zapísané spolu", "A", True),
      tgt(f'nvme_data_units_read_total{{{J}}} * 512000', "Prečítané spolu", "B", True),
      tgt(f'nvme_power_on_hours_total{{{J}}}', "Hodín v prevádzke", "C", True),
      tgt(f'nvme_unsafe_shutdowns_total{{{J}}}', "Nečisté vypnutia", "D", True),
      tgt(f'nvme_media_errors_total{{{J}}}', "Chyby média", "E", True)],
     text="value_and_name", h=7, thresholds=th("blue"),
     overrides=[{"matcher": {"id": "byRegexp", "options": "Zapísané spolu|Prečítané spolu"},
                 "properties": [{"id": "unit", "value": "bytes"}, {"id": "decimals", "value": 1}]},
                {"matcher": {"id": "byName", "options": "Chyby média"},
                 "properties": [{"id": "thresholds", "value": th("green", 1, "red")}]}],
     desc="Fanxiang S500Pro 1TB. Nečisté vypnutia = výpadky prúdu/tvrdé vypnutia.")
ts("Disk – priepustnosť", 0, 34, 8, 8,
   [tgt(f'rate(node_disk_read_bytes_total{{{NV}}}[$__rate_interval])', "Čítanie", "A"),
    tgt(f'rate(node_disk_written_bytes_total{{{NV}}}[$__rate_interval])', "Zápis", "B")],
   "Bps", overrides=[neg("Zápis"), color("Čítanie", "green"), color("Zápis", "orange")],
   desc="Hore čítanie, dole zápis.")
ts("Disk – operácie (IOPS)", 8, 34, 8, 8,
   [tgt(f'rate(node_disk_reads_completed_total{{{NV}}}[$__rate_interval])', "Čítanie", "A"),
    tgt(f'rate(node_disk_writes_completed_total{{{NV}}}[$__rate_interval])', "Zápis", "B")],
   "iops", overrides=[neg("Zápis"), color("Čítanie", "green"), color("Zápis", "orange")])
ts("Disk – vyťaženie", 16, 34, 8, 8,
   [tgt(f'rate(node_disk_io_time_seconds_total{{{NV}}}[$__rate_interval]) * 100', "Vyťaženie", "A")],
   "percent", minv=0, maxv=100, overrides=[color("Vyťaženie", "purple")],
   desc="Koľko % času disk niečo robil.")

# ── Sieť ───────────────────────────────────────────────────────────────────
row("Sieť", 42)
for x, dev, title in [(0, "enp1s0", "Sieť – LAN (enp1s0)"), (12, "wg0", "Sieť – WireGuard VPN (wg0)")]:
    ts(title, x, 43, 12, 8,
       [tgt(f'rate(node_network_receive_bytes_total{{{J},device="{dev}"}}[$__rate_interval]) * 8', "Prijaté", "A"),
        tgt(f'rate(node_network_transmit_bytes_total{{{J},device="{dev}"}}[$__rate_interval]) * 8', "Odoslané", "B")],
       "bps", overrides=[neg("Odoslané"), color("Prijaté", "blue"), color("Odoslané", "green")],
       desc="Hore prijaté, dole odoslané.")

dash = {"uid": "kocka-hw", "title": "Kocka – hardvér", "tags": ["kocka", "hw", "node-exporter"],
        "description": "CPU, pamäť, disky, teploty a sieť servera kocka (node_exporter).",
        "timezone": "browser", "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
        "graphTooltip": 1, "editable": True, "schemaVersion": 41, "panels": panels,
        "templating": {"list": []}, "annotations": {"list": []}}
json.dump(dash, sys.stdout, ensure_ascii=False, indent=1)
