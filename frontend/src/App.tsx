import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { SignedIn, SignedOut, SignInButton, SignUpButton, useUser, useAuth, UserButton } from '@clerk/clerk-react';
import RaterView from './components/RaterView';
import AdminView from './components/AdminView';
import ExperimentDetailPage from './components/ExperimentDetailPage';
import { api } from './api';

function App() {
  return (
    <>
      {/* Minimal header with account menu when signed in */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: 12 }}>
        <SignedIn>
          <UserButton afterSignOutUrl="/" />
        </SignedIn>
        <SignedOut>
          {/* When Clerk signs out, also clear the backend admin cookie */}
          <BackendLogoutOnSignedOut />
        </SignedOut>
      </div>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/rate" element={<RaterView />} />
        <Route
          path="/admin"
          element={
            <>
              <SignedIn>
                <AdminPage />
              </SignedIn>
              <SignedOut>
                <RequireSignIn message="You must sign in to access the admin panel." />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/admin/experiments/:experimentId"
          element={
            <>
              <SignedIn>
                <AdminPage>
                  <ExperimentDetailPage />
                </AdminPage>
              </SignedIn>
              <SignedOut>
                <RequireSignIn message="You must sign in to access this page." />
              </SignedOut>
            </>
          }
        />
      </Routes>
    </>
  );
}

function Home() {
  return (
    <div className="container">
      <div className="card">
        <h1>Human Rating Platform</h1>
        <SignedOut>
          <p>Please sign in or sign up to continue.</p>
          <div style={{ marginTop: '20px', display: 'flex', gap: 12 }}>
            <SignInButton />
            <SignUpButton />
          </div>
        </SignedOut>
        <SignedIn>
          <p>You are signed in.</p>
          <div style={{ marginTop: '20px' }}>
            <a href="/admin" style={{ marginRight: '20px' }}>
              <button>Go to Admin Panel</button>
            </a>
          </div>
        </SignedIn>
      </div>
    </div>
  );
}

function RequireSignIn({ message }: { message: string }) {
  return (
    <div className="container">
      <div className="card" style={{ textAlign: 'center' }}>
        <p style={{ fontSize: 20, marginBottom: 16 }}>{message}</p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <SignInButton />
          <SignUpButton />
        </div>
      </div>
    </div>
  );
}

function AdminPage({ children }: { children?: React.ReactNode }) {
  const { isLoaded, isSignedIn, user } = useUser();
  const { getToken } = useAuth();
  const [state, setState] = React.useState<'idle' | 'loading' | 'ok' | 'forbidden' | 'error'>('idle');
  const [message, setMessage] = React.useState<string>('');
  // Allow overriding the Clerk JWT template via env; default to 'admin'.
  const ADMIN_JWT_TEMPLATE = (import.meta.env.VITE_CLERK_JWT_TEMPLATE as string | undefined) || 'admin';

  React.useEffect(() => {
    if (!isLoaded) return; // wait for Clerk to load
    if (!isSignedIn) return; // SignedOut wrapper handles this

    let cancelled = false;
    const email = user?.primaryEmailAddress?.emailAddress || user?.emailAddresses?.[0]?.emailAddress;
    if (!email) return;

    (async () => {
      setState('loading');
      try {
        const token = await getToken({ template: ADMIN_JWT_TEMPLATE });
        if (!token) {
          throw new Error('Missing Clerk session token');
        }
        const resp = await api.adminLogin(token);
        if (cancelled) return;
        if ((resp as any).ok === true) {
          setState('ok');
        } else {
          const msg = (resp as any)?.message || 'Access denied';
          if (msg.toLowerCase().includes('forbidden') || msg.toLowerCase().includes('allowlist')) {
            setState('forbidden');
            setMessage(msg);
          } else {
            setState('ok');
          }
        }
      } catch (err: any) {
        if (cancelled) return;
        const msg = err?.message || 'Failed to create admin session';
        if (msg.includes('403')) {
          setState('forbidden');
          setMessage('You are not allowed to access the admin panel.');
        } else {
          setState('error');
          setMessage(msg);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn, user?.primaryEmailAddress?.emailAddress, user?.emailAddresses?.[0]?.emailAddress, getToken]);

  if (!isLoaded || state === 'loading' || state === 'idle') {
    return <InfoCard title="Preparing admin session…" />;
  }

  if (state === 'forbidden') {
    return (
      <InfoCard
        title="You don’t have admin access."
        body="Please contact Juliana, Andrew, or Sander to have your email added to the allowlist."
      />
    );
  }

  if (state === 'error') {
    return <InfoCard title="Error preparing admin session." body={message} />;
  }

  return <>{children ?? <AdminView />}</>;
}

type InfoCardProps = {
  title: string;
  body?: string;
  align?: React.CSSProperties['textAlign'];
};

function InfoCard({ title, body, align = 'center' }: InfoCardProps) {
  return (
    <div className="container">
      <div className="card" style={{ textAlign: align }}>
        <p style={{ fontSize: 20, marginBottom: body ? 8 : 0 }}>{title}</p>
        {body && (
          <p style={{ color: '#666', margin: 0 }}>
            {body}
          </p>
        )}
      </div>
    </div>
  );
}

function BackendLogoutOnSignedOut() {
  React.useEffect(() => {
    void api.adminLogout().catch(() => {});
  }, []);
  return null;
}

export default App;
