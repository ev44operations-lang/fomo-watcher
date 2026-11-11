"""Like-wachter voor @TheFomoDoctor.
Kijkt of er nieuwe likes zijn en drukt dan op de startknop van het brein (Claude scheduled task).
Bewaart alleen hashes van gezien likes (deze repo is openbaar; likes zijn privé). Print nooit tweet-ids."""
import hashlib, json, os, sys, time, urllib.request

USER_ID = "2108518365023141888"            # @TheFomoDoctor
FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/trig_01BAxnJfMZ9R1dJVVR3pQc8J/fire"
STATE = "state.json"
COOLDOWN_S = 8 * 60                         # niet vaker dan eens per 8 min starten (brein is dan nog bezig)


def h(x):
    return hashlib.sha256(("fomo:" + x).encode()).hexdigest()[:16]


def get_likes():
    req = urllib.request.Request(f"https://api.x.com/2/users/{USER_ID}/liked_tweets?max_results=10",
                                 headers={"Authorization": "Bearer " + os.environ["X_BEARER"]})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [t["id"] for t in json.load(r).get("data", [])]


def fire(n):
    body = json.dumps({"text": f"{n} nieuwe like(s) van Valentijn. Verwerk ze volgens je instructies."}).encode()
    req = urllib.request.Request(FIRE_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + os.environ["CLAUDE_FIRE_TOKEN"],
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("brein gestart:", r.status)


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
    if pending and time.time() - st.get("last_fire", 0) > COOLDOWN_S:
        fire(pending)
        st["last_fire"], pending = time.time(), 0
    st.update(seen=sorted(seen)[-200:], pending=pending)
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    main()
