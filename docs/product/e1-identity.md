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
