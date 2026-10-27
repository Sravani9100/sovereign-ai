"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminOnly } from "@/components/AdminOnly";
import {
  Badge,
  Button,
  Card,
  ClassificationBadge,
  controlClass,
  ErrorNotice,
  Field,
  inputClass,
  PageHeader,
} from "@/components/ui";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Classification, Grant, Member, Permission, PrincipalType, Space, Team } from "@/lib/types";

export default function AccessPage() {
  return (
    <AdminOnly>
      <Access />
    </AdminOnly>
  );
}

function Access() {
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, t, m] = await Promise.all([
        api<Space[]>("/knowledge/spaces"),
        api<Team[]>("/teams"),
        api<Member[]>("/members"),
      ]);
      setSpaces(s);
      setTeams(t);
      setMembers(m.filter((x) => x.status === "active"));
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Spaces & access"
        description={
          <>
            Each space is readable only by the people, teams, or organization it&apos;s granted to. Retrieval checks these
            grants before searching, so the AI never sees content a user can&apos;t read. <b>Confidential</b> spaces are
            also never sent to external models.
          </>
        }
        action={<Button onClick={() => setCreating((c) => !c)}>{creating ? "Close" : "New space"}</Button>}
      />
      {error && <ErrorNotice message={error} />}
      {creating && (
        <NewSpace
          onCreated={() => {
            setCreating(false);
            load();
          }}
        />
      )}
      <div className="space-y-4">
        {spaces.map((space) => (
          <SpaceCard key={space.id} space={space} teams={teams} members={members} onChange={load} />
        ))}
      </div>
    </div>
  );
}

function NewSpace({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [classification, setClassification] = useState<Classification>("internal");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/knowledge/spaces", { method: "POST", body: json({ name, description, classification }) });
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card title="New space" className="mb-6">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-3">
        <Field label="Name">
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Description">
          <input className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Classification">
          <select className={inputClass} value={classification} onChange={(e) => setClassification(e.target.value as Classification)}>
            <option value="internal">Internal</option>
            <option value="confidential">Confidential (local models only)</option>
          </select>
        </Field>
        <div className="sm:col-span-3">
          {error && <ErrorNotice message={error} />}
          <p className="mb-3 text-xs text-muted">A new space has no grants: nobody can read it until you add some.</p>
          <Button type="submit">Create space</Button>
        </div>
      </form>
    </Card>
  );
}

function SpaceCard({
  space,
  teams,
  members,
  onChange,
}: {
  space: Space;
  teams: Team[];
  members: Member[];
  onChange: () => void;
}) {
  const { org } = useSession();
  const [grants, setGrants] = useState<Grant[]>([]);
  const [principal, setPrincipal] = useState("");
  const [permission, setPermission] = useState<Permission>("read");
  const [error, setError] = useState<string | null>(null);

  const loadGrants = useCallback(() => {
    api<Grant[]>(`/knowledge/spaces/${space.id}/grants`).then(setGrants).catch((e) => setError(errorMessage(e)));
  }, [space.id]);

  useEffect(() => {
    loadGrants();
  }, [loadGrants]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      loadGrants();
      onChange();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  function addGrant(e: React.FormEvent) {
    e.preventDefault();
    const [principal_type, principal_id] = principal.split(":") as [PrincipalType, string];
    run(() =>
      api(`/knowledge/spaces/${space.id}/grants`, {
        method: "POST",
        body: json({ principal_type, principal_id, permission }),
      }),
    );
    setPrincipal("");
  }

  function setClassification(classification: Classification) {
    run(() => api(`/knowledge/spaces/${space.id}`, { method: "PATCH", body: json({ classification }) }));
  }

  return (
    <Card
      title={
        <span className="flex flex-wrap items-center gap-2">
          {space.name}
          <ClassificationBadge value={space.classification} />
          {space.can_read ? <Badge tone="ok">You can read</Badge> : <Badge>You can&apos;t read</Badge>}
        </span>
      }
      action={
        <select
          aria-label="Classification"
          value={space.classification}
          onChange={(e) => setClassification(e.target.value as Classification)}
          className="rounded-lg border border-border bg-surface px-2 py-1 text-sm"
        >
          <option value="internal">Internal</option>
          <option value="confidential">Confidential</option>
        </select>
      }
    >
      {space.description && <p className="mb-4 text-sm text-muted">{space.description}</p>}
      {error && (
        <div className="mb-4">
          <ErrorNotice message={error} />
        </div>
      )}
      <ul className="divide-y divide-border rounded-lg border border-border">
        {grants.length === 0 && <li className="px-4 py-3 text-sm text-muted">No grants: nobody can read this space.</li>}
        {grants.map((g) => (
          <li key={g.id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
            <span className="flex items-center gap-2">
              {g.principal_name}
              <Badge tone={g.permission === "edit" ? "accent" : "neutral"}>{g.permission === "edit" ? "Read & edit" : "Read"}</Badge>
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => run(() => api(`/knowledge/spaces/${space.id}/grants/${g.id}`, { method: "DELETE" }))}
            >
              Remove
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={addGrant} className="mt-4 flex flex-wrap items-end gap-2">
        <select
          aria-label="Grant to"
          className={`${controlClass} min-w-56 flex-1`}
          value={principal}
          onChange={(e) => setPrincipal(e.target.value)}
          required
        >
          <option value="">Grant access to…</option>
          <option value={`organization:${org.organization_id}`}>Everyone in {org.name}</option>
          <optgroup label="Teams">
            {teams.map((t) => (
              <option key={t.id} value={`team:${t.id}`}>
                {t.name}
              </option>
            ))}
          </optgroup>
          <optgroup label="People">
            {members.map((m) => (
              <option key={m.id} value={`member:${m.id}`}>
                {m.display_name} ({m.role})
              </option>
            ))}
          </optgroup>
        </select>
        <select
          aria-label="Permission"
          className={controlClass}
          value={permission}
          onChange={(e) => setPermission(e.target.value as Permission)}
        >
          <option value="read">Read</option>
          <option value="edit">Read & edit</option>
        </select>
        <Button type="submit" variant="secondary">
          Add
        </Button>
      </form>
      <p className="mt-2 text-xs text-muted">Edit grants only apply to editors and admins; employees always read.</p>
    </Card>
  );
}
