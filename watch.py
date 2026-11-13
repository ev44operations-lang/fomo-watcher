"""Like-wachter voor @TheFomoDoctor.
Kijkt of er nieuwe likes zijn en drukt dan op de startknop van het brein (Claude scheduled task).
Bewaart alleen hashes van gezien likes (deze repo is openbaar; likes zijn privé). Print nooit tweet-ids."""
import urllib.error, hashlib, json, os, sys, time, urllib.request

USER_ID = "2108518365023141888"            # @TheFomoDoctor
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/trig_01BAxnJfMZ9R1dJVVR3pQc8J/fire"
STATE = "state.json"
COOLDOWN_S = 5 * 60                         # niet vaker dan eens per 5 min starten (brein is dan meestal klaar)


def h(x):
    return hashlib.sha256(("fomo:" + x).encode()).hexdigest()[:16]


def oauth1(method, url, params):
    """X-inlog (OAuth 1.0a) met de 4 sleutels van het account; alleen standaard Python."""
    import base64, hmac, secrets, urllib.parse
    E = lambda k: os.environ[k].strip()
    q = lambda x: urllib.parse.quote(str(x), safe="~")
    oa = {"oauth_consumer_key": E("X_API_KEY"), "oauth_nonce": secrets.token_hex(16),
          "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())),
          "oauth_token": E("X_ACCESS_TOKEN"), "oauth_version": "1.0"}
    allp = {**params, **oa}
    base = "&".join([method, q(url), q("&".join(f"{q(k)}={q(allp[k])}" for k in sorted(allp)))])
    key = f"{q(E('X_API_SECRET'))}&{q(E('X_ACCESS_TOKEN_SECRET'))}"
    oa["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{q(k)}="{q(v)}"' for k, v in oa.items())


def get_likes():
    url = f"https://api.x.com/2/users/{USER_ID}/liked_tweets"
    params = {"max_results": "10"}
    req = urllib.request.Request(url + "?max_results=10", headers={"Authorization": oauth1("GET", url, params)})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return [t["id"] for t in json.load(r).get("data", [])]
    except urllib.error.HTTPError as e:
        print("X fout:", e.code, e.read().decode()[:300]); raise


def fire(n, text=None):
    text = text or (f"{n} nieuwe like(s) van Valentijn. Verwerk ze volgens je instructies. Lees ook BREIN.md stap 1d-bis: "
                    "geef bij de laatste tg-send.yml-start de input wekker mee (bijv. '2 replies klaar'), zodat Valentijn een ntfy-melding krijgt.")
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(FIRE_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + os.environ["CLAUDE_FIRE_TOKEN"].strip().removeprefix("Bearer ").strip(),
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("brein gestart:", r.status)


def get_mentions(since_id):
    """Nieuwe tags op @TheFomoDoctor (alleen nieuwe kosten iets). Geeft [(id, auteur-id)]."""
    url = f"https://api.x.com/2/users/{USER_ID}/mentions"
    params = {"max_results": "5", "tweet.fields": "author_id"}
    if since_id:
        params["since_id"] = since_id
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url + "?" + qs, headers={"Authorization": oauth1("GET", url, params)})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [(t["id"], t.get("author_id")) for t in json.load(r).get("data", [])]


def check_tags(st):
    """Snelle route voor tags (13 nov): nieuwe tag → brein meteen starten (niet pas bij de uur-check)."""
    try:
        new = get_mentions(st.get("mention_since"))
    except Exception as e:
        print("tags lezen mislukt:", type(e).__name__); return
    if not new:
        return
    first = not st.get("mention_since")
    st["mention_since"] = max(new, key=lambda x: int(x[0]))[0]
    new = [m for m in new if m[1] != USER_ID]
    if first or not new:
        print("tags: beginpunt gezet" if first else "tags: alleen eigen"); return
    print("nieuwe tags:", len(new))
    fire(0, f"TAG: {len(new)} nieuwe tag(s)/mention(s) op @TheFomoDoctor. Iemand roept ons op: antwoord ZO SNEL MOGELIJK. "
            "Sla likes en wekker over. Start metrics.yml (±90 s, git pull), beantwoord alle mentions met replied: false volgens "
            "BREIN.md stap 1c via de wachtrij (reply_mention, scheduled_at = nu), met kaartje als er een wallet of claim in staat "
            "(geen adres in de tekst tot en met 19 nov), en start daarna meteen publish.yml. Log met bron \"tag-snel\".")


def main():
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    seen, pending = set(st.get("seen", [])), int(st.get("pending", 0))
    ids = get_likes()
    new = [i for i in ids if h(i) not in seen]
    first_run = not seen
    seen |= {h(i) for i in ids}
    if first_run:
        print("eerste keer: huidige likes onthouden, niks gestart")
        new = []
    pending += len(new)
    print("nieuwe likes:", len(new), "| wachtend:", pending)
    if os.environ.get("FORCE") == "true":  # handmatig: brein toch starten (bijv. overgeslagen likes opnieuw)
        pending = max(pending, 1); st["last_fire"] = 0
    if pending and time.time() - st.get("last_fire", 0) > COOLDOWN_S:
        fire(pending)
        st["last_fire"], pending = time.time(), 0
    check_tags(st)
    st.update(seen=sorted(seen)[-200:], pending=pending)
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    main()
