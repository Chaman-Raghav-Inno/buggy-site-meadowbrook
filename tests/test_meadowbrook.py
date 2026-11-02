"""Meadowbrook's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from meadowbrook import data, server

T = server.today()


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str, password: str = data.PASSWORD) -> int:
        return self.post("/api/login", {"email": f"{who}@meadowbrook.test", "password": password})[0]

    def times(self, doctor: int, date: str, length: int = 15, **extra) -> list[str]:
        return self.get("/api/slots", doctor=doctor, date=date, length=length, **extra)[1]["times"]

    def book(self, doctor: int, date: str, time: str, length: int = 15, **extra):
        return self.post("/api/appointments", {"doctor": doctor, "date": date, "time": time, "length": length} | extra)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def ava(base_url):
    c = Client(base_url)
    assert c.login("ava") == 200
    return c


@pytest.fixture
def world():
    return data.world(T)


def works(w: dict, did: int, date: dt.date) -> bool:
    doc = w["doctors"][did - 1]
    return data.is_workday(date, w["closures"]) and date.weekday() in doc["days"]


def next_day(w: dict, did: int, after: dt.date | None = None) -> dt.date:
    d = (after or T) + dt.timedelta(days=1)
    while not works(w, did, d):
        d += dt.timedelta(days=1)
    return d


def test_pages_and_access(base_url, ava):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/home")
    assert status == 302 and headers["Location"] == "/login?next=%2Fhome"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert ava.request("/desk")[0] == 403 and ava.get("/api/desk")[0] == 403
    for path in ("/home", "/doctors", "/book", "/appointments", "/prescriptions", "/results", "/messages", "/profile"):
        assert ava.request(path)[0] == 200, path
    kai = Client(base_url)
    kai.login("kai")
    assert kai.request("/desk")[0] == 200 and kai.request("/home")[0] == 403


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_seed(world):
    assert server.nhs_ok("9434765919")
    for p in world["patients"]:
        digits = [int(c) for c in p["nhs"]]
        check = (11 - sum(d * w for d, w in zip(digits[:9], range(10, 1, -1), strict=True)) % 11) % 11
        assert check == digits[9], p["name"]
    assert len(world["appointments"]) == len({(a["doctor"], a["date"], a["time"]) for a in world["appointments"]})


def test_find_a_clinician(ava):
    assert ava.get("/api/doctors", q="Wilk")[1]["doctors"] == []  # BUG-01
    assert [d["name"] for d in ava.get("/api/doctors", q="dr t")[1]["doctors"]] == ["Dr Tomasz Wilk"]
    vaccinators = [d["name"] for d in ava.get("/api/doctors", specialty="Vaccinations")[1]["doctors"]]
    assert vaccinators == ["Rosa Delgado"]  # BUG-02: Dr Achebe lists it second
    rosa = next(d for d in ava.get("/api/doctors")[1]["doctors"] if d["id"] == 4)
    date, time = rosa["next"].split("T")
    assert time == "08:00" and "08:00" not in ava.times(4, date)  # BUG-04
    okoro = ava.get("/api/doctors/5")[1]["doctor"]
    assert okoro["leave"] and okoro["next"] < okoro["leave"]["until"]  # BUG-05
    assert ava.times(5, okoro["next"][:10])
    assert ava.get("/api/doctors/1")[1]["doctor"]["weekdays"] == [1, 2, 4, 5]
    assert ava.get("/api/doctors/99")[0] == 404


def test_booking_rules(ava, world):
    closed = next(iter(world["closures"]))
    doc = next(d for d in (1, 2, 3, 4) if dt.date.fromisoformat(closed).weekday() in world["doctors"][d - 1]["days"])
    assert ava.times(doc, closed)  # BUG-06
    nand = next_day(world, 1).isoformat()
    assert "12:30" in ava.times(1, nand)  # BUG-08
    assert "17:45" in ava.times(1, nand, 30)  # BUG-07
    assert ava.book(1, nand, "17:45", 30)[0] == 200
    assert server.Store.window_note(world, T) is None  # BUG-11
    if T.weekday() < 5:
        assert ava.book(4, day(0), "11:00")[0] == 200
    assert ava.book(1, day(-1), "11:00")[0] == 400
    assert ava.book(1, day(40), "11:00")[0] == 400


def test_booking_for_family_and_overlaps(ava, world):
    tomorrow = data.add_workdays(T, 1, world["closures"])
    gp = next(d for d in (1, 2, 3) if tomorrow.weekday() in world["doctors"][d - 1]["days"])
    status, result = ava.book(gp, tomorrow.isoformat(), "10:00", **{"for": "2"})
    assert status == 200  # BUG-09: Ava already sees Rosa at 10:00 that day
    assert result["appointment"]["patient_name"] == "Ava Thornton"  # BUG-10: booked for Leo (id "2")
    assert ava.book(gp, tomorrow.isoformat(), "10:30", **{"for": 2})[1]["appointment"]["patient"] == 2


def test_appointments_list(ava, world):
    listing = ava.get("/api/appointments")[1]
    assert all(a["patient"] == 1 for a in listing["upcoming"])  # BUG-32: Leo's appointment is missing
    dates = [(a["date"], a["time"]) for a in listing["upcoming"]]
    assert dates != sorted(dates)  # BUG-17
    assert ava.get("/api/home")[1]["upcoming"] == 4  # BUG-19: one of them is cancelled
    wilk = next(a for a in listing["upcoming"] if a["length"] == 30)
    status, raw, headers = ava.request(f"/api/appointments/{wilk['id']}.ics")
    assert "DTSTART:" + wilk["date"].replace("-", "") + "T020000" in raw.decode()  # BUG-18
    assert headers["Content-Type"].startswith("text/calendar")


def test_cancel_and_move(ava, world):
    listing = ava.get("/api/appointments")[1]
    blood = next(a for a in listing["upcoming"] if a["reason"] == "Blood test")
    status, after = ava.post(f"/api/appointments/{blood['id']}/cancel")
    assert status == 200 and after["fee"] == 15  # BUG-13: it's tomorrow, not today
    assert blood["time"] not in ava.times(4, blood["date"])  # BUG-14
    wilk = next(a for a in listing["upcoming"] if a["length"] == 30)
    other = next_day(world, 2, dt.date.fromisoformat(wilk["date"]))
    status, moved = ava.post(f"/api/appointments/{wilk['id']}/reschedule", {"date": other.isoformat(), "time": "14:00"})
    assert status == 200 and moved["moved"]["length"] == 15  # BUG-16


def test_move_double_books(ava, world):
    tomorrow = data.add_workdays(T, 1, world["closures"]).isoformat()
    blood = next(a for a in ava.get("/api/appointments")[1]["upcoming"] if a["reason"] == "Blood test")
    assert "08:00" not in ava.times(4, tomorrow)
    assert "08:00" in ava.times(4, tomorrow, moving=blood["id"])  # BUG-15
    assert ava.post(f"/api/appointments/{blood['id']}/reschedule", {"date": tomorrow, "time": "08:00"})[0] == 200
    ava.post("/api/logout")
    ava.login("kai")
    rows = ava.get("/api/desk", date=tomorrow)[1]["appointments"]
    assert len([a for a in rows if a["doctor"] == 4 and a["time"] == "08:00"]) == 2


def test_prescriptions(ava):
    assert ava.post("/api/prescriptions", {"medicine": 4, "quantity": 200, "pharmacy": data.PHARMACIES[0]})[0] == 200
    assert ava.post("/api/prescriptions", {"medicine": 2, "quantity": 28, "pharmacy": data.PHARMACIES[0]})[0] == 200
    assert ava.post("/api/prescriptions", {"medicine": 3, "quantity": 1, "pharmacy": data.PHARMACIES[0]})[0] == 200
    # BUG-20, BUG-21 (levothyroxine was ordered 10 days ago), BUG-23 (salbutamol's review is overdue)
    history = ava.get("/api/prescriptions")[1]["requests"]
    sertraline = next(r for r in history if r["medicine"] == 1)
    assert dt.date.fromisoformat(sertraline["requested"]).weekday() == 3
    assert dt.date.fromisoformat(sertraline["ready"]).weekday() == 5  # BUG-24
    assert ava.post("/api/prescriptions", {"medicine": 4, "quantity": 0, "pharmacy": data.PHARMACIES[0]})[0] == 400


def test_results(ava):
    thyroid = ava.get("/api/results/2")[1]["result"]
    tsh = thyroid["markers"][0]
    assert tsh["value"] == tsh["high"] and tsh["flag"] == "High"  # BUG-25
    status, other = ava.get("/api/results/6")
    assert status == 200 and other["result"]["patient_name"] == "Ben Okafor"  # BUG-27
    assert ava.get("/api/results/99")[0] == 404


def test_messages(ava):
    assert ava.post("/api/messages", {"topic": "General question", "subject": "Hi", "message": "   \n "})[0] == 200
    # BUG-29
    assert ava.post("/api/messages", {"topic": "General question", "subject": "", "message": "x"})[0] == 400
    thread = next(t for t in ava.get("/api/messages")[1]["threads"] if t["unread"])
    assert ava.post(f"/api/messages/{thread['id']}/read")[1]["unread"] == 1  # BUG-30
    assert b'id="nav-unread">1<' in ava.request("/messages")[1]


def test_family_and_profile(ava):
    fifteen = data.years_ago(T, 16, -1)  # 16 tomorrow, so 15 today
    status, _ = ava.post("/api/family", {"name": "Mia Thornton", "dob": str(fifteen), "nhs": "6123456784"})
    if fifteen.year == T.year - 16:
        assert status == 400  # BUG-31
    assert ava.post("/api/family", {"name": "Sam", "dob": str(data.years_ago(T, 3)), "nhs": "4729103858"})[0] == 200
    me = ava.get("/api/profile")[1]
    base = {"dob": me["dob"], "nhs": me["nhs"], "phone": me["phone"], "email": me["email"]}
    assert ava.post("/api/profile", base | {"nhs": "9434765918"})[0] == 200  # BUG-33
    assert ava.post("/api/profile", base | {"dob": day(30)})[0] == 200  # BUG-34
    assert ava.post("/api/profile", base | {"phone": "call me later"})[0] == 200  # BUG-35
    assert ava.post("/api/profile", base | {"email": "ava@"})[0] == 400


def test_desk(base_url, world):
    kai = Client(base_url)
    kai.login("kai")
    desk = kai.get("/api/desk")[1]
    ben = [a for a in desk["appointments"] if a["patient_name"] == "Ben Okafor"]
    assert len(ben) == 2
    after = kai.post(f"/api/desk/appointments/{ben[0]['id']}/checkin")[1]
    assert [a["status"] for a in after["appointments"] if a["patient_name"] == "Ben Okafor"] == ["arrived"] * 2
    # BUG-37
    status, raw, _ = kai.request(f"/api/desk/day.csv?date={desk['day']}")
    assert "Harriet Cole" in raw.decode()  # BUG-39: her appointment is cancelled
    found = kai.get("/api/desk/patients", q="ava")[1]["patients"][0]
    assert found["results"]  # BUG-36
    target = next_day(world, 4, data.add_workdays(T, 1, world["closures"])).isoformat()
    assert kai.post("/api/desk/block", {"doctor": 4, "date": target, "time": "11:00", "reason": "Emergency"})[0] == 200
    kai.post("/api/logout")
    kai.login("ava")
    assert "11:00" in kai.times(4, target)  # BUG-38
    assert kai.book(4, target, "11:00")[0] == 200
