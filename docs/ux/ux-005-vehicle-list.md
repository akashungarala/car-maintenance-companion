# UX-005 — The garage

**Story:** [E2-005](../product/e2-garage.md#e2-003-to-e2-005--the-interface) · **Mockup:**
`mockups/ux-005-vehicle-list.html`

## User goal

See what the app knows about my cars, and get to one of them.

## Information architecture

The home of the signed-in application, replacing the placeholder from E1-003. Every other screen
is reached from here.

## Layout

Header with the signed-in address and sign-out, then either the empty state or a list of vehicle
cards, with "Add a vehicle" always reachable.

## Components

| Component     | Purpose              | Notes                                                                               |
| ------------- | -------------------- | ----------------------------------------------------------------------------------- |
| Vehicle card  | One car              | Nickname prominent, year/make/model beneath, mileage last                           |
| Add a vehicle | The primary action   | A button in the header once a list exists; the focus of the empty state before that |
| Empty state   | First-visit guidance | Explains what to do and why it is worth doing                                       |

## States

### Default

Cards in a single column on mobile, two across on wider screens, newest first. Newest first because
the most recently added vehicle is the one the user is currently thinking about.

### Loading

Two skeleton cards. Not a spinner: the shape of what is coming is known, and showing it makes the
wait feel like loading rather than like nothing happening.

### Empty

The most important screen in this story. A first-time user arrives here immediately after signing
in, and a blank page with a button is an instruction to guess.

> **Add your first car**
> Tell us what you drive and roughly how much, and we will keep track of what it needs and when.
> [Add a vehicle]

It states the exchange: two pieces of information, in return for the thing they came for.

### Error

A retry, never a redirect to sign-in unless the API says 401. A failed list is not a failed
session.

### Validation

Not applicable.

### Success

Arriving here after adding a vehicle is the success. The new vehicle is at the top of the list.

### Confirmation

None in this story: nothing here deletes anything yet.

## Responsive

| Breakpoint      | Behaviour                                                     |
| --------------- | ------------------------------------------------------------- |
| 375px (primary) | One card per row; "Add a vehicle" full width beneath the list |
| 768px           | Two cards per row; the add button moves into the header       |
| 1280px          | Unchanged from 768px; content capped so cards do not stretch  |

## Accessibility

- **List semantics:** the vehicles are a `<ul>`, so a screen reader announces how many there are.
- **Heading order:** one `<h1>` for the garage, `<h2>` per vehicle. No levels skipped.
- **Loading:** skeletons are `aria-hidden` inside a container marked `aria-busy`.
- **Contrast:** the secondary line under each nickname meets AA — it is quieter in emphasis, not
  in legibility.

## Acceptance criteria

- [ ] Given no vehicles, then the empty state explains what to do and offers the add action
- [ ] Given vehicles, then each card shows nickname, year/make/model and mileage
- [ ] Given vehicles, then they are listed newest first
- [ ] Given a 401 from the list, then the browser goes to sign-in
- [ ] Given a 500 from the list, then a retry is offered and no redirect happens
- [ ] Given the list is loading, then no vehicle data is rendered
