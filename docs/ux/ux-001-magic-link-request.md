# UX-001 — Request a magic link

**Story:** [E1-001](../product/e1-identity.md#e1-001--request-a-magic-link) · **Mockup:**
`mockups/ux-001-magic-link-request.html`

## User goal

Get into my garage by typing my email address, without inventing or remembering a password.

## Information architecture

The entry point to the entire application. An unauthenticated visit to any route lands here
(E1-003). After a successful request the user leaves the browser for their email client and
returns via the link (E1-002), so this screen's real job is to end well: the confirmation is the
last thing they see before switching apps, and it has to survive being read on a phone lock screen
thirty seconds later.

## Layout

One column, centred, nothing else on the page. No navigation, no marketing, no cookie banner. The
eye should reach, in order: what this is, the email field, the button.

The form is a single field on purpose. Every additional element on a sign-in screen is a chance to
hesitate.

## Components

| Component          | Purpose                         | Notes                                                                                  |
| ------------------ | ------------------------------- | -------------------------------------------------------------------------------------- |
| Heading            | Says what this is               | "Sign in to your garage" — not "Welcome back", which is wrong for a first-time user    |
| Email field        | The only input                  | `type="email"`, `autocomplete="email"`, `inputmode="email"`, autofocus on desktop only |
| Submit button      | Sends the request               | Label "Email me a link", not "Submit" — it names what happens next                     |
| Inline error       | Validation and failure messages | Below the field, associated by `aria-describedby`                                      |
| Confirmation panel | Replaces the form on success    | Names the exact address, so a typo is visible                                          |

## Interaction flow

1. User types an email address
2. User submits (button, or Enter)
3. Client validates the shape only — presence and a plausible address
4. `POST /auth/magic-link` with `{ email }`
5. **202** → the form is replaced by the confirmation panel
6. **429** → rate-limit message with the wait derived from `Retry-After`
7. **5xx or network failure** → error message, form preserved with the address still in it

The response is deliberately identical for registered and unregistered addresses, so this screen
cannot report "no such account" (see the product decision on enumeration).

## States

### Default

Heading, empty field, enabled button. No error text occupying space before anything has gone wrong.

### Loading

Button shows a spinner and the label becomes "Sending…". Button and field both disabled to prevent
a second submit. **The form stays visible** — it is not replaced until we know the request
succeeded, so a failure returns the user to a filled-in form rather than a blank one.

### Empty

Not applicable: a single-field form has no empty state distinct from Default.

### Error

Request failed (5xx, timeout, offline). Message: _"Something went wrong sending your link. Please
try again."_ The field keeps its value. The button returns to its default label.

Offline is worth distinguishing — _"You appear to be offline."_ — because the user's next action is
different: wait, rather than retry.

### Validation

Empty: _"Enter your email address."_
Malformed: _"That does not look like an email address."_

Validation fires on submit, not on keystroke. Validating while someone is halfway through typing
tells them they are wrong before they have finished being right.

### Success

The form is replaced by a confirmation panel:

> **Check your email**
> We sent a link to **someone@example.com**. It works once and expires in 15 minutes.
>
> Wrong address? [Use a different one]

Naming the address is what makes a typo recoverable — the most common failure here is not an error,
it is a link sent somewhere the user cannot read. "Use a different one" returns to Default with the
field cleared.

### Confirmation

The success panel is the confirmation. Nothing here is destructive, so no confirm-before-acting
step exists.

### Rate limited

Not one of the seven, but real: **429** shows _"Too many attempts. Try again in N seconds."_ with N
from `Retry-After`, counting down. Saying "too many attempts" without saying how long turns a
temporary limit into an apparent dead end.

## Responsive

| Breakpoint      | Behaviour                                                                                                                                                                        |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 375px (primary) | Full-width card with 16px gutters; field and button both full width and stacked; button ≥ 44px tall for touch; no autofocus, which would raise the keyboard and hide the heading |
| 768px           | Card constrained to 420px, vertically centred                                                                                                                                    |
| 1280px          | Unchanged from 768px. A sign-in form gains nothing from a wide viewport                                                                                                          |

## Accessibility

- **Focus order:** heading (not focusable) → email field → submit button. On success, focus moves
  to the confirmation panel heading, which has `tabindex="-1"`, so a screen-reader user is not left
  focused on a button that no longer exists.
- **ARIA:** field has a visible `<label>`, not a placeholder acting as one. Errors are linked with
  `aria-describedby` and the field gets `aria-invalid="true"`.
- **Announcements:** the error region is `role="alert"`. The confirmation panel is
  `aria-live="polite"` — the change of view is not an emergency, and `assertive` would interrupt.
- **Contrast:** all text and the button meet AA at 4.5:1; the button's disabled state is
  distinguished by more than colour alone (label change plus spinner).
- Keyboard-only: Enter submits from the field. Nothing requires a pointer.

## Acceptance criteria

Written so Playwright can assert them directly.

- [ ] Given the page, when it loads, then the email field has an associated visible label
- [ ] Given an empty field, when submitted, then "Enter your email address." appears and no network
      request is made
- [ ] Given "not-an-email", when submitted, then a validation message appears and no network
      request is made
- [ ] Given a valid address, when submitted, then the button shows "Sending…" and is disabled
- [ ] Given a 202 response, then the confirmation panel appears containing the exact address typed
- [ ] Given a 202 response, then focus moves to the confirmation heading
- [ ] Given a 500 response, then an error message appears and the field still contains the address
- [ ] Given a 429 with `Retry-After: 45`, then the message names a wait of 45 seconds
- [ ] Given the confirmation panel, when "Use a different one" is clicked, then the form returns
      with an empty field
