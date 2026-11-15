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
FALLBACK_S = 2 * 3600         # 15 nov: na 2 uur zonder wekker toch het beste van wat er is klaarzetten


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
    test = os.environ.get("WEKKER_TEST") == "true"   # echte melding nu, ruimere grenzen, telt niet als 'gezien'
    fresh_min = 180 if test else FRESH_MIN
    now = datetime.now(timezone.utc)
    nl = now.astimezone(ZoneInfo("Europe/Amsterdam"))
    if not test and (not (9 <= nl.hour < 23) or time.time() - st.get("last_scan", 0) < SCAN_EVERY_S):
        return
    st["last_scan"] = time.time()
    seen, fresh, rest = set(st.get("seen", [])), [], []
    for ch, acc in CHANNELS.items():
        try:
            items = fetch(ch)
        except Exception as e:
            print("wekker: kanaal mislukt", ch, type(e).__name__); continue
        for it in items:
            age = (now - it["time"]).total_seconds() / 60
            if age > fresh_min or (h(it["tg"]) in seen and not test):
                continue
            sc = score(it)
            # zelfde lat als het brein: alleen posts met een wallet of een harde $-claim in onze niche (anders maakt het brein niks)
            it.update(acc=acc, age=int(age), sc=sc)
            if sc >= 4 and (it["addr"] or re.search(r"\$\d", it["text"])):
                fresh.append(it)
            elif age <= 60:
                rest.append(it)   # gewoon nieuws: reservebak voor als er lang niks goeds is
    fresh.sort(key=lambda i: (-i["sc"], i["age"]))
    strong = any(i["sc"] >= STRONG for i in fresh)
    print("wekker: verse posts", len(fresh), "| sterk:", strong)
    if test or ((len(fresh) >= MIN_NEW or strong) and time.time() - st.get("last_push", 0) > COOLDOWN_S):
        from watch import fire
        accs = ", ".join(sorted({"@" + i["acc"] for i in fresh[:5]}))
        fire(0, f"WEKKER: {len(fresh)} verse kanaal-posts ({accs}). Er zijn misschien geen nieuwe likes: stop dan NIET, "
                "maar volg BREIN.md stap 1d-bis (beste verse tg_feed-items, max 3 replies, kanalen-dagpotje geldt, "
                "bij de laatste tg-send.yml de input wekker meegeven). Log met bron \"wekker\"."
                + (" TEST-RUN van Valentijn: gebruik deze keer items tot age_min < 180 en maak er precies 1 (de beste, liefst een post jonger dan 60 min)." if test else ""))
        if not test:
            st["last_push"] = time.time()
            seen |= {h(i["tg"]) for i in fresh}
    elif time.time() - st.get("last_push", 0) > FALLBACK_S and (fresh or rest):
        # 15 nov (Valentijn): ook als alles matig is toch iets klaarzetten: het beste van wat er is.
        from watch import fire
        best = sorted(fresh + rest, key=lambda i: (-i["sc"], i["age"]))[:3]
        accs = ", ".join(sorted({"@" + i["acc"] for i in best}))
        fire(0, f"WEKKER (beste van wat er is): al {FALLBACK_S // 3600}+ uur geen sterke post. Kies uit de verse tg_feed-items "
                f"(age_min < 60, o.a. {accs}) de 1–2 beste, OOK zonder wallet en OOK bij score < 4. Voeg iets toe met eigen data "
                "(Polymarket-odds, Hyperliquid-koers/funding/liquidaties, wallet-bewegingen rond het nieuws) en maak een kaartje. "
                "Stop dan NIET. Volg verder BREIN.md 1d-bis (kanalen-dagpotje, bij de laatste tg-send.yml de input wekker meegeven). "
                "Log met bron \"wekker-reserve\".")
        st["last_push"] = time.time()
        seen |= {h(i["tg"]) for i in best}
    st["seen"] = sorted(seen)[-400:]
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    main()
