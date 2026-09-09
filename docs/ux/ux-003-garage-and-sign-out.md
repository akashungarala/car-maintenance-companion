# UX-003 — Signed in, and signing out

**Story:** [E1-003](../product/e1-identity.md#e1-003--stay-signed-in-and-be-able-to-leave) ·
**Mockup:** `mockups/ux-003-garage-and-sign-out.html`

## User goal

See that the app knows who I am, and be able to end that.

## Information architecture

The first screen behind authentication, and the destination of a successful sign-in. In E2 it
becomes the garage proper; here it exists to make identity visible, which it currently is not.

## Layout

A header carrying the signed-in address and the way out, above a body that is honestly empty. The
empty state is the screen, not an accident of having no data yet.

## Components

| Component         | Purpose                | Notes                                               |
| ----------------- | ---------------------- | --------------------------------------------------- |
| Signed-in address | Makes identity visible | The one thing a user cannot otherwise verify        |
| Sign out          | Ends the session       | A button, not a link: it acts rather than navigates |
| Empty state       | Says what comes next   | Names the absence rather than showing a blank page  |

## Interaction flow

1. The page loads and asks the API who is signed in
2. **200** → the address is shown
3. **401** → the browser goes to the sign-in page
4. Sign out → the session is revoked, the cookie cleared, the browser goes to the sign-in page

## States

### Default

Header with the address, empty state below.

### Loading

A skeleton where the address will be, not a full-page spinner. The page's structure is known before
the answer is; replacing everything with a spinner throws that away and makes the screen flash on
every visit.

**Nothing about the user is rendered before the API answers.** Not from a cached value, not from
the cookie. A page that optimistically shows an address it has not confirmed will show the wrong
one to somebody eventually.

### Empty

This is the screen, deliberately:

> **Your garage is empty**
> Adding a vehicle is coming next. For now, this page exists to prove you are signed in.

Naming what is missing and why beats a blank area that reads as a page that failed to load.

### Error

If the identity check fails for any reason other than 401 — a 500, a timeout — the page shows a
retry rather than redirecting. Sending someone to sign in again because the server had a bad
moment means they sign in, land here, and are bounced out again.

### Validation

Not applicable: no input.

### Success

Signing out is confirmed by arriving at the sign-in page. A "you have been signed out" banner
there would be a message about the past on a screen about the future.

### Confirmation

None. Sign-out is trivially reversible — sign in again — and a confirmation dialogue for an action
whose undo is "do the thing you already know how to do" is friction pretending to be safety.

## Responsive

| Breakpoint      | Behaviour                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| 375px (primary) | Address truncates with an ellipsis before the sign-out button shrinks; the button keeps its 44px touch target |
| 768px           | Header on one line, content constrained to 640px                                                              |
| 1280px          | Unchanged                                                                                                     |

## Accessibility

- **Focus:** sign-out is a real `<button>`, reachable and operable by keyboard, with a visible focus ring.
- **Loading:** the skeleton is `aria-busy="true"` on its container and `aria-hidden` on the shape itself, so a screen reader is not told about a grey rectangle.
- **Announcement:** the address, once loaded, is inside an `aria-live="polite"` region, so it is announced rather than silently appearing.
- **Contrast:** the empty-state text meets AA against the page background — it is secondary in emphasis, not in legibility.

## Acceptance criteria

- [ ] Given a valid session, when the page loads, then the signed-in address is displayed
- [ ] Given a 401 from the identity check, then the browser navigates to the sign-in page
- [ ] Given a 500 from the identity check, then a retry is offered and no redirect happens
- [ ] Given the page is loading, then no address is shown
- [ ] Given the sign-out button, when clicked, then a `DELETE` is sent to `/auth/session`
- [ ] Given the sign-out request fails, then the browser still navigates to the sign-in page
