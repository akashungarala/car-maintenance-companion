# E1 — Identity

**Goal:** a person can get into their garage without a password, and stay in.

Identity is not the product. Nobody wants an account; they want to know when their car needs
something. Every decision here is therefore biased towards _fewest steps_, and the epic is
deliberately three stories rather than a login system.

## Stories

| ID         | Story                           | Area               | Depends on |
| ---------- | ------------------------------- | ------------------ | ---------- |
| **E1-001** | Request a magic link            | backend + frontend | —          |
| **E1-002** | Exchange the link for a session | backend + frontend | E1-001     |
| **E1-003** | Protected routes and sign-out   | backend + frontend | E1-002     |

---

## E1-001 — Request a magic link

**As** someone who wants to check on my car
**I want** to sign in by typing my email
**So that** I do not have to invent, remember or reset a password.

### Product decisions

**The response never reveals whether the email is registered.** Submitting an unknown address and
a known one produce the same confirmation, the same status code, and the same timing envelope.
Anything else turns the sign-in form into a tool for discovering who has an account. This costs
one piece of helpfulness — we cannot say "no account found, want to sign up?" — and that trade is
deliberate. Sign-in and sign-up are the same action here, so the question rarely arises.

**Sending the email happens in the background.** The request enqueues a job and returns. Holding
the HTTP request open while an external mail API responds makes login latency a function of
Resend's availability, and a slow provider becomes a slow, then failing, sign-in page.

**One link at a time per address.** Requesting again invalidates any earlier unused link. Two live
links for one address doubles the window in which an intercepted email is useful, for no benefit —
the user is looking at the most recent email.

**Links last 15 minutes and work once** (ADR-0009). Long enough to switch to a phone and find the
email; short enough that a link sitting in an inbox for a week is not a standing key.

**The email address is stored, but never logged.** It appears in the database because it is the
account identifier. It does not appear in log lines, metric labels, or span attributes, where it
would be a personal identifier scattered across systems with different retention and access rules.

### Acceptance criteria

- [ ] Given a valid email, when submitted, then the response is 202 and the page shows a
      "check your email" confirmation naming the address
- [ ] Given an email that has never been seen, when submitted, then the response is identical in
      status, body and observable timing to a registered one
- [ ] Given a malformed email, when submitted, then the field shows a validation message and no
      request is sent
- [ ] Given six requests within a minute from one address, then the sixth is refused with 429 and
      a `Retry-After` header
- [ ] Given a successful request, then exactly one email job is enqueued
- [ ] Given a second request for the same address, then the first link no longer works
- [ ] The email address appears in no log line, metric label or span attribute

### Out of scope

Consuming the link (E1-002), sessions (E1-002), sign-out (E1-003), and "remember me". Resending
from the confirmation screen is deliberately deferred: the user can request again from the form,
and a resend button is a second rate-limiting surface to reason about for very little gain.

### Dependency, not yet satisfied

Delivery needs a Resend API key and a verified sending domain. Until both exist the job runs and
records that it could not send, which keeps the request path complete and testable — but no email
arrives, so E1-001 is not _done_ until they do.

---

## E1-002 — Exchange the link for a session

**As** someone who clicked the link in my email
**I want** to arrive already signed in
**So that** proving who I am costs me nothing beyond opening my inbox.

### The decision that shapes this story: link scanners prefetch

Gmail, Outlook and corporate mail gateways fetch the URLs in an email to check them for malware.
If clicking the link is what consumes the token, the scanner consumes it first — and the person
opens their email to find a link that has already been used, seconds after it was sent. This is a
well-known way for magic-link implementations to appear intermittently broken.

**The link is therefore a `GET` that consumes nothing.** It lands on a page that immediately
exchanges the token with a `POST`. Scanners issue `GET`s, so nothing is spent by being scanned,
and a real visitor needs no extra click — the exchange happens while the page is still showing a
spinner.

The alternative, a "click here to sign in" confirmation page, defeats scanners just as well and
costs every user an extra deliberate click on every sign-in. That trade is not worth it for a
product whose entire premise is asking little of the user.

### Product decisions

**The session is a row, not a signed token.** It can be revoked (ADR-0014). A stateless token
remains valid until it expires no matter what happens in between, which means a sign-out that does
not sign you out, and no way to end a session from a device you no longer have.

**Sessions last 30 days, sliding.** This is a product people use when something needs doing, which
may be six weeks apart. A session that expires between visits turns every visit into a sign-in,
which is the thing the whole epic exists to avoid.

**Every failure looks the same.** Expired, already used, never existed, tampered with — one
message. Distinguishing them tells an attacker which tokens once existed.

**The account is created here**, not when the link was requested, because this is the first moment
control of the address is proven.

### Acceptance criteria

- [ ] Given a valid, unused link, when opened, then a session cookie is set and the user lands in
      their garage
- [ ] Given the same link a second time, then sign-in fails with the generic message
- [ ] Given a link older than 15 minutes, then sign-in fails with the generic message
- [ ] Given any failure, then the message is identical regardless of cause
- [ ] The session cookie is `HttpOnly`, `Secure` and `SameSite=Lax`
- [ ] The session token is stored hashed, never in plaintext
- [ ] A `GET` of the link URL alone consumes nothing — a prefetching scanner does not spend it
- [ ] Signing in creates exactly one user for an address, no matter how many links were requested

### Out of scope

Sign-out and protected routes (E1-003). Session revocation from other devices, which needs a UI
nobody has asked for yet.
