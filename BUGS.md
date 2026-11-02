# Meadowbrook Clinic: answer key (40 planted bugs)

Meadowbrook Clinic is a demo GP patient portal (find a clinician, book, move and cancel appointments, repeat
prescriptions, test results, messages, children on your account, your details, and a reception desk) with
**functional bugs planted on purpose**, for checking what the AI QA Scanner finds. Most bugs break a rule published
on the site, so finding them takes the rules, some date or time arithmetic, a download, a second page or the
receptionist's account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_meadowbrook.py` keeps the server-side ones in
place. The rules every bug breaks are published on the site's **Help and policies** page (`/help`).

## Run it

- **Locally**: `python -m meadowbrook` (port 8086, or `PORT`), then open http://localhost:8086.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Ava and then Kai in the same browser shares one world, so what Kai does shows up
for Ava. A restart resets everything.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC). "Working day" means Monday to Friday
and not the clinic's closed day. All times are clinic time.

| What | Value |
|---|---|
| Accounts (password `Meadowbrook@2026`, listed on the login page) | `ava@meadowbrook.test` Ava Thornton, patient (born 17 Apr 1988, NHS 943 476 5919) · `kai@meadowbrook.test` Kai Morgan, receptionist |
| Family | Leo Thornton, Ava's son, aged 7 (NHS 401 023 2137) |
| Clinicians | Dr Priya Nandakumar, GP, Mon/Tue/Thu/Fri 08:00–18:00 (Women's health, Contraception, Menopause) · Dr Tomasz Wilk, GP, Mon/Wed/Thu 08:00–18:00 · Dr Helen Achebe, GP, Tue/Wed/Fri 08:00–18:00 (Children's health, **Vaccinations**, Asthma) · Rosa Delgado, practice nurse, weekdays 08:00–12:30 (**Vaccinations**, Blood tests, Asthma) · Dr Samuel Okoro, GP, Mon–Thu, **on leave** from day −3 to the 8th working day · Lena Fischer, physiotherapist, Thu/Fri 09:00–17:00 |
| Clinic | Mon–Fri 08:00–18:00, lunch 12:30–13:30; closed at weekends and on the **7th working day** ("Staff training day", listed on the booking page) |
| Ava's upcoming appointments | Rosa Delgado, next working day 10:00, blood test · Dr Wilk, his 2nd working day, 14:00, **30 minutes**, knee injection · Dr Nandakumar, her 6th working day, 08:30 · Dr Nandakumar, her 3rd working day, 11:00, **cancelled** |
| Leo's | Dr Achebe, her 3rd working day, 15:00, pre-school vaccinations |
| Other bookings | Rosa Delgado 08:00, 08:15, 08:30, 08:45 on the next working day (Grace Liu, Harriet Cole, Felix Grant, Ines Moreau) |
| Reception's day list | Today (or the next working day at weekends): Ben Okafor twice (Rosa 09:00, GP 15:30), Grace Liu GP 09:00, Harriet Cole GP 11:15 (**cancelled**), Felix Grant GP 14:00, Ines Moreau Rosa 10:30 |
| Repeat medicines | Sertraline (last ordered on a Thursday 7–13 days ago) · Levothyroxine (ordered day −10) · Salbutamol inhaler (review **overdue** since day −14) · Omeprazole (ordered day −35). Up to 56 tablets/capsules or 2 inhalers per request |
| Test results | Full blood count (platelets 410, range 150–400: high) · Thyroid (TSH **4.0**, range 0.4–4.0) · HbA1c 41, previously 44 · Cholesterol 5.9 (up to 5.0: high) · Vitamin D 38 (50–175: low, unread) · result 6 is Ben Okafor's liver function test |
| Messages | "Do I need to fast for my blood test?" with an unread reply from Kai · "Fit note for work" (read) |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a download,
a reload or the receptionist's account; **Expert** needs date arithmetic, a checksum, or a calendar or time edge.

## The bugs

### Finding a clinician

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | Search only matches the start of the name | Clinicians: search "Wilk" (or "Achebe") | Dr Tomasz Wilk | "0 clinicians" ("Dr T" finds him) | Low | Medium | `server.py` `Store.doctors` |
| BUG-02 | Specialty filter only checks each clinician's first specialty | Clinicians: Specialty = Vaccinations | Rosa Delgado and Dr Helen Achebe | Only Rosa Delgado (Achebe lists it second; "Asthma" finds nobody) | Low | Medium | `server.py` `Store.doctors` |
| BUG-03 | Profile shows the wrong working days | Dr Nandakumar's profile: Working week | Monday, Tuesday, Thursday, Friday (as on the list) | Tuesday, Wednesday, Friday, Saturday | Medium | Hard | `static/doctor.js` (Monday = 1 used as an index) |
| BUG-04 | "Next available" ignores bookings | Rosa Delgado's card: Next available; then book her that day | Her first free time (09:00) | "08:00", which is booked | Medium | Hard | `server.py` `Store.next_free` |
| BUG-05 | Clinicians on leave can be booked | Dr Okoro's profile says he's on leave; book him for tomorrow | No times until he's back | Next available tomorrow; a full day of free times; booking works | High | Hard | `server.py` `Store.closed_note` |

### Booking

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-06 | The clinic's closed day can be booked | Book: pick the day listed under Closed days (staff training) | "Closed", no times | A full day of free times; booking works | High | Hard | `server.py` `Store.closed_note` |
| BUG-07 | A long appointment can run past closing | Book Dr Nandakumar, Long (30 minutes), 17:45 | 17:45 not offered (must end by 18:00) | Booked; Appointments shows 17:45–18:15 | Medium | Expert | `server.py` `Store.free` |
| BUG-08 | 12:30 is offered though lunch starts then | Book any full-day GP, standard | Times stop at 12:15 and restart at 13:30 | 12:30 is offered | Medium | Hard | `server.py` `slot_starts` |
| BUG-09 | Two appointments at the same time | Ava has Rosa at 10:00 on the next working day; book a GP at 10:00 that day | Refused | Booked | Medium | Medium | `server.py` `Store.book` |
| BUG-10 | Booking for a child books it for you | Book, Who is it for = Leo Thornton | Appointment in Leo's name | Confirmation says "for Leo Thornton"; Appointments lists it for Ava, and Leo's family entry doesn't have it | High | Medium | `server.py` `Store.book` (the id arrives as text) |
| BUG-11 | Same-day appointments can be booked online | Book: the day picker starts today; pick today (a weekday) | Only from tomorrow ("call at 8am") | Today's times offered and booked | Medium | Medium | `server.py` `Store.window_note`, `static/book.js` (`min`) |
| BUG-12 | Confirmation shows 15 minutes for a long appointment | Book a Long (30 minutes) appointment | "…, 10:00–10:30" | "…, 10:00–10:15" (Appointments says 10:30) | Low | Medium | `static/book.js` (always adds 15) |

### Your appointments

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-13 | Late fee charged the day before | Cancel Rosa's 10:00 on the next working day (the dialog says "No fee") | No fee (only on the day) | "A late-cancellation fee of £15.00 has been added"; Your details shows £15 | High | Hard | `server.py` `Store.cancel` |
| BUG-14 | A cancelled time isn't released | Cancel Rosa's 10:00, then Book Rosa that day | 10:00 offered again | 10:00 missing (the cancelled 11:00 with Dr Nandakumar is blocked too) | High | Hard | `server.py` `Store.taken` |
| BUG-15 | Moving an appointment can double-book | Move Rosa's 10:00; the list offers 08:00–08:45 (booked; Book doesn't offer them); pick 08:00 | Only free times offered | Moved; reception's list shows Ava and Grace Liu both at 08:00 | Critical | Hard | `server.py` `Store.free` (`moving`) |
| BUG-16 | Moving a long appointment shortens it | Move Dr Wilk's 30-minute knee injection to another day | Still 30 minutes | "(15 min)", e.g. 14:00–14:15 | Medium | Hard | `server.py` `Store.reschedule`, `static/appointments.js` (length not sent) |
| BUG-17 | Upcoming isn't in date order | Appointments: Upcoming | Soonest first | Sorted by time of day: the 08:30 two weeks away comes first | Low | Medium | `server.py` `Store.appointments` |
| BUG-18 | Calendar file has the wrong time | Add to calendar on Dr Wilk's 14:00 appointment | DTSTART …T140000 | DTSTART …T020000 (2 am) | High | Hard | `server.py` `Store.ics` (`%I`) |
| BUG-19 | Home counts cancelled appointments | Home: Your upcoming appointments | 3 | 4 (includes the cancelled one) | Low | Medium | `server.py` `Store.home` |
| BUG-32 | Children's appointments are missing | Family: Leo's next appointment; then Appointments | Leo's 15:00 with Dr Achebe listed | Not listed | High | Hard | `server.py` `Store.appointments` |

### Repeat prescriptions

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-20 | No limit on quantity | Order Omeprazole, 200 | Refused (56 at most) | "Requested 200 × Omeprazole…" | Critical | Medium | `server.py` `Store.request_prescription` |
| BUG-21 | The 28-day rule isn't applied | Order Levothyroxine (ordered day −10) | Refused until day +18 | Requested | High | Hard | `server.py` `Store.request_prescription` |
| BUG-22 | "Next order from" is 30 days, not 28 | Prescriptions: Levothyroxine | Next order from day +18 (ordered + 28 days) | Day +20 (ordered + 30) | Medium | Expert | `static/prescriptions.js` |
| BUG-23 | Medicines with an overdue review are issued | Order Salbutamol (review overdue notice shown) | Refused: book a review | Requested | Critical | Hard | `server.py` `Store.request_prescription` |
| BUG-24 | Ready date counts weekends | Your requests: Sertraline, requested on a Thursday | Ready Monday (2 working days) | Ready Saturday; new requests on a Thursday or Friday also land on a weekend | Medium | Expert | `data.py` `ready_date` |

### Test results

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-25 | A value at the upper limit is flagged High | Thyroid function: TSH 4.0, range 0.4–4.0 | In range (limits included) | High | Medium | Hard | `server.py` `flag` |
| BUG-26 | Results list ignores high values | Results: Full blood count; open it | "1 value outside range" (platelets 410 > 400) | "All in range" (Cholesterol too) | High | Hard | `static/results.js` (counts Low only) |
| BUG-27 | Another patient's result by changing the id | Open `/result?id=6` | Not found | Ben Okafor's liver function test with his NHS number | Critical | Hard | `server.py` `Store.result` |
| BUG-28 | Trend arrow is reversed | HbA1c: 41, previous 44 | "Down from 44" | "Up from 44" | Low | Medium | `static/result.js` |

### Messages

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-29 | A blank message can be sent | New message, text of only spaces/blank lines | "Write your message" | "Sent."; an empty message in the conversation | Low | Medium | `server.py` `Store.send_message`, `static/messages.js` |
| BUG-30 | Opening a reply doesn't mark it read | Open "Do I need to fast…", reload | Badge gone, no "New reply" | Messages badge still 1; "New reply" still shown; Home still 1 unread | Low | Medium | `server.py` `Store.read_thread` |

### Family and your details

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-31 | A 15-year-old is refused | Family: add a child born 16 years ago tomorrow (15 today) | Added (under 16) | "Children aged 16 or over need to register…" | Medium | Expert | `server.py` `Store.add_child` (years only) |
| BUG-33 | NHS check digit isn't checked | Your details: NHS 943 476 5918 (5919 is valid) | "That NHS number isn't valid" | Saved | High | Expert | `server.py` `nhs_ok` |
| BUG-34 | Date of birth in the future accepted | Your details: date of birth next year | Refused | Saved | Low | Medium | `server.py` `Store.save_profile` |
| BUG-35 | Phone number isn't validated | Your details: phone "call me later" | Refused (11-digit UK number) | Saved | Medium | Medium | `server.py` `Store.save_profile` |

### Reception desk (Kai)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-36 | Reception sees test results | As Kai, Find a patient: "Thornton" | Contact details and appointments only | "Latest results: Vitamin D 38 nmol/L Low; Full blood count…" | High | Hard | `server.py` `Store.find_patients` |
| BUG-37 | Check-in marks all the patient's appointments | As Kai, Check in Ben Okafor's 09:00 | Only the 09:00 arrived | His 15:30 is "Arrived" too | High | Hard | `server.py` `Store.check_in` |
| BUG-38 | Blocked times can still be booked | As Kai, keep Rosa 11:00 free on a later day; as Ava, Book Rosa that day | 11:00 not offered | Offered and booked | High | Hard | `server.py` `Store.free` |
| BUG-39 | Day list CSV includes cancelled appointments | As Kai, Download the day list (CSV) | Harriet Cole's cancelled 11:15 left out | Listed like any other, with no status | Medium | Hard | `server.py` `Store.day_csv` |

### Errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-40 | An unknown clinician hangs on "Loading…" | Open `/doctor?id=99` | "We couldn't find that clinician" | "Loading…" forever and a JavaScript error | Low | Medium | `static/doctor.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug or a page: 401 on wrong passwords, 400 when a form is refused (such as the
  15-year-old in BUG-31), 404 and the JavaScript error on an unknown clinician (BUG-40), 403 on `/desk` as Ava and
  on patient pages as Kai, 404 on unknown pages.
- Bugs that combine: BUG-07 bookings at 17:45 also show the BUG-12 end time; a child booked under BUG-10 lands in
  Ava's own list; BUG-04 and BUG-05 both make Dr Okoro's "next available" wrong; other requests in the history with a
  weekend "ready" date are BUG-24.
- At weekends there is no same-day booking to try (BUG-11 needs a weekday), and the reception desk shows the next
  working day's list. BUG-31 can't be shown on 31 December.
- Results show limits like "4" for 4.0; date pickers show dates in the browser's format.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo clinic for QA testing — not real medical advice" in the footer and the demo accounts on the login page.

By area: finding a clinician 5, booking 7, your appointments 8, repeat prescriptions 5, test results 4, messages 2,
family and your details 4, reception desk 4, errors 1.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 4, High 13, Medium 13, Low 10.
