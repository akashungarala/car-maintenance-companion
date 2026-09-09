# E3 — Projection

**Goal:** answer "what does my car need right now?" without asking the user to keep a logbook.

This epic is the product. Everything before it was scaffolding for this question, and if the answer
is not trustworthy, nothing else matters.

## The mechanic

```
estimated_mileage(t) = odometer + (annual_mileage / 365) × days since the reading
due_date(item)       = the earlier of the date projected from miles and the date from months
```

One odometer reading, one usage rate, and no further input. That is the whole bet: that a
projection accurate to within a week or two is useful enough to act on, and that not having to
enter mileage is what makes people keep using it.

## The decision this epic turns on: what do we assume about a new car?

Somebody adds a 2019 Civic with 48,200 miles. We do not know when its oil was last changed. There
are three honest options and one dishonest one.

**Ask them.** Highest accuracy, and a wall of questions at exactly the moment a new user is
deciding whether this is worth the effort. Eight items, each needing a date nobody remembers.

**Assume everything is overdue.** A first screen that is entirely red, mostly wrongly. It destroys
trust in the one number the product exists to provide, on the first impression.

**Assume everything was just done.** A comfortable, quiet first screen — and a lie. It says
"nothing is due" about a car that might need oil today.

**What we do: baseline from today, and say so.** Items are seeded as "tracking from today" rather
than as "done today". The projection runs from the vehicle's own reading, so the dates are real,
but the UI is explicit that we are assuming rather than knowing — and the first time the user marks
something done (E4), the assumption is replaced by fact.

This is the honest option, and it is also the one that degrades correctly: a user who ignores it
gets sensible-looking dates, and a user who cares can fix them by doing the thing they were going
to do anyway.

**The cost, stated plainly:** for a new user with a car that genuinely needs an oil change today,
we will not say so. We are trading a false negative for the false positives of the alternative, on
the grounds that a product which cries wolf on day one is uninstalled on day one.

## Seeded intervals

Generic, not manufacturer-specific — no free source of OEM schedules exists (plan §1.1, ADR-0006).
These cover the common cases across mainstream vehicles.

| Item                      | Miles  | Months         |
| ------------------------- | ------ | -------------- |
| Engine oil & filter       | 5,000  | 6              |
| Tire rotation             | 6,000  | —              |
| Cabin air filter          | 15,000 | 12             |
| Engine air filter         | 30,000 | —              |
| Brake fluid               | 30,000 | 36             |
| Coolant                   | 60,000 | 60             |
| Registration / inspection | —      | 12             |
| Wash & interior clean     | —      | ~0.7 (21 days) |

Whichever limit arrives first wins. A car driven 25,000 miles a year needs oil on mileage; one
driven 3,000 needs it on time. Using only miles would tell a low-mileage driver their year-old oil
is fine, which is wrong in a way that damages an engine.

## Status bands

| Status       | Meaning                 |
| ------------ | ----------------------- |
| **Overdue**  | The due date has passed |
| **Due soon** | Within 30 days          |
| **Upcoming** | Everything else         |

Thirty days because it is long enough to book a garage and short enough to still be true — the
projection's error grows with distance, so a "due in 6 months" is a guess and a "due in 3 weeks" is
close to a fact.

## Stories

| ID         | Story                                 | Area     |
| ---------- | ------------------------------------- | -------- |
| **E3-001** | Interval templates and seeding        | backend  |
| **E3-002** | The projection engine                 | backend  |
| **E3-003** | Seed a plan when a vehicle is created | backend  |
| **E3-004** | `GET /vehicles/{id}/plan`             | backend  |
| **E3-005** | Dashboard UX specification            | ux       |
| **E3-006** | The dashboard                         | frontend |

## Acceptance

- [ ] The engine is pure, and its tests do not touch a database or a clock
- [ ] Mileage estimation is exact at the reading date and grows linearly
- [ ] The earlier of the mileage-based and time-based due dates wins
- [ ] An item with only a mileage interval never produces a time-based date, and vice versa
- [ ] Creating a vehicle seeds its plan in the same transaction
- [ ] A plan belongs to its vehicle's owner and nobody else
- [ ] The dashboard groups by Overdue, Due soon and Upcoming, and says when it is assuming
