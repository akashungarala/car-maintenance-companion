# E4 — Completion and service history

**Goal:** marking something done makes every future answer more accurate, without the user knowing
that is what they did.

This is the epic the product's central bet lives in. Every date on the dashboard is currently an
assumption; this is where assumptions become facts, and where the usage rate quietly corrects
itself.

## The mechanic

When somebody marks an item done, we ask for one number they are already looking at — the
odometer. That single act does three things:

1. **Records the service.** The item's `last_done_at` and `last_done_mileage` become real, and
   `is_baseline` clears, so the dashboard stops saying "assumed".
2. **Re-anchors the projection.** The vehicle's odometer reading is updated, so every other item's
   projected date improves too.
3. **Recalibrates the usage rate.** We now know how far this car actually travelled between two
   known readings, which is better information than the guess made when it was added.

The third is the point, and the user is never asked to do it. They came to record an oil change.

## Product decisions

**We ask for the odometer, and only the odometer.** Not the cost, not the garage, not a note. Every
additional field is a reason to close the sheet, and the one number we need is the one on the
dashboard they are standing next to.

**Recalibration needs at least 30 days of history.** Below that the arithmetic is dominated by
noise: a person who marks something done a week after adding their car, having driven to the coast
and back, would have their annual mileage tripled by one weekend. Thirty days is short enough to
correct a badly wrong initial guess within the first month, and long enough that a single unusual
week does not dominate.

**A reading lower than the last one is rejected, not absorbed.** Odometers do not run backwards.
It is a typo — 4820 for 48200 — and silently accepting it would move every projected date on that
car years into the future, which is the kind of wrong that is never noticed.

**The recalibrated rate is clamped to 500–60,000 miles a year.** Outside that range the input is
almost certainly wrong rather than the driver unusual, and a projection built on 400,000 miles a
year is worse than one built on a stale guess.

**Marking done is undoable.** People tap the wrong row. The history entry can be deleted, which
restores the previous state — and knowing that is possible is what makes the primary action feel
safe enough to use quickly.

**We record history, not just the latest state.** "When did I last do this?" is a question people
ask standing in a garage forecourt, and the answer is worth more than the storage it costs.

## What this deliberately does not do

**It does not ask for past services.** Retroactive entry stays out of the MVP (plan §MVP). Someone
who wants to enter three years of records is welcome to, later; asking a new user for them is how
the first session ends without a vehicle being added.

**It does not average across multiple windows.** The rate is computed from the last known reading
to this one. A longer history would give a steadier estimate, and it would also mean storing a
reading series and explaining which window we used. If the rate proves too jumpy in practice, that
is the fix — but building it before there is evidence would be solving a problem we have not
observed.

## Stories

| ID         | Story                                     | Area               |
| ---------- | ----------------------------------------- | ------------------ |
| **E4-001** | Mark an item done, recalibrating the rate | backend            |
| **E4-002** | Mark-done UX specification                | ux                 |
| **E4-003** | The mark-done sheet                       | frontend           |
| **E4-004** | Service history                           | backend + frontend |

## Acceptance

- [ ] Marking done records the date and mileage, and clears the assumed flag
- [ ] The vehicle's odometer reading is updated to the new reading
- [ ] With 30+ days of history, the annual mileage is recalculated from actual travel
- [ ] With less than 30 days, the rate is left alone
- [ ] A reading below the previous one is rejected with a message naming the problem
- [ ] A recalculated rate outside 500–60,000 is clamped rather than stored
- [ ] Completing an item creates a history entry
- [ ] A user cannot complete, or see history for, another user's item
