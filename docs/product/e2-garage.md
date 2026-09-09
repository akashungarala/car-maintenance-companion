# E2 — Garage

**Goal:** a person can tell the app what they drive, and see it.

This is the first epic that delivers something a user came for. It is also where the product's
central bet gets its scaffolding: the projection engine in E3 needs a mileage reading and a usage
rate, and both are captured here.

## Stories

| ID         | Story                        | Area     | Depends on     |
| ---------- | ---------------------------- | -------- | -------------- |
| **E2-001** | Vehicle model and migration  | backend  | E1             |
| **E2-002** | `POST` and `GET /vehicles`   | backend  | E2-001         |
| **E2-003** | Add-vehicle UX specification | ux       | —              |
| **E2-004** | Add-vehicle form             | frontend | E2-002, E2-003 |
| **E2-005** | Vehicle list and empty state | frontend | E2-002, E2-003 |

---

## What a vehicle is

| Field                   | Why it exists                                                     |
| ----------------------- | ----------------------------------------------------------------- |
| `nickname`              | What the user calls it. Optional — defaults to "2019 Honda Civic" |
| `year`, `make`, `model` | Identity, and later the basis for interval templates              |
| `odometer`              | The single reading the whole projection is anchored to            |
| `odometer_recorded_at`  | When that reading was taken                                       |
| `annual_mileage`        | How much they drive. The other half of the projection             |

### Product decisions

**We do not ask when the odometer reading was taken.** It is recorded as now. People type in the
number they just read off the dashboard, or the one they remember from this week; asking them to
date it adds a field to justify a precision the input does not have. A reading that is a few days
stale moves a projected due date by hours. Being wrong by hours does not matter here — being
annoying enough that someone abandons the form does.

**Annual mileage is offered as three choices, not a text box.** Low (6,000), Average (12,000),
High (18,000), with an exact figure available for anyone who knows theirs. Almost nobody knows
their annual mileage, and a required number nobody knows is a wall. Three plausible options that
can be corrected later is the difference between finishing the form and closing the tab.

**Nickname is optional and defaulted.** Most people have one car and do not name it. Requiring a
name for something they think of as "the car" is a question with no right answer.

**VIN is not collected** (see the plan's §1.1). It identifies the vehicle but yields no maintenance
schedule without a paid data source, and every field that earns nothing is a field that costs
completion.

**No vehicle limit.** The MVP targets one to three vehicles, but enforcing that would mean writing
an error message for a case that harms nobody.

### Ownership

Every query for a vehicle goes through one helper that scopes it to the signed-in user. Not by
convention — by there being no other way to build the query.

Ad-hoc `WHERE user_id = ...` filters are how IDOR bugs ship: the safe version and the unsafe
version look nearly identical, the unsafe one works perfectly in every test written by someone who
owns the data, and it is discovered by a stranger. Making the scoped path the only path means the
mistake cannot be made by omission.

A test asserts that one user cannot read another's vehicle, and that test is expected to exist for
every resource added from here on.

---

## E2-001 — Vehicle model and migration

**Acceptance**

- [ ] A vehicle belongs to exactly one user, and deleting the user removes their vehicles
- [ ] `year` is constrained to a plausible range; a typo of `219` is rejected
- [ ] `odometer` cannot be negative
- [ ] `annual_mileage` cannot be negative
- [ ] Migration applies and reverses; models and migrations describe the same schema

## E2-002 — `POST` and `GET /vehicles`

**Acceptance**

- [ ] `POST /vehicles` creates a vehicle for the signed-in user and returns it
- [ ] `GET /vehicles` returns only that user's vehicles, newest first
- [ ] Both return 401 without a session
- [ ] A user cannot read, or create for, another user — asserted directly
- [ ] Invalid input returns 422 naming the field
- [ ] `odometer_recorded_at` is set server-side, never accepted from the client

## E2-003 to E2-005 — the interface

Specified in [UX-004](../ux/ux-004-add-vehicle.md) and [UX-005](../ux/ux-005-vehicle-list.md).

**Acceptance**

- [ ] The garage lists vehicles with their nickname and mileage
- [ ] The empty state explains what to do rather than showing an empty box
- [ ] Adding a vehicle returns to the list with the new vehicle present
- [ ] Validation errors appear against the field that caused them
- [ ] The form survives a failed submission with its values intact
