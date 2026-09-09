/**
 * UX-001 acceptance criteria, asserted as written.
 *
 * See docs/ux/ux-001-magic-link-request.md — each test below is one of the
 * criteria in that spec's final section.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '../../mocks/node';
import { SignInForm } from './SignInForm';

const ENDPOINT = '/apps/car-maintenance-companion/api/auth/magic-link';

function accepted() {
  return http.post(ENDPOINT, () => HttpResponse.json({ status: 'accepted' }, { status: 202 }));
}

describe('SignInForm', () => {
  it('gives the email field a visible label', () => {
    render(<SignInForm />);

    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  });

  it('refuses an empty submission without calling the API', async () => {
    const user = userEvent.setup();
    const seen = vi.fn();
    server.use(
      http.post(ENDPOINT, () => {
        seen();
        return HttpResponse.json({}, { status: 202 });
      }),
    );
    render(<SignInForm />);

    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByText(/enter your email address/i)).toBeInTheDocument();
    expect(seen).not.toHaveBeenCalled();
  });

  it('refuses a malformed address without calling the API', async () => {
    const user = userEvent.setup();
    const seen = vi.fn();
    server.use(
      http.post(ENDPOINT, () => {
        seen();
        return HttpResponse.json({}, { status: 202 });
      }),
    );
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'not-an-email');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByText(/does not look like an email address/i)).toBeInTheDocument();
    expect(seen).not.toHaveBeenCalled();
  });

  it('shows the confirmation naming the exact address', async () => {
    const user = userEvent.setup();
    server.use(accepted());
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'sam@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByRole('heading', { name: /check your email/i })).toBeInTheDocument();
    // Naming it is what makes a typo recoverable: the most common failure here
    // is not an error, it is a link sent somewhere the user cannot read.
    expect(screen.getByText('sam@example.com')).toBeInTheDocument();
  });

  it('moves focus to the confirmation heading', async () => {
    const user = userEvent.setup();
    server.use(accepted());
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'sam@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    // Otherwise a screen-reader user is left focused on a button that no
    // longer exists, with no announcement of what replaced it.
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: /check your email/i })).toHaveFocus(),
    );
  });

  it('keeps the address in the field when the request fails', async () => {
    const user = userEvent.setup();
    server.use(http.post(ENDPOINT, () => HttpResponse.json({}, { status: 500 })));
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'sam@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
    // Clearing it would make the user retype the address to retry.
    expect(screen.getByLabelText(/email address/i)).toHaveValue('sam@example.com');
  });

  it('names the wait when rate limited', async () => {
    const user = userEvent.setup();
    server.use(
      http.post(
        ENDPOINT,
        () => new HttpResponse(null, { status: 429, headers: { 'Retry-After': '45' } }),
      ),
    );
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'sam@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));

    // "Too many attempts" with no number is indistinguishable from a dead end.
    expect(await screen.findByText(/45 seconds/i)).toBeInTheDocument();
  });

  it('returns to an empty form from the confirmation', async () => {
    const user = userEvent.setup();
    server.use(accepted());
    render(<SignInForm />);

    await user.type(screen.getByLabelText(/email address/i), 'typo@example.com');
    await user.click(screen.getByRole('button', { name: /email me a link/i }));
    await screen.findByRole('heading', { name: /check your email/i });

    await user.click(screen.getByRole('button', { name: /use a different one/i }));

    expect(await screen.findByLabelText(/email address/i)).toHaveValue('');
  });
});
