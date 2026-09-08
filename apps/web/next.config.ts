import type { NextConfig } from 'next';

// Applied to every response. Cheap, and the absence of them is the kind of
// thing nobody notices until a security review.
const securityHeaders = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  // Deliberately no Strict-Transport-Security. This app is served under a path
  // on akashungarala.com, so an HSTS header here would set policy for the whole
  // parent domain and every subdomain of it — including ones this project knows
  // nothing about. That belongs to the portfolio project, which owns the domain.
  {
    // Deliberately strict while there is nothing to break. Tightening later,
    // once third-party scripts exist, is far harder than starting strict.
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data:",
      "font-src 'self'",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; '),
  },
];

// The app is served at akashungarala.com/apps/car-maintenance-companion, proxied
// by the portfolio project's Next.js rewrites. basePath makes this app serve
// *every* route under that same prefix, so the proxy maps 1:1 and needs no path
// rewriting — links, asset URLs, form actions and redirects all stay valid.
// Without it, the HTML would load and every /_next/static asset would 404.
const BASE_PATH = '/apps/car-maintenance-companion';

const nextConfig: NextConfig = {
  basePath: BASE_PATH,
  // `standalone` produces the self-contained server bundle the container image
  // needs, keeping the Kubernetes escape hatch in ADR-0007 a config change
  // rather than a rewrite.
  //
  // It must NOT be set on Vercel. Vercel runs its own build pipeline that emits
  // trace files (`next-server.js.nft.json`); with `standalone` those are never
  // produced and the build dies at onBuildComplete with an ENOENT — *after*
  // compiling successfully, which makes it read like an infrastructure fault
  // rather than a config conflict.
  //
  // So it is opt-in, set only by the Dockerfile and the Playwright web server.
  ...(process.env['BUILD_STANDALONE'] === '1' ? { output: 'standalone' as const } : {}),
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  },
};

export default nextConfig;
