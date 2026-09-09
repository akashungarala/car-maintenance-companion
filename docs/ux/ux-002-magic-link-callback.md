# UX-002 — Arriving from the sign-in link

**Story:** [E1-002](../product/e1-identity.md#e1-002--exchange-the-link-for-a-session) · **Mockup:**
`mockups/ux-002-magic-link-callback.html`

## User goal

Get into my garage by clicking the link in my email, without thinking about it.

## Information architecture

A pass-through. The user arrives from their email client and should leave immediately for their
garage. Nobody wants to look at this screen; its success condition is being seen for under a
second.

It is also the only screen a user reaches from outside the application, which makes it the one
place where "something went wrong" has no context to fall back on — there is no previous page and
no navigation.

## Layout

Centred, single column, matching UX-001 so the two feel like one flow rather than two apps.

## Components

| Component             | Purpose                                | Notes                                                        |
| --------------------- | -------------------------------------- | ------------------------------------------------------------ |
| Spinner + status line | Occupies the moment the exchange takes | "Signing you in…" — states what is happening, not what to do |
| Error panel           | When the link cannot be used           | Always the same message, whatever the cause                  |
| Request-again link    | The only recovery                      | Returns to UX-001                                            |

## Interaction flow

1. The link is opened, landing here with a token in the query string
2. The page immediately `POST`s the token to `/auth/session`
3. **200** → redirect to the garage; the session cookie is already set
4. **401** → error panel
5. **Network failure** → error panel with a retry affordance

The exchange is a `POST` on purpose. Mail scanners prefetch links with `GET`, and if the `GET`
consumed the token, a scanner would spend it before the user ever clicked. That failure looks like
"this link has expired" on a link that arrived seconds ago.

## States

### Default

There is no idle state. The page begins working the instant it loads; showing a button would add a
click for every user to solve a problem the `POST` already solves.

### Loading

Spinner and "Signing you in…". This is the expected state and usually lasts a few hundred
milliseconds.

Deliberately not instant-blank: replacing the screen with nothing while a request runs reads as a
broken page, and a user who sees nothing presses back.

### Empty

Not applicable.

### Error

One message for every cause:

> **This link cannot be used**
> Sign-in links work once and expire after 15 minutes.
> [Request a new link]

Expired, already used, never existed, altered — all identical. Telling the user which one it was
would tell an attacker which tokens once existed, and none of the four changes what the user does
next.

### Validation

Not applicable: there is no input.

### Success

No success state is rendered. The user is redirected to their garage, which is the success. A
"you're signed in!" interstitial would be a screen whose only content is a delay.

### Confirmation

Not applicable: nothing here is destructive.

### Missing token

Arriving with no token at all — a bookmarked callback URL, a truncated link — shows the same error
panel. It is not a distinct state to the user, and treating it as one would mean two ways to say
the same thing.

## Responsive

| Breakpoint      | Behaviour                                                                                           |
| --------------- | --------------------------------------------------------------------------------------------------- |
| 375px (primary) | Full-width card, 16px gutters. This is where most links are opened, because email is read on phones |
| 768px           | Card constrained to 420px, vertically centred                                                       |
| 1280px          | Unchanged                                                                                           |

## Accessibility

- **Announcement:** the status region is `aria-live="polite"`, so the transition from "signing you
  in" to an error is announced without interrupting.
- **Focus:** on error, focus moves to the error heading (`tabindex="-1"`). The user arrived from
  outside the app with focus nowhere useful, and the error is the only thing on the page.
- **Not colour alone:** the error is conveyed by heading and text; the red border is redundant.
- **Reduced motion:** the spinner respects `prefers-reduced-motion` and becomes static text.

## Acceptance criteria

- [ ] Given a valid token in the URL, when the page loads, then a `POST` to `/auth/session` is made
      without any user action
- [ ] Given a 200 response, then the browser navigates to the garage
- [ ] Given a 401 response, then the error panel appears with the generic message
- [ ] Given no token in the URL, then the error panel appears with the same message
- [ ] Given a network failure, then the error panel appears
- [ ] Given the error panel, then focus is on its heading
- [ ] The page issues no request until it has loaded — a `GET` of this URL alone consumes nothing
