"""Meadowbrook Clinic's demo world: clinicians, patients, appointments, prescriptions, results and messages, dated
from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib

PASSWORD = "Meadowbrook@2026"
SALT = b"meadowbrook-demo-salt"

SLOT = 15
LONG = 30
LUNCH = ("12:30", "13:30")
BOOK_AHEAD = 28
LATE_FEE = 15.0
CHILD_AGE = 16
REPEAT_DAYS = 28
READY_WORKDAYS = 2
MESSAGE_MAX = 1000
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PHARMACIES = ["Meadowbrook Pharmacy (in the clinic)", "Hollins Chemist, 14 Mill Lane"]
TOPICS = ["General question", "Appointments", "Prescriptions", "Test results"]


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def is_workday(day: dt.date, closures) -> bool:
    return day.weekday() < 5 and day.isoformat() not in closures


def add_workdays(day: dt.date, n: int, closures=()) -> dt.date:
    """The nth working day after day (or before it, for a negative n)."""
    step = dt.timedelta(days=1 if n > 0 else -1)
    left = abs(n)
    while left:
        day += step
        if is_workday(day, closures):
            left -= 1
    return day


def ready_date(day: dt.date, closures=()) -> dt.date:
    """When a prescription requested on day can be collected."""
    return day + dt.timedelta(days=READY_WORKDAYS)  # BUG-24: counts calendar days, not working days


def years_ago(day: dt.date, years: int, days: int = 0) -> dt.date:
    try:
        back = day.replace(year=day.year - years)
    except ValueError:
        back = day.replace(year=day.year - years, day=28)
    return back - dt.timedelta(days=days)


CLINICIANS = [
    {"id": 1, "name": "Dr Priya Nandakumar", "role": "GP", "days": [0, 1, 3, 4], "hours": ["08:00", "18:00"],
     "specialties": ["Women's health", "Contraception", "Menopause"],
     "bio": "Priya has been a GP at Meadowbrook since 2015. She runs the women's health clinic on Thursdays."},
    {"id": 2, "name": "Dr Tomasz Wilk", "role": "GP", "days": [0, 2, 3], "hours": ["08:00", "18:00"],
     "specialties": ["Minor surgery", "Joint injections", "Skin problems"],
     "bio": "Tomasz does the practice's minor operations and joint injections, and sees skin problems."},
    {"id": 3, "name": "Dr Helen Achebe", "role": "GP", "days": [1, 2, 4], "hours": ["08:00", "18:00"],
     "specialties": ["Children's health", "Vaccinations", "Asthma"],
     "bio": "Helen looks after children and families, and leads the practice's childhood vaccination programme."},
    {"id": 4, "name": "Rosa Delgado", "role": "Practice nurse", "days": [0, 1, 2, 3, 4], "hours": ["08:00", "12:30"],
     "specialties": ["Vaccinations", "Blood tests", "Asthma"],
     "bio": "Rosa takes blood, gives vaccinations and runs asthma reviews, every weekday morning."},
    {"id": 5, "name": "Dr Samuel Okoro", "role": "GP", "days": [0, 1, 2, 3], "hours": ["08:00", "18:00"],
     "specialties": ["Mental health", "Sleep problems"],
     "bio": "Samuel has a special interest in mental health and sleep, and supervises the practice's trainee GPs."},
    {"id": 6, "name": "Lena Fischer", "role": "Physiotherapist", "days": [3, 4], "hours": ["09:00", "17:00"],
     "specialties": ["Back and neck pain", "Sports injuries"],
     "bio": "Lena sees back, neck and joint problems and sports injuries, on Thursdays and Fridays."},
]  # fmt: skip


def world(today: dt.date) -> dict:
    """A fresh copy of everything one visitor can see and change."""
    closures = {add_workdays(today, 7).isoformat(): "Staff training day"}
    leave = {"from": (today - dt.timedelta(days=3)).isoformat(), "until": add_workdays(today, 8, closures).isoformat()}
    doctors = [dict(c, days=list(c["days"]), hours=list(c["hours"]), leave=None) for c in CLINICIANS]
    doctors[4]["leave"] = leave

    def works(doc: dict, day: dt.date) -> bool:
        off = doc["leave"] and doc["leave"]["from"] <= day.isoformat() <= doc["leave"]["until"]
        return is_workday(day, closures) and day.weekday() in doc["days"] and not off

    def on(did: int, n: int) -> dt.date:
        """The nth day after today that clinician did works (n < 0: before today)."""
        step = dt.timedelta(days=1 if n > 0 else -1)
        day, left = today, abs(n)
        while left:
            day += step
            if works(doctors[did - 1], day):
                left -= 1
        return day

    clinic_day = today if is_workday(today, closures) else add_workdays(today, 1, closures)
    gp = next(d for d in (1, 2, 3) if clinic_day.weekday() in doctors[d - 1]["days"])
    tomorrow = add_workdays(today, 1, closures)
    appointments: list[dict] = []

    def book(patient, doctor, day, time, reason, length=SLOT, status="booked"):
        if any(a["doctor"] == doctor and a["date"] == day.isoformat() and a["time"] == time for a in appointments):
            return
        appointments.append({"id": len(appointments) + 1, "patient": patient, "doctor": doctor,
                             "date": day.isoformat(), "time": time, "length": length, "reason": reason,
                             "status": status})  # fmt: skip

    # Ava (1) and Leo (2)
    book(1, 4, tomorrow, "10:00", "Blood test")
    book(1, 2, on(2, 2), "14:00", "Knee injection", length=LONG)
    book(1, 1, on(1, 6), "08:30", "Contraception review")
    book(1, 1, on(1, 3), "11:00", "Repeat smear test", status="cancelled")
    book(2, 3, on(3, 3), "15:00", "Pre-school vaccinations")
    book(1, 1, on(1, -6), "09:15", "Cough that won't go away", status="attended")
    book(1, 4, on(4, -12), "08:45", "Blood test", status="attended")
    book(1, 2, on(2, -14), "16:30", "Mole check", status="no-show")
    # Other patients
    for time, patient in (("08:00", 4), ("08:15", 5), ("08:30", 6), ("08:45", 7)):
        book(patient, 4, tomorrow, time, "Blood test")
    book(3, 4, clinic_day, "09:00", "Blood test")
    book(3, gp, clinic_day, "15:30", "Blood pressure check")
    book(4, gp, clinic_day, "09:00", "Earache")
    book(5, gp, clinic_day, "11:15", "Rash on arm", status="cancelled")
    book(6, gp, clinic_day, "14:00", "Back pain")
    book(7, 4, clinic_day, "10:30", "Travel vaccinations")

    def back(n: int) -> str:
        return (today - dt.timedelta(days=n)).isoformat()

    thursday = today - dt.timedelta(days=7)
    while thursday.weekday() != 3:
        thursday -= dt.timedelta(days=1)

    def marker(name, value, unit, low, high, previous=None):
        return {"name": name, "value": value, "unit": unit, "low": low, "high": high, "previous": previous}

    def request(rid, medicine, quantity, day: dt.date):
        return {"id": rid, "medicine": medicine, "quantity": quantity, "requested": day.isoformat(),
                "ready": ready_date(day, closures).isoformat(), "pharmacy": PHARMACIES[0],
                "status": "collected"}  # fmt: skip

    return {
        "today": today.isoformat(),
        "clinic_day": clinic_day.isoformat(),
        "closures": closures,
        "users": [
            {"id": 1, "name": "Ava Thornton", "email": "ava@meadowbrook.test", "role": "patient", "patient": 1,
             "salt": SALT.hex(), "hash": DEMO_HASH},
            {"id": 2, "name": "Kai Morgan", "email": "kai@meadowbrook.test", "role": "staff", "patient": None,
             "salt": SALT.hex(), "hash": DEMO_HASH},
        ],
        "patients": [
            {"id": 1, "name": "Ava Thornton", "dob": "1988-04-17", "nhs": "9434765919", "phone": "07700 900461",
             "email": "ava@meadowbrook.test", "guardian": None},
            {"id": 2, "name": "Leo Thornton", "dob": years_ago(today, 7, 40).isoformat(), "nhs": "4010232137",
             "phone": "07700 900461", "email": "ava@meadowbrook.test", "guardian": 1},
            {"id": 3, "name": "Ben Okafor", "dob": "1979-09-02", "nhs": "4857773023", "phone": "07700 900218",
             "email": "ben.okafor@example.test", "guardian": None},
            {"id": 4, "name": "Grace Liu", "dob": "1994-01-23", "nhs": "6123456784", "phone": "07700 900735",
             "email": "grace.liu@example.test", "guardian": None},
            {"id": 5, "name": "Harriet Cole", "dob": "1951-06-30", "nhs": "7382019462", "phone": "07700 900590",
             "email": "harriet.cole@example.test", "guardian": None},
            {"id": 6, "name": "Felix Grant", "dob": "1983-11-08", "nhs": "5501182637", "phone": "07700 900843",
             "email": "felix.grant@example.test", "guardian": None},
            {"id": 7, "name": "Ines Moreau", "dob": "2001-03-14", "nhs": "4729103858", "phone": "07700 900377",
             "email": "ines.moreau@example.test", "guardian": None},
        ],
        "doctors": doctors,
        "appointments": appointments,
        "blocked": [],
        "medicines": [
            {"id": 1, "patient": 1, "name": "Sertraline 50 mg tablets", "dose": "One tablet each morning",
             "unit": "tablets", "max": 56, "last": thursday.isoformat(), "review": back(-60)},
            {"id": 2, "patient": 1, "name": "Levothyroxine 75 microgram tablets",
             "dose": "One tablet daily, before breakfast",
             "unit": "tablets", "max": 56, "last": back(10), "review": back(-120)},
            {"id": 3, "patient": 1, "name": "Salbutamol 100 micrograms/dose inhaler", "dose": "Two puffs when needed",
             "unit": "inhalers", "max": 2, "last": back(50), "review": back(14)},
            {"id": 4, "patient": 1, "name": "Omeprazole 20 mg capsules", "dose": "One capsule daily",
             "unit": "capsules", "max": 56, "last": back(35), "review": back(-90)},
        ],
        "requests": [
            request(1, 3, 1, today - dt.timedelta(days=50)),
            request(2, 4, 56, today - dt.timedelta(days=35)),
            request(3, 1, 56, thursday),
            request(4, 2, 56, today - dt.timedelta(days=10)),
        ],
        "results": [
            {"id": 1, "patient": 1, "name": "Full blood count", "date": back(12), "by": "Rosa Delgado", "read": True,
             "comment": "Platelets a little high. We'll repeat the test in three months; nothing to do before then.",
             "markers": [marker("Haemoglobin", 128, "g/L", 115, 165, 131),
                         marker("White cells", 7.9, "×10⁹/L", 4.0, 11.0, 6.8),
                         marker("Platelets", 410, "×10⁹/L", 150, 400, 380)]},
            {"id": 2, "patient": 1, "name": "Thyroid function", "date": back(30), "by": "Rosa Delgado", "read": True,
             "comment": "Thyroid levels fine on your current dose.",
             "markers": [marker("TSH", 4.0, "mU/L", 0.4, 4.0, 3.1), marker("Free T4", 15, "pmol/L", 9, 19, 14)]},
            {"id": 3, "patient": 1, "name": "HbA1c (blood sugar)", "date": back(30), "by": "Rosa Delgado", "read": True,
             "comment": "Better than last time. Keep going with the diet changes.",
             "markers": [marker("HbA1c", 41, "mmol/mol", 20, 42, 44)]},
            {"id": 4, "patient": 1, "name": "Cholesterol", "date": back(95), "by": "Dr Priya Nandakumar", "read": True,
             "comment": "Total cholesterol is raised. Let's talk about it at your next review.",
             "markers": [marker("Total cholesterol", 5.9, "mmol/L", None, 5.0),
                         marker("HDL cholesterol", 1.4, "mmol/L", 1.0, None)]},
            {"id": 5, "patient": 1, "name": "Vitamin D", "date": back(3), "by": "Rosa Delgado", "read": False,
             "comment": "Vitamin D is low. Please buy a 25 microgram (1,000 unit) supplement and take one a day.",
             "markers": [marker("Vitamin D", 38, "nmol/L", 50, 175)]},
            {"id": 6, "patient": 3, "name": "Liver function", "date": back(6), "by": "Rosa Delgado", "read": False,
             "comment": "ALT raised. Dr Wilk would like to see you to talk about alcohol and your medicines.",
             "markers": [marker("ALT", 64, "U/L", 7, 56, 49), marker("Bilirubin", 12, "µmol/L", 0, 21)]},
        ],
        "threads": [
            {"id": 1, "patient": 1, "topic": "Test results", "subject": "Do I need to fast for my blood test?",
             "read": False, "messages": [
                {"from": "patient", "name": "Ava Thornton", "date": back(2), "read": True,
                 "text": "Hi, I have a blood test booked with Rosa. Do I need to stop eating beforehand?"},
                {"from": "practice", "name": "Kai Morgan, reception", "date": back(1), "read": False,
                 "text": "Hi Ava, no need to fast for this one. Drink plenty of water so it's easier to take blood."},
            ]},
            {"id": 2, "patient": 1, "topic": "General question", "subject": "Fit note for work", "read": True,
             "messages": [
                {"from": "patient", "name": "Ava Thornton", "date": back(40), "read": True,
                 "text": "Could I have a fit note for last week? I was off with the chest infection."},
                {"from": "practice", "name": "Dr Priya Nandakumar", "date": back(39), "read": True,
                 "text": "Done. It's ready to collect from reception, or we can email it to you."},
            ]},
        ],
        "fees": [],
        "pharmacy": PHARMACIES[0],
        "next_id": 1000,
    }  # fmt: skip
