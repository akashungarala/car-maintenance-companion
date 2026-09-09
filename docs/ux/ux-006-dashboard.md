# UX-006 — The dashboard

**Story:** [E3-006](../product/e3-projection.md) · **Mockup:** `mockups/ux-006-dashboard.html`

## User goal

Find out what my car needs right now, in one glance, without doing any arithmetic.

## Information architecture

Reached from a vehicle in the garage. This is the screen the product exists for; everything else
is either how you got here or how you keep it accurate.

## Layout

The vehicle and its estimated mileage at the top, then three groups in the order that matters:
**Overdue**, **Due soon**, **Upcoming**. Groups with nothing in them are not rendered — an empty
"Overdue" heading is a reassuring thing to read, and reassurance is not what an empty section is
for.

## Components

| Component         | Purpose                              | Notes                                                   |
| ----------------- | ------------------------------------ | ------------------------------------------------------- |
| Estimated mileage | The number they cannot otherwise get | Labelled "estimated", never presented as a reading      |
| Group heading     | Bands the list                       | Carries a count, so the shape is legible before reading |
| Item row          | One thing the car needs              | Name, projected date, projected mileage                 |
| Assumed marker    | Honesty                              | On every item we have not been told about               |

## Interaction flow

1. The page loads and asks for the vehicle's plan
2. **200** → groups render
3. **401** → go to sign-in
4. **404** → the vehicle is gone or was never theirs; back to the garage
5. **5xx** → retry, no redirect

## States

### Default

Three groups, most urgent first.

### Loading

Three skeleton rows under a single heading. Not a spinner: the page's shape is known.

### Empty

Impossible in practice — a vehicle always has eight seeded items — but rendered defensively as
"Nothing scheduled" rather than a blank area, because "impossible" states are what appear after a
data migration.

### Error

A retry, and no redirect unless the API says 401.

### Validation

Not applicable.

### Success

Not applicable: this screen reports rather than acts.

### Confirmation

Not applicable in this story. Marking an item done arrives in E4.

## The honesty requirement

Every seeded item carries `is_assumed`. Until somebody marks it done, we are guessing when it was
last serviced — and the interface must say so, in words, next to the date:

> Engine oil & filter — **due 8 February 2027** · from 48,200 mi
> _Assumed: we started tracking this when you added the car._

This is the single most important detail on the screen. A projected date presented as fact is a
lie the product tells about the thing it exists to be trusted on, and the first time a user
discovers it was a guess is the last time they believe any of the other dates.

## Responsive

| Breakpoint      | Behaviour                                              |
| --------------- | ------------------------------------------------------ |
| 375px (primary) | One column; date and mileage stack under the item name |
| 768px           | Name left, date and mileage right-aligned on one row   |
| 1280px          | Unchanged; content capped so rows do not stretch       |

## Accessibility

- **Structure:** `<h1>` vehicle, `<h2>` per group, items as a `<ul>` per group — so a screen
  reader can skip between bands and hear how many are in each.
- **Not colour alone:** "Overdue" is a word, not a red dot. Colour reinforces the heading; it never
  carries the meaning.
- **Dates:** written out (`8 February 2027`), not `08/02/27`, which is ambiguous across locales.
- **Assumed marker:** real text, not a tooltip or an icon — the thing it says is too important to
  hide behind a hover that touch devices do not have.

## Acceptance criteria

- [ ] Given a plan, then items appear under Overdue, Due soon and Upcoming
- [ ] Given a band with no items, then its heading is not rendered
- [ ] Given an item, then its projected date and projected mileage are shown
- [ ] Given an item with no due date, then it reads "not scheduled" rather than showing a date
- [ ] Given an assumed item, then the screen says so in words next to the date
- [ ] Given a 401, then the browser goes to sign-in
- [ ] Given a 500, then a retry is offered and no redirect happens
- [ ] Given the page is loading, then no dates are rendered
