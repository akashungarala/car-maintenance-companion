import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RootLayout, { metadata } from './layout';

describe('root layout', () => {
  it('renders its children', () => {
    // React renders <html>/<body> into the document root here rather than the
    // default container, which is why the baseElement is queried.
    render(
      <RootLayout>
        <p>child content</p>
      </RootLayout>,
    );

    expect(screen.getByText('child content')).toBeInTheDocument();
  });

  it('declares the document language for screen readers', () => {
    const { baseElement } = render(
      <RootLayout>
        <span />
      </RootLayout>,
    );

    expect(baseElement.ownerDocument.documentElement).toHaveAttribute('lang', 'en');
  });

  it('sets a title and description for search and link previews', () => {
    expect(metadata.title).toBe('Car Maintenance Companion');
    expect(metadata.description).toBeTruthy();
  });
});
