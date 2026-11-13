"""Wekker voor Valentijn (13 nov): push naar de ntfy-app als er verse posts zijn om te liken/replyen.
Leest de openbare Telegram-kanalen van grote on-chain accounts (t.me/s/<kanaal>), kost niks.
Push als er >= MIN_NEW nieuwe verse niche-posts zijn, of 1 hele sterke. Alleen 09:00-23:00 NL.
Onderwerp komt uit secret NTFY_TOPIC (deze repo is openbaar). Bewaart alleen hashes in wekker.json."""
import hashlib, html, json, os, re, time, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CHANNELS = {"OnchainLens": "OnchainLens", "lookonchainchannel": "lookonchain", "WatcherGuru": "WatcherGuru",
            "whale_alert_io": "whale_alert", "ai_9684xtpa": "ai_9684xtpa", "investigations": "zachxbt",
            "wublockchainenglish": "WuBlockchain", "mlmonchain": "mlmabc", "whaleinsidernews": "WhaleInsider"}
NICHE = ("hyperliquid", "polymarket", "solana", "$sol", "pump.fun", "pumpfun", "memecoin", "whale", "long", "short",
         "liquidat", "wallet", "address", "trader", "profit", "loss", "$hype", "bet", "insider", "sniper")
STATE = "wekker.json"
SCAN_EVERY_S = 10 * 60        # elke 10 min kijken
FRESH_MIN = 45                # alleen posts jonger dan 45 min
MIN_NEW = 3                   # zoveel verse posts = wekker
STRONG = 5                    # 1 post met deze score = ook wekker
COOLDOWN_S = 25 * 60          # max 1 wekker per 25 min (behalve test)


def h(x):
    return hashlib.sha256(("wekker:" + x).encode()).hexdigest()[:16]


def fetch(ch):
    req = urllib.request.Request(f"https://t.me/s/{ch}", headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(req, timeout=20).read().decode("utf8", "ignore")
    out = []
    for b in page.split("tgme_widget_message_wrap")[1:]:
        pid = re.search(r'data-post="([^"]+)"', b)
        tm = re.search(r'<time datetime="([^"]+)"', b)
        t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
        if not (pid and tm and t):
            continue
        text = html.unescape(re.sub(r"<[^>]+>", " ", t.group(1).replace("<br/>", "\n")))
        text = " ".join(text.split())
        xl = re.findall(r"(?:x|twitter)\.com/(\w+)/status/(\d+)", b)
        out.append({"tg": pid.group(1), "time": datetime.fromisoformat(tm.group(1)), "text": text,
                    "x_id": xl[0][1] if xl else None, "addr": bool(re.search(r"0x[a-fA-F0-9]{40}", b))})
    return out


def score(it):
    low = it["text"].lower()
    return sum(1 for w in NICHE if w in low) + (2 if it["addr"] else 0) + (1 if re.search(r"\$\d", it["text"]) else 0)


def push(topic, title, lines, actions):
    body = {"topic": topic, "title": title, "message": "\n\n".join(lines) or "-", "tags": ["bell"], "priority": 4}
    if actions:
        body["click"] = actions[0]["url"]
        body["actions"] = actions[:3]
    req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    print("wekker verstuurd:", urllib.request.urlopen(req, timeout=15).status)


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("wekker: geen NTFY_TOPIC, sla over"); return
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if os.environ.get("WEKKER_TEST") == "true":
        push(topic, "🔔 Test: Dr Fomo wekker werkt", ["Vanaf nu krijg je hier een seintje bij verse posts om te liken."], [])
    now = datetime.now(timezone.utc)
    nl = now.astimezone(ZoneInfo("Europe/Amsterdam"))
    if not (9 <= nl.hour < 23) or time.time() - st.get("last_scan", 0) < SCAN_EVERY_S:
        return
    st["last_scan"] = time.time()
    seen, fresh = set(st.get("seen", [])), []
    for ch, acc in CHANNELS.items():
        try:
            items = fetch(ch)
        except Exception as e:
            print("wekker: kanaal mislukt", ch, type(e).__name__); continue
        for it in items:
            age = (now - it["time"]).total_seconds() / 60
            if age > FRESH_MIN or h(it["tg"]) in seen:
                continue
            sc = score(it)
            if sc >= 2:
                it.update(acc=acc, age=int(age), sc=sc)
                fresh.append(it)
    fresh.sort(key=lambda i: (-i["sc"], i["age"]))
    strong = any(i["sc"] >= STRONG for i in fresh)
    print("wekker: verse posts", len(fresh), "| sterk:", strong)
    if (len(fresh) >= MIN_NEW or strong) and time.time() - st.get("last_push", 0) > COOLDOWN_S:
        lines, actions = [], []
        for i in fresh[:5]:
            url = f"https://x.com/{i['acc']}/status/{i['x_id']}" if i["x_id"] else f"https://x.com/{i['acc']}"
            lines.append(f"@{i['acc']} ({i['age']} min): {i['text'][:90]}\n{url}")
            actions.append({"action": "view", "label": f"@{i['acc']}"[:20], "url": url})
        push(topic, f"🔔 Tijd om te liken: {len(fresh)} verse posts", lines, actions)
        st["last_push"] = time.time()
        seen |= {h(i["tg"]) for i in fresh}
    st["seen"] = sorted(seen)[-400:]
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    main()
