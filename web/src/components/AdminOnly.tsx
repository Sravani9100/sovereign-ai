"use client";

import { Empty } from "@/components/ui";
import { useSession } from "@/lib/session";

export function AdminOnly({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useSession();
  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <Empty title="Admins only">Ask an owner or admin of this organization for access.</Empty>
      </div>
    );
  }
  return <>{children}</>;
}
