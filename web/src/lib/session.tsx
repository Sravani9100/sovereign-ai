"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, getActiveOrg, setActiveOrg } from "@/lib/api";
import type { Me, OrgMembership } from "@/lib/types";

interface Session {
  me: Me;
  org: OrgMembership;
  isAdmin: boolean;
  switchOrg: (id: string) => void;
  logout: () => Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession outside SessionProvider");
  return session;
}

/** Loads the signed-in user and their active organization; redirects to login otherwise. */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [orgId, setOrgId] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/auth/me")
      .then((user) => {
        if (user.organizations.length === 0) {
          router.replace("/onboarding");
          return;
        }
        const saved = getActiveOrg();
        const org = user.organizations.find((o) => o.organization_id === saved) ?? user.organizations[0];
        setActiveOrg(org.organization_id);
        setOrgId(org.organization_id);
        setMe(user);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  const switchOrg = useCallback(
    (id: string) => {
      setActiveOrg(id);
      setOrgId(id);
      router.push("/app/chat");
    },
    [router],
  );

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setActiveOrg(null);
    router.replace("/login");
  }, [router]);

  const org = me?.organizations.find((o) => o.organization_id === orgId);
  if (!me || !org) {
    return <div className="grid min-h-screen place-items-center text-sm text-muted">Loading…</div>;
  }
  return (
    <SessionContext.Provider
      // Re-mount the app when the organization changes so no data from the previous
      // tenant stays on screen.
      key={org.organization_id}
      value={{ me, org, isAdmin: org.role === "owner" || org.role === "admin", switchOrg, logout }}
    >
      {children}
    </SessionContext.Provider>
  );
}
