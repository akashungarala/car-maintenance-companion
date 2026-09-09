import { SignInForm } from './SignInForm';

export const metadata = { title: 'Sign in · Car Maintenance Companion' };

export default function SignInPage() {
  return (
    // One column, centred, nothing else. Every additional element on a sign-in
    // screen is a chance to hesitate (UX-001).
    <main className="mx-auto flex min-h-screen max-w-[420px] flex-col justify-center px-4">
      <SignInForm />
    </main>
  );
}
