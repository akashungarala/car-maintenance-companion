# UX-004 — Adding a vehicle

**Story:** [E2-004](../product/e2-garage.md#e2-003-to-e2-005--the-interface) · **Mockup:**
`mockups/ux-004-add-vehicle.html`

## User goal

Tell the app what I drive, in under a minute, without looking anything up.

## Information architecture

Reached from the garage — from the empty state on a first visit, or from "Add a vehicle" once
there is a list. Returns to the garage on success.

## Layout

A single column of fields in the order a person thinks about their car: what it is, how far it has
gone, how much they drive it. Nickname sits last because it is optional and thinking of a name is
the slowest part of the form.

## Components

| Component              | Purpose                  | Notes                                                                  |
| ---------------------- | ------------------------ | ---------------------------------------------------------------------- |
| Year / Make / Model    | Identity                 | Year is a number input with a sane range; make and model are free text |
| Current mileage        | Anchors every projection | Number input, `inputmode="numeric"`                                    |
| How much do you drive? | The usage rate           | Three cards plus "I know my exact mileage"                             |
| Nickname               | What they call it        | Optional, placeholder shows the default                                |
| Save                   | Submits                  | "Add vehicle", not "Submit"                                            |

## Interaction flow

1. The user fills in year, make, model and current mileage
2. They pick one of three driving levels, or enter an exact figure
3. Submit → `POST /vehicles`
4. **201** → return to the garage, new vehicle visible
5. **422** → field-level messages, values preserved
6. **401** → the session ended; go to sign-in
7. **5xx** → a form-level error, values preserved

## States

### Default

Empty fields, "Average" preselected. A preselected middle option means someone who does not know
their mileage — which is most people — can move on without deciding.

### Loading

The button becomes "Adding…" and is disabled. Fields stay enabled: a slow request is not a reason
to prevent someone correcting a typo they just noticed.

### Empty

Not applicable.

### Error

A form-level banner above the fields for failures that are not about a specific field. Values are
never cleared — losing five fields to a server hiccup is the fastest way to lose the user too.

### Validation

Per field, below the field, on submit. The messages name what is wrong in the user's terms:

- Year: _"Enter a year between 1900 and 2027."_
- Make / Model: _"Enter the make."_ / _"Enter the model."_
- Mileage: _"Enter the current mileage."_ and _"Mileage cannot be negative."_
- Exact annual mileage: _"Enter how many miles you drive a year."_

### Success

No success screen. The user returns to the garage and their vehicle is there, which is more
convincing than a message saying it worked.

### Confirmation

None on add. Adding a vehicle is not destructive and is trivially undone by deleting it.

## Responsive

| Breakpoint      | Behaviour                                                                              |
| --------------- | -------------------------------------------------------------------------------------- |
| 375px (primary) | Single column; driving-level cards stack full width; numeric keyboards via `inputmode` |
| 768px           | Year, make and model share a row; the rest stays stacked                               |
| 1280px          | Content capped at 640px — a wide form is a harder form to read                         |

## Accessibility

- **Grouping:** the driving-level choice is a `<fieldset>` with a `<legend>`, so a screen reader
  announces the question before the options rather than three unexplained buttons.
- **Errors:** each is linked with `aria-describedby`, and the field gets `aria-invalid`.
- **Focus:** on a failed submit, focus moves to the first field with an error — otherwise a
  keyboard user is left at the bottom of a form with messages they cannot see.
- **Labels:** every field has a real `<label>`. Placeholders are examples, never labels.

## Acceptance criteria

- [ ] Given the form, then every field has an associated visible label
- [ ] Given empty required fields, when submitted, then each shows its own message and no request is sent
- [ ] Given a year of 219, when submitted, then the year field shows a range message
- [ ] Given a negative mileage, when submitted, then the mileage field shows a message
- [ ] Given "Average" is preselected, then a user can submit without touching the driving question
- [ ] Given "I know my exact mileage", when chosen, then a number field appears and is required
- [ ] Given a valid submission, then the browser returns to the garage
- [ ] Given a 500, then a form-level error appears and every value is preserved
- [ ] Given a failed submit, then focus moves to the first field with an error
