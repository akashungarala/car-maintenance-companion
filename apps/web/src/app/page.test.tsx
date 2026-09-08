import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Page from './page';

describe('home page', () => {
  it('greets the visitor', () => {
    render(<Page />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Hello World');
  });

  it('names the product so the deployment is identifiable', () => {
    render(<Page />);

    expect(screen.getByText(/car maintenance companion/i)).toBeInTheDocument();
  });

  it('states that this is the Phase 0 foundation, not the product', () => {
    render(<Page />);

    // Phase 0 is deliberately visible: anyone who reaches this deployment
    // should understand the product is not built yet, rather than assume it
    // is broken.
    expect(screen.getByText(/phase 0/i)).toBeInTheDocument();
  });
});
