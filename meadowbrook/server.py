"""Meadowbrook Clinic: a demo GP patient portal with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the patient or the receptionist in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
TIME = re.compile(r"\d\d:\d\d")

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Welcome", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Help and policies", None),
    "/home": ("home", "Home", "patient"),
    "/doctors": ("doctors", "Find a clinician", "patient"),
    "/doctor": ("doctor", "Clinician", "patient"),
    "/book": ("book", "Book an appointment", "patient"),
    "/appointments": ("appointments", "Appointments", "patient"),
    "/prescriptions": ("prescriptions", "Repeat prescriptions", "patient"),
    "/results": ("results", "Test results", "patient"),
    "/result": ("result", "Test result", "patient"),
    "/messages": ("messages", "Messages", "patient"),
    "/family": ("family", "Family", "patient"),
    "/profile": ("profile", "Your details", "patient"),
    "/desk": ("desk", "Reception desk", "staff"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _date(value, message: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, message) from None


def _id(value, message: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, message) from None


def mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


LUNCH_START, LUNCH_END = (mins(t) for t in data.LUNCH)


def nhs_ok(nhs: str) -> bool:
    return bool(re.fullmatch(r"\d{10}", nhs))  # BUG-33: the mod-11 check digit is never checked


def age(dob: dt.date, on: dt.date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def flag(m: dict) -> str:
    if m["low"] is not None and m["value"] < m["low"]:
        return "Low"
    if m["high"] is not None and m["value"] >= m["high"]:  # BUG-25: a value equal to the upper limit is flagged
        return "High"
    return "Normal"


def slot_starts(doc: dict) -> list[int]:
    """Every 15-minute start in the clinician's day, leaving out lunch."""
    start, end = (mins(t) for t in doc["hours"])
    out = []
    for t in range(start, end - data.SLOT + 1, data.SLOT):
        if LUNCH_START < t < LUNCH_END:  # BUG-08: the 12:30 slot is offered though lunch starts at 12:30
            continue
        out.append(t)
    return out


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return next((u for u in self.world(sess)["users"] if u["id"] == sess["user"]), None)

    def signed_in(self, sess: dict, role: str = "patient") -> dict:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if user["role"] != role:
            raise ApiError(403, "That is for " + ("patients." if role == "patient" else "clinic staff."))
        return self.world(sess)

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        out = {"today": self.world(sess)["today"]}
        return out | {"user": {k: user[k] for k in ("id", "name", "email", "role")} if user else None}

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        if not (u and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)

    # people

    @staticmethod
    def patient(w: dict, pid: int) -> dict:
        return next(p for p in w["patients"] if p["id"] == pid)

    def patient_of(self, sess: dict) -> tuple[dict, dict]:
        w = self.signed_in(sess)
        return w, self.patient(w, self.user(sess)["patient"])

    @staticmethod
    def family(w: dict, me: dict) -> list[dict]:
        return [me] + [p for p in w["patients"] if p["guardian"] == me["id"]]

    @staticmethod
    def owed(w: dict) -> float:
        return round(sum(f["amount"] for f in w["fees"]), 2)

    @staticmethod
    def unread(w: dict, me: dict) -> int:
        return sum(
            1
            for t in w["threads"]
            if t["patient"] == me["id"]
            for m in t["messages"]
            if m["from"] == "practice" and not m["read"]
        )

    # clinicians and free times

    @staticmethod
    def doctor(w: dict, did: int) -> dict:
        found = next((d for d in w["doctors"] if d["id"] == did), None)
        if not found:
            raise ApiError(404, "We couldn't find that clinician.")
        return found

    @staticmethod
    def window_note(w: dict, day: dt.date) -> str | None:
        now = dt.date.fromisoformat(w["today"])
        if day < now:  # BUG-11: same-day appointments can be booked online (bookings open from tomorrow)
            return "Choose a day from tomorrow onwards. For a same-day appointment, call us at 8am."
        if day > now + dt.timedelta(days=data.BOOK_AHEAD):
            return f"You can book up to {data.BOOK_AHEAD} days ahead."
        return None

    @staticmethod
    def closed_note(w: dict, doc: dict, day: dt.date) -> str | None:
        if day.weekday() >= 5:
            return "The clinic is closed at weekends."
        # BUG-06: the clinic's closed days (bank holidays, training days) are not checked
        if day.weekday() not in doc["days"]:
            return f"{doc['name']} doesn't work on {data.DAY_NAMES[day.weekday()]}s."
        # BUG-05: time off is not checked, so a clinician on leave can still be booked
        return None

    @staticmethod
    def taken(w: dict, did: int, day: str) -> set[int]:
        out: set[int] = set()
        for a in w["appointments"]:
            if a["doctor"] == did and a["date"] == day:  # BUG-14: cancelled appointments still hold their time
                out.update(range(mins(a["time"]), mins(a["time"]) + a["length"], data.SLOT))
        return out

    def free(self, w: dict, doc: dict, day: dt.date, length: int, moving: int | None = None) -> list[int]:
        if self.closed_note(w, doc, day):
            return []
        busy = self.taken(w, doc["id"], day.isoformat()) if moving is None else set()  # BUG-15: when moving
        # an appointment, everyone else's bookings are ignored
        # BUG-38: times the reception desk has blocked are still offered
        # BUG-07: a long appointment needs the next 15 minutes free, but not inside the session, so one can start at
        # 17:45 and run past closing
        return [t for t in slot_starts(doc) if t not in busy and (length == data.SLOT or t + data.SLOT not in busy)]

    def next_free(self, w: dict, doc: dict) -> str | None:
        now = dt.date.fromisoformat(w["today"])
        for n in range(1, data.BOOK_AHEAD + 1):
            day = now + dt.timedelta(days=n)
            if not self.closed_note(w, doc, day):
                return f"{day.isoformat()}T{hm(slot_starts(doc)[0])}"  # BUG-04: ignores booked times
        return None

    def doctor_card(self, w: dict, d: dict) -> dict:
        return {k: d[k] for k in ("id", "name", "role", "specialties", "hours", "leave")} | {
            "days_text": ", ".join(data.DAY_NAMES[i][:3] for i in d["days"]),
            "next": self.next_free(w, d),
        }

    def doctors(self, sess: dict, query: dict) -> dict:
        w = self.signed_in(sess)
        q = (query.get("q") or [""])[0].strip().lower()
        specialty = (query.get("specialty") or [""])[0]
        rows = w["doctors"]
        if q:
            rows = [d for d in rows if d["name"].lower().startswith(q)]  # BUG-01: matches the start of the name only
        if specialty:
            rows = [d for d in rows if d["specialties"][0] == specialty]  # BUG-02: only the first specialty counts
        specialties = sorted({s for d in w["doctors"] for s in d["specialties"]})
        return {"doctors": [self.doctor_card(w, d) for d in rows], "specialties": specialties}

    def doctor_detail(self, sess: dict, did: int) -> dict:
        w = self.signed_in(sess)
        d = self.doctor(w, did)
        # weekdays: ISO numbers, Monday = 1
        return {"doctor": self.doctor_card(w, d) | {"bio": d["bio"], "weekdays": [i + 1 for i in d["days"]]}}

    def book_info(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        now = dt.date.fromisoformat(w["today"])
        closures = [{"date": k, "name": v} for k, v in sorted(w["closures"].items()) if k > w["today"]]
        return {
            "today": w["today"],
            "until": (now + dt.timedelta(days=data.BOOK_AHEAD)).isoformat(),
            "doctors": [{k: d[k] for k in ("id", "name", "role")} for d in w["doctors"]],
            "family": [{"id": p["id"], "name": p["name"]} for p in self.family(w, me)],
            "closures": closures,
        }

    def slots(self, sess: dict, query: dict) -> dict:
        w, me = self.patient_of(sess)
        arg = {k: (query.get(k) or [""])[0] for k in query}
        doc = self.doctor(w, _id(arg.get("doctor"), "Choose a clinician."))
        day = _date(arg.get("date"), "Choose a day.")
        length = data.LONG if arg.get("length") == "30" else data.SLOT
        moving = None
        if arg.get("moving"):
            moving = self.own_appointment(w, me, _id(arg["moving"], "Bad appointment."))["id"]
        note = self.window_note(w, day) or self.closed_note(w, doc, day)
        times = [] if note else self.free(w, doc, day, length, moving)
        if not note and not times:
            note = "No free times on this day. Try another day."
        return {"date": day.isoformat(), "times": [hm(t) for t in times], "note": note}

    # appointments

    def view(self, w: dict, a: dict) -> dict:
        doc = self.doctor(w, a["doctor"])
        return a | {
            "end": hm(mins(a["time"]) + a["length"]),
            "doctor_name": doc["name"],
            "doctor_role": doc["role"],
            "patient_name": self.patient(w, a["patient"])["name"],
        }

    def own_appointment(self, w: dict, me: dict, aid: int) -> dict:
        ids = {p["id"] for p in self.family(w, me)}
        a = next((a for a in w["appointments"] if a["id"] == aid and a["patient"] in ids), None)
        if not a:
            raise ApiError(404, "We couldn't find that appointment.")
        return a

    def book(self, sess: dict, body: dict) -> dict:
        w, me = self.patient_of(sess)
        doc = self.doctor(w, _id(body.get("doctor"), "Choose a clinician."))
        day = _date(body.get("date"), "Choose a day.")
        length = data.LONG if body.get("length") in (30, "30") else data.SLOT
        time = str(body.get("time") or "")
        note = self.window_note(w, day) or self.closed_note(w, doc, day)
        if note:
            raise ApiError(400, note)
        if not TIME.fullmatch(time) or mins(time) not in self.free(w, doc, day, length):
            raise ApiError(409, "That time has just been taken. Choose another.")
        # BUG-10: the page sends the family member's id as text, which never equals the number, so every booking
        # falls back to the account holder
        who = next((p for p in self.family(w, me) if p["id"] == body.get("for")), me)
        # BUG-09: the patient's other appointments at the same time are not checked
        a = {
            "id": w["next_id"],
            "patient": who["id"],
            "doctor": doc["id"],
            "date": day.isoformat(),
            "time": time,
            "length": length,
            "reason": _text(body, "reason", 300),
            "status": "booked",
        }
        w["next_id"] += 1
        w["appointments"].append(a)
        return {"appointment": self.view(w, a)}

    def appointments(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        now = w["today"]
        mine = [a for a in w["appointments"] if a["patient"] == me["id"]]  # BUG-32: children's are left out
        upcoming = sorted((a for a in mine if a["date"] >= now), key=lambda a: (a["time"], a["date"]))  # BUG-17
        past = sorted((a for a in mine if a["date"] < now), key=lambda a: (a["date"], a["time"]), reverse=True)
        return {
            "today": now,
            "upcoming": [self.view(w, a) for a in upcoming],
            "past": [self.view(w, a) for a in past],
            "owed": self.owed(w),
        }

    def working_days_until(self, w: dict, day: dt.date) -> int:
        """Working days from tomorrow up to and including day."""
        d, n = dt.date.fromisoformat(w["today"]), 0
        while d < day:
            d += dt.timedelta(days=1)
            n += data.is_workday(d, w["closures"])
        return n

    def cancel(self, sess: dict, aid: int) -> dict:
        w, me = self.patient_of(sess)
        a = self.own_appointment(w, me, aid)
        if a["status"] != "booked" or a["date"] < w["today"]:
            raise ApiError(409, "That appointment can't be cancelled now.")
        a["status"] = "cancelled"
        day = dt.date.fromisoformat(a["date"])
        child = age(dt.date.fromisoformat(self.patient(w, a["patient"])["dob"]), day) < data.CHILD_AGE
        fee = 0.0
        if not child and self.working_days_until(w, day) <= 1:  # BUG-13: the working day before is charged too
            fee = data.LATE_FEE
            w["fees"].append(
                {
                    "date": w["today"],
                    "amount": fee,
                    "description": f"Late cancellation: {self.doctor(w, a['doctor'])['name']}, {a['date']} {a['time']}",
                }
            )
        return self.appointments(sess) | {"fee": fee}

    def reschedule(self, sess: dict, aid: int, body: dict) -> dict:
        w, me = self.patient_of(sess)
        a = self.own_appointment(w, me, aid)
        if a["status"] != "booked" or a["date"] < w["today"]:
            raise ApiError(409, "That appointment can't be moved now.")
        doc = self.doctor(w, a["doctor"])
        day = _date(body.get("date"), "Choose a day.")
        length = data.LONG if body.get("length") in (30, "30") else data.SLOT  # BUG-16: the page never sends the
        # length, so a 30-minute appointment shrinks to 15 minutes when it's moved
        time = str(body.get("time") or "")
        note = self.window_note(w, day) or self.closed_note(w, doc, day)
        if note:
            raise ApiError(400, note)
        if not TIME.fullmatch(time) or mins(time) not in self.free(w, doc, day, length, a["id"]):
            raise ApiError(409, "That time has just been taken. Choose another.")
        a.update(date=day.isoformat(), time=time, length=length)
        return self.appointments(sess) | {"moved": self.view(w, a)}

    def ics(self, sess: dict, aid: int) -> tuple[bytes, str, str]:
        w, me = self.patient_of(sess)
        a = self.view(w, self.own_appointment(w, me, aid))
        start = dt.datetime.combine(dt.date.fromisoformat(a["date"]), dt.time.fromisoformat(a["time"]))
        end = start + dt.timedelta(minutes=a["length"])
        stamp = "%Y%m%dT%I%M00"  # BUG-18: a 12-hour clock with no AM/PM, so 14:00 goes into the calendar as 02:00
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Meadowbrook Clinic//Appointments//EN",
            "BEGIN:VEVENT",
            f"UID:appointment-{a['id']}@meadowbrook.test",
            f"DTSTAMP:{w['today'].replace('-', '')}T000000",
            f"DTSTART:{start.strftime(stamp)}",
            f"DTEND:{end.strftime(stamp)}",
            f"SUMMARY:{a['patient_name']} with {a['doctor_name']}",
            "LOCATION:Meadowbrook Clinic, 2 Meadow Lane",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        return ("\r\n".join(lines) + "\r\n").encode(), "text/calendar; charset=utf-8", "appointment.ics"

    def home(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        now = w["today"]
        mine = [a for a in w["appointments"] if a["patient"] == me["id"] and a["date"] >= now]
        booked = sorted((a for a in mine if a["status"] == "booked"), key=lambda a: (a["date"], a["time"]))
        return {
            "name": me["name"].split()[0],
            "upcoming": len(mine),  # BUG-19: cancelled appointments are counted
            "next": self.view(w, booked[0]) if booked else None,
            "unread": self.unread(w, me),
            "new_results": sum(1 for r in w["results"] if r["patient"] == me["id"] and not r["read"]),
            "owed": self.owed(w),
        }

    # prescriptions

    def prescriptions(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        meds = [m | {"overdue": m["review"] < w["today"]} for m in w["medicines"] if m["patient"] == me["id"]]
        names = {m["id"]: m["name"] for m in meds}
        requests = sorted(
            (r | {"name": names[r["medicine"]]} for r in w["requests"] if r["medicine"] in names),
            key=lambda r: (r["requested"], r["id"]),
            reverse=True,
        )
        return {"medicines": meds, "requests": requests, "pharmacies": data.PHARMACIES, "pharmacy": w["pharmacy"]}

    def request_prescription(self, sess: dict, body: dict) -> dict:
        w, me = self.patient_of(sess)
        mid = _id(body.get("medicine"), "Choose a medicine.")
        med = next((m for m in w["medicines"] if m["id"] == mid and m["patient"] == me["id"]), None)
        if not med:
            raise ApiError(400, "Choose a medicine.")
        qty = body.get("quantity")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            raise ApiError(400, "Enter how many you need.")
        # BUG-20: the most you can ask for at once (56 tablets or capsules, 2 inhalers) is not enforced
        # BUG-21: one request per medicine every 28 days is not checked
        # BUG-23: a medicine whose review is overdue is still issued
        pharmacy = body.get("pharmacy")
        if pharmacy not in data.PHARMACIES:
            raise ApiError(400, "Choose where to collect it.")
        now = dt.date.fromisoformat(w["today"])
        r = {
            "id": w["next_id"],
            "medicine": med["id"],
            "quantity": qty,
            "requested": w["today"],
            "ready": data.ready_date(now, w["closures"]).isoformat(),
            "pharmacy": pharmacy,
            "status": "requested",
        }
        w["next_id"] += 1
        w["requests"].append(r)
        med["last"] = w["today"]
        return self.prescriptions(sess) | {"request": r | {"name": med["name"]}}

    # results

    def result_view(self, w: dict, r: dict) -> dict:
        p = self.patient(w, r["patient"])
        markers = [m | {"flag": flag(m)} for m in r["markers"]]
        return r | {"markers": markers, "patient_name": p["name"], "patient_nhs": p["nhs"]}

    def results(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        mine = sorted((r for r in w["results"] if r["patient"] == me["id"]), key=lambda r: r["date"], reverse=True)
        return {"results": [self.result_view(w, r) for r in mine]}

    def result(self, sess: dict, rid: int) -> dict:
        w, me = self.patient_of(sess)
        r = next((r for r in w["results"] if r["id"] == rid), None)  # BUG-27: whose result it is isn't checked
        if not r:
            raise ApiError(404, "We couldn't find that result.")
        return {"result": self.result_view(w, r)}

    def read_result(self, sess: dict, rid: int) -> dict:
        w, me = self.patient_of(sess)
        r = next((r for r in w["results"] if r["id"] == rid and r["patient"] == me["id"]), None)
        if r:
            r["read"] = True
        return {"ok": True}

    # messages

    def messages(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        threads = []
        for t in w["threads"]:
            if t["patient"] == me["id"]:
                fresh = any(m["from"] == "practice" and not m["read"] for m in t["messages"])
                threads.append(t | {"unread": fresh, "updated": t["messages"][-1]["date"]})
        threads.sort(key=lambda t: (t["updated"], t["id"]), reverse=True)
        return {"threads": threads, "topics": data.TOPICS, "unread": self.unread(w, me)}

    def send_message(self, sess: dict, body: dict) -> dict:
        w, me = self.patient_of(sess)
        topic = body.get("topic")
        if topic not in data.TOPICS:
            raise ApiError(400, "Choose a topic.")
        subject = _text(body, "subject", 120)
        if not subject:
            raise ApiError(400, "Add a subject.")
        text = body.get("message")
        if not isinstance(text, str) or not text:  # BUG-29: a message of only spaces or blank lines is accepted
            raise ApiError(400, "Write your message.")
        if len(text) > data.MESSAGE_MAX:
            raise ApiError(400, f"Messages can be up to {data.MESSAGE_MAX} characters.")
        thread = {
            "id": w["next_id"],
            "patient": me["id"],
            "topic": topic,
            "subject": subject,
            "read": True,
            "messages": [{"from": "patient", "name": me["name"], "date": w["today"], "read": True, "text": text}],
        }
        w["next_id"] += 1
        w["threads"].append(thread)
        return self.messages(sess) | {"sent": thread["id"]}

    def read_thread(self, sess: dict, tid: int) -> dict:
        w, me = self.patient_of(sess)
        t = next((t for t in w["threads"] if t["id"] == tid and t["patient"] == me["id"]), None)
        if not t:
            raise ApiError(404, "We couldn't find that conversation.")
        t["read"] = True  # BUG-30: the practice's replies inside it stay unread
        return {"unread": self.unread(w, me)}

    # family

    def family_view(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        now = dt.date.fromisoformat(w["today"])
        out = []
        for p in self.family(w, me)[1:]:
            booked = sorted(
                (a for a in w["appointments"] if a["patient"] == p["id"] and a["status"] == "booked"),
                key=lambda a: (a["date"], a["time"]),
            )
            upcoming = [self.view(w, a) for a in booked if a["date"] >= w["today"]]
            out.append(
                {k: p[k] for k in ("id", "name", "dob", "nhs")}
                | {"age": age(dt.date.fromisoformat(p["dob"]), now), "upcoming": upcoming}
            )
        return {"children": out, "today": w["today"]}

    def add_child(self, sess: dict, body: dict) -> dict:
        w, me = self.patient_of(sess)
        now = dt.date.fromisoformat(w["today"])
        name = _text(body, "name", 80)
        if not name:
            raise ApiError(400, "Enter the child's full name.")
        dob = _date(body.get("dob"), "Enter the child's date of birth.")
        if dob > now:
            raise ApiError(400, "The date of birth can't be in the future.")
        if now.year - dob.year >= data.CHILD_AGE:  # BUG-31: age from the years alone, so a 15-year-old whose
            # birthday is still to come this year is refused
            raise ApiError(400, "Children aged 16 or over need to register for their own account.")
        nhs = re.sub(r"\s", "", _text(body, "nhs", 20))
        if not nhs_ok(nhs):
            raise ApiError(400, "That NHS number isn't valid.")
        w["patients"].append(
            {
                "id": w["next_id"],
                "name": name,
                "dob": dob.isoformat(),
                "nhs": nhs,
                "phone": self.patient(w, me["id"])["phone"],
                "email": me["email"],
                "guardian": me["id"],
            }
        )
        w["next_id"] += 1
        return self.family_view(sess)

    # profile

    def profile(self, sess: dict) -> dict:
        w, me = self.patient_of(sess)
        fees = sorted(w["fees"], key=lambda f: f["date"], reverse=True)
        return {k: me[k] for k in ("name", "dob", "nhs", "phone", "email")} | {"fees": fees, "owed": self.owed(w)}

    def save_profile(self, sess: dict, body: dict) -> dict:
        w, me = self.patient_of(sess)
        dob = _date(body.get("dob"), "Enter your date of birth.")  # BUG-34: a date in the future is accepted
        nhs = re.sub(r"\s", "", _text(body, "nhs", 20))
        if not nhs_ok(nhs):
            raise ApiError(400, "That NHS number isn't valid. It has 10 digits, like 943 476 5919.")
        phone = _text(body, "phone", 40)
        if len(phone) < 10:  # BUG-35: only the length is checked, not that it's an 11-digit UK number
            raise ApiError(400, "Enter a UK phone number, like 07700 900123.")
        email = _text(body, "email", 120)
        if not EMAIL.fullmatch(email):
            raise ApiError(400, "Enter a valid email address.")
        me.update(dob=dob.isoformat(), nhs=nhs, phone=phone, email=email)
        return self.profile(sess)

    # reception desk

    def desk(self, sess: dict, query: dict) -> dict:
        w = self.signed_in(sess, "staff")
        raw = (query.get("date") or [""])[0]
        day = _date(raw, "Choose a day.").isoformat() if raw else w["clinic_day"]
        rows = sorted(
            (self.view(w, a) for a in w["appointments"] if a["date"] == day),
            key=lambda a: (a["time"], a["doctor"]),
        )
        names = {d["id"]: d["name"] for d in w["doctors"]}
        blocked = sorted(
            (b | {"doctor_name": names[b["doctor"]]} for b in w["blocked"] if b["date"] >= w["today"]),
            key=lambda b: (b["date"], b["time"]),
        )
        return {
            "day": day,
            "today": w["today"],
            "closed": w["closures"].get(day),
            "appointments": rows,
            "blocked": blocked,
            "doctors": [{k: d[k] for k in ("id", "name", "role", "hours")} for d in w["doctors"]],
            "clinic_day": w["clinic_day"],
        }

    def desk_appointment(self, w: dict, aid: int) -> dict:
        a = next((a for a in w["appointments"] if a["id"] == aid), None)
        if not a:
            raise ApiError(404, "We couldn't find that appointment.")
        if a["status"] != "booked":
            raise ApiError(409, "That appointment has already been dealt with.")
        return a

    def check_in(self, sess: dict, aid: int) -> dict:
        w = self.signed_in(sess, "staff")
        a = self.desk_appointment(w, aid)
        for other in w["appointments"]:
            if other["patient"] == a["patient"] and other["date"] == a["date"] and other["status"] == "booked":
                other["status"] = "arrived"  # BUG-37: every appointment that patient has that day is checked in
        return self.desk(sess, {"date": [a["date"]]})

    def no_show(self, sess: dict, aid: int) -> dict:
        w = self.signed_in(sess, "staff")
        a = self.desk_appointment(w, aid)
        a["status"] = "no-show"
        return self.desk(sess, {"date": [a["date"]]})

    def block(self, sess: dict, body: dict) -> dict:
        w = self.signed_in(sess, "staff")
        doc = self.doctor(w, _id(body.get("doctor"), "Choose a clinician."))
        day = _date(body.get("date"), "Choose a day.")
        if day < dt.date.fromisoformat(w["today"]):
            raise ApiError(400, "Choose today or a later day.")
        note = self.closed_note(w, doc, day)
        if note:
            raise ApiError(400, note)
        time = str(body.get("time") or "")
        if not TIME.fullmatch(time) or mins(time) not in slot_starts(doc):
            raise ApiError(400, "Choose a time in the clinician's day.")
        if mins(time) in self.taken(w, doc["id"], day.isoformat()):
            raise ApiError(409, "Someone is booked at that time.")
        if any(b["doctor"] == doc["id"] and b["date"] == day.isoformat() and b["time"] == time for b in w["blocked"]):
            raise ApiError(409, "That time is already blocked.")
        reason = _text(body, "reason", 120) or "Kept free"
        w["blocked"].append(
            {"id": w["next_id"], "doctor": doc["id"], "date": day.isoformat(), "time": time, "reason": reason}
        )
        w["next_id"] += 1
        return self.desk(sess, {"date": [day.isoformat()]})

    def unblock(self, sess: dict, bid: int) -> dict:
        w = self.signed_in(sess, "staff")
        b = next((b for b in w["blocked"] if b["id"] == bid), None)
        if not b:
            raise ApiError(404, "We couldn't find that blocked time.")
        w["blocked"].remove(b)
        return self.desk(sess, {"date": [b["date"]]})

    def find_patients(self, sess: dict, query: dict) -> dict:
        w = self.signed_in(sess, "staff")
        q = (query.get("q") or [""])[0].strip().lower()
        if len(q) < 2:
            raise ApiError(400, "Type at least two letters of the name.")
        out = []
        for p in w["patients"]:
            if q not in p["name"].lower():
                continue
            upcoming = sorted(
                (self.view(w, a) for a in w["appointments"] if a["patient"] == p["id"] and a["date"] >= w["today"]),
                key=lambda a: (a["date"], a["time"]),
            )
            results = [
                self.result_view(w, r) for r in sorted(w["results"], key=lambda r: r["date"], reverse=True)
            ]  # BUG-36: test results go to reception with the contact details
            out.append(
                {k: p[k] for k in ("id", "name", "dob", "nhs", "phone", "email")}
                | {"upcoming": upcoming, "results": [r for r in results if r["patient"] == p["id"]][:3]}
            )
        return {"patients": out}

    def day_csv(self, sess: dict, query: dict) -> tuple[bytes, str, str]:
        d = self.desk(sess, query)
        lines = ["Time,Ends,Clinician,Patient,Reason"]
        for a in d["appointments"]:  # BUG-39: cancelled appointments are listed as if they were still on
            reason = a["reason"].replace('"', "'")
            lines.append(f'{a["time"]},{a["end"]},{a["doctor_name"]},{a["patient_name"]},"{reason}"')
        return ("\n".join(lines) + "\n").encode(), "text/csv; charset=utf-8", f"day-list-{d['day']}.csv"


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Not for this account"
    user = store.user(sess)
    if not user:
        nav = '<a href="/" data-nav="landing">Welcome</a><a href="/help" data-nav="help">Help and policies</a>'
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        if user["role"] == "patient":
            w = store.world(sess)
            unread = store.unread(w, store.patient(w, user["patient"]))
            badge = f' <span class="badge" id="nav-unread">{unread}</span>' if unread else ""
            links = [
                ("/home", "home", "Home"),
                ("/doctors", "doctors", "Clinicians"),
                ("/book", "book", "Book"),
                ("/appointments", "appointments", "Appointments"),
                ("/prescriptions", "prescriptions", "Prescriptions"),
                ("/results", "results", "Results"),
                ("/messages", "messages", "Messages" + badge),
                ("/family", "family", "Family"),
            ]
        else:
            links = [("/desk", "desk", "Reception desk")]
        nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
        nav += '<a href="/help" data-nav="help">Help</a>'
        first = html.escape(user["name"].split()[0])
        account = (
            f'<a href="/profile" class="who">{first}</a>'
            if user["role"] == "patient"
            else f'<span class="who">{first}</span>'
        )
        account += '<button type="button" id="logout" class="link">Log out</button>'
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": (PAGES_DIR / f"{name}.html").read_text(),
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "meadowbrook"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["mb_sid"].value if "mb_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"mb_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, tuple):
                            content, ctype, filename = result
                            extra = {"Content-Disposition": f'attachment; filename="{filename}"'}
                            return self._send(200, content, ctype, extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role and user["role"] != role:
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/home": lambda: store.home(sess),
                    "/api/doctors": lambda: store.doctors(sess, query),
                    "/api/book-info": lambda: store.book_info(sess),
                    "/api/slots": lambda: store.slots(sess, query),
                    "/api/appointments": lambda: store.appointments(sess),
                    "/api/prescriptions": lambda: store.prescriptions(sess),
                    "/api/results": lambda: store.results(sess),
                    "/api/messages": lambda: store.messages(sess),
                    "/api/family": lambda: store.family_view(sess),
                    "/api/profile": lambda: store.profile(sess),
                    "/api/desk": lambda: store.desk(sess, query),
                    "/api/desk/patients": lambda: store.find_patients(sess, query),
                    "/api/desk/day.csv": lambda: store.day_csv(sess, query),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/doctors/(\d+)", lambda i: store.doctor_detail(sess, int(i))),
                    (r"/api/appointments/(\d+)\.ics", lambda i: store.ics(sess, int(i))),
                    (r"/api/results/(\d+)", lambda i: store.result(sess, int(i))),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/appointments": lambda: store.book(sess, body),
                    "/api/prescriptions": lambda: store.request_prescription(sess, body),
                    "/api/messages": lambda: store.send_message(sess, body),
                    "/api/family": lambda: store.add_child(sess, body),
                    "/api/profile": lambda: store.save_profile(sess, body),
                    "/api/desk/block": lambda: store.block(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/appointments/(\d+)/cancel", lambda i: store.cancel(sess, int(i))),
                    (r"/api/appointments/(\d+)/reschedule", lambda i: store.reschedule(sess, int(i), body)),
                    (r"/api/results/(\d+)/read", lambda i: store.read_result(sess, int(i))),
                    (r"/api/messages/(\d+)/read", lambda i: store.read_thread(sess, int(i))),
                    (r"/api/desk/appointments/(\d+)/checkin", lambda i: store.check_in(sess, int(i))),
                    (r"/api/desk/appointments/(\d+)/noshow", lambda i: store.no_show(sess, int(i))),
                    (r"/api/desk/block/(\d+)/delete", lambda i: store.unblock(sess, int(i))),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8086"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Meadowbrook Clinic listening on :{port}", flush=True)
    httpd.serve_forever()
