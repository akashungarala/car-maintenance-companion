# UX-007 — Marking maintenance done

**Story:** [E4-003](../product/e4-completion.md) · **Mockup:** `mockups/ux-007-mark-done.html`

## User goal

Record that I have just had something done, in a few seconds, standing next to the car.

## Information architecture

Opened from any item on the dashboard. Returns to the dashboard, with that item moved out of
Overdue and its "assumed" note gone.

## Layout

A sheet over the dashboard rather than a separate page. The context — which car, which item — is
what makes the single question legible, and a full-page form would throw it away.

## Components

| Component | Purpose                     | Notes                                                             |
| --------- | --------------------------- | ----------------------------------------------------------------- |
| Item name | Says what is being recorded | Not editable here; the sheet answers one question                 |
| Odometer  | The only input              | Prefilled with the current estimate, `inputmode="numeric"`        |
| Date      | When it was done            | Defaults to today; a stepper back for "actually it was last week" |
| Save      | Records it                  | "Mark as done"                                                    |

## The single question

We ask for the odometer and nothing else. Not the cost, not the garage, not a note.

Every additional field is a reason to close the sheet, and the number we need is the one on the
dashboard they are standing next to. It also happens to be the number that silently corrects the
usage rate — but that is our business, not something to explain in the interface.

**The field is prefilled with our current estimate.** Somebody who has not looked at their
dashboard can accept it; somebody who has can correct it in two taps. A blank field asks everyone
to walk outside.

## States

### Default

Item name, odometer prefilled, date set to today, one button.

### Loading

Button reads "Saving…" and is disabled. Fields stay enabled.

### Empty

Not applicable.

### Error

A message inside the sheet, values kept. The sheet does not close on failure — closing it would
lose what they typed and leave them unsure whether it saved.

### Validation

The one case that matters is a reading lower than the last:

> **That is lower than the last reading (48,200 miles).** Check the number — odometers do not go
> backwards.

Said in the user's terms, naming the previous value so the typo is visible. `4820` for `48200` is
the mistake this is for, and the message shows them exactly what to compare against.

### Success

The sheet closes and the dashboard is behind it, updated. The item has moved band, and its
"assumed" line is gone — which is the confirmation. A toast saying "saved" would be a second
message about something already visible.

### Confirmation

None on save. Undo lives in the history list, which is the honest place for it: a confirmation
dialogue before a reversible action is friction pretending to be safety.

## Responsive

| Breakpoint      | Behaviour                                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------------------------ |
| 375px (primary) | Sheet from the bottom, full width, 44px targets; the odometer field is focused but the keyboard is not forced open |
| 768px           | Centred dialogue, 420px                                                                                            |
| 1280px          | Unchanged                                                                                                          |

## Accessibility

- **Dialogue semantics:** `role="dialog"`, `aria-modal="true"`, labelled by the item name.
- **Focus:** moves into the sheet on open and returns to the triggering row on close, so a keyboard
  user is not dropped at the top of the page.
- **Escape closes**, and so does the backdrop — with the values discarded, which is safe because
  nothing has been sent.
- **Errors** are `role="alert"` and linked with `aria-describedby`.

## Acceptance criteria

- [ ] Given an item, when its row is activated, then a sheet opens naming that item
- [ ] Given the sheet, then the odometer is prefilled with the current estimate
- [ ] Given a lower reading, when saved, then a message names the previous value and nothing is sent
- [ ] Given a valid reading, when saved, then the sheet closes and the dashboard reflects it
- [ ] Given a server error, then the sheet stays open with the values intact
- [ ] Given the sheet is open, then Escape closes it
- [ ] Given the sheet closes, then focus returns to the row that opened it
