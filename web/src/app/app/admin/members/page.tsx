"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminOnly } from "@/components/AdminOnly";
import { Badge, Button, Card, ErrorNotice, Field, inputClass, PageHeader, Table, Td, Th } from "@/components/ui";
import { api, errorMessage, json } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Member, Role, Team } from "@/lib/types";

const ROLES: Role[] = ["owner", "admin", "editor", "employee"];

export default function MembersPage() {
  return (
    <AdminOnly>
      <Members />
    </AdminOnly>
  );
}

function Members() {
  const { me, org } = useSession();
  const [members, setMembers] = useState<Member[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [adding, setAdding] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, t] = await Promise.all([api<Member[]>("/members"), api<Team[]>("/teams")]);
      setMembers(m);
      setTeams(t);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const update = (id: string, body: Partial<Pick<Member, "role" | "status">>) =>
    run(() => api(`/members/${id}`, { method: "PATCH", body: json(body) }));

  const toggleTeam = (team: Team, member: Member) =>
    run(() =>
      api(`/teams/${team.id}/members/${member.id}`, { method: member.team_ids.includes(team.id) ? "DELETE" : "PUT" }),
    );

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Members & teams"
        description="Changes apply on the person's next request, even mid-session: permissions are loaded from the database every time, never from the login token."
        action={<Button onClick={() => setAdding((a) => !a)}>{adding ? "Close" : "Add member"}</Button>}
      />
      {error && (
        <div className="mb-4">
          <ErrorNotice message={error} />
        </div>
      )}
      {adding && (
        <AddMember
          onAdded={() => {
            setAdding(false);
            load();
          }}
        />
      )}

      <Card padded={false} className="mb-6">
        <Table>
          <thead>
            <tr>
              <Th>Person</Th>
              <Th>Role</Th>
              <Th>Teams</Th>
              <Th className="text-right">Access</Th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const self = m.user_id === me.id;
              const revoked = m.status === "revoked";
              return (
                <tr key={m.id} className={revoked ? "opacity-60" : ""}>
                  <Td>
                    <div className="font-medium">
                      {m.display_name} {self && <span className="text-xs text-muted">(you)</span>}
                    </div>
                    <div className="text-xs text-muted">{m.email}</div>
                  </Td>
                  <Td>
                    <select
                      aria-label={`Role of ${m.display_name}`}
                      value={m.role}
                      disabled={self}
                      onChange={(e) => update(m.id, { role: e.target.value as Role })}
                      className="rounded-lg border border-border bg-surface px-2 py-1 text-sm capitalize"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1.5">
                      {teams.map((t) => {
                        const inTeam = m.team_ids.includes(t.id);
                        return (
                          <button
                            key={t.id}
                            onClick={() => toggleTeam(t, m)}
                            title={inTeam ? `Remove from ${t.name}` : `Add to ${t.name}`}
                            className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
                              inTeam
                                ? "border-accent bg-accent-soft text-accent"
                                : "border-dashed border-border text-muted hover:border-accent"
                            }`}
                          >
                            {inTeam ? t.name : `+ ${t.name}`}
                          </button>
                        );
                      })}
                    </div>
                  </Td>
                  <Td className="text-right">
                    {self ? (
                      <Badge tone="ok">Active</Badge>
                    ) : revoked ? (
                      <Button size="sm" variant="secondary" onClick={() => update(m.id, { status: "active" })}>
                        Restore
                      </Button>
                    ) : (
                      <Button size="sm" variant="danger" onClick={() => update(m.id, { status: "revoked" })}>
                        Revoke
                      </Button>
                    )}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card>

      <Card title="Teams">
        <p className="mb-4 text-sm text-muted">
          Teams group people for access grants. Grant a team access to a space under Spaces &amp; access.
        </p>
        <div className="mb-4 flex flex-wrap gap-2">
          {teams.map((t) => (
            <Badge key={t.id}>
              {t.name} · {t.member_ids.length}
            </Badge>
          ))}
        </div>
        <form
          className="flex max-w-md gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(() => api("/teams", { method: "POST", body: json({ name: teamName }) }));
            setTeamName("");
          }}
        >
          <input
            className={inputClass}
            placeholder={`New team in ${org.name}`}
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
            required
          />
          <Button type="submit" variant="secondary">
            Create
          </Button>
        </form>
      </Card>
    </div>
  );
}

function AddMember({ onAdded }: { onAdded: () => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("employee");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/members", {
        method: "POST",
        body: json({ email, display_name: name, role, password: password || undefined }),
      });
      onAdded();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Card title="Add member" className="mb-6">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Email">
          <input className={inputClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Name">
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Role">
          <select className={inputClass} value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Initial password (new users)">
          <input className={inputClass} type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <div className="sm:col-span-2 lg:col-span-4">
          {error && <ErrorNotice message={error} />}
          <Button type="submit" className="mt-2">
            Add member
          </Button>
        </div>
      </form>
    </Card>
  );
}
