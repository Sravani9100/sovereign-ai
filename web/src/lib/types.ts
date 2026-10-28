// Mirrors backend/src/sovereign/api/schemas.py.

export type Role = "owner" | "admin" | "editor" | "employee";
export type Classification = "internal" | "confidential";
export type PrincipalType = "organization" | "team" | "member";
export type Permission = "read" | "edit";
export type VersionStatus = "pending" | "processing" | "ready" | "failed";
export type MessageStatus = "complete" | "partial" | "error";

export interface OrgMembership {
  organization_id: string;
  name: string;
  slug: string;
  role: Role;
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  read_only: boolean;
  organizations: OrgMembership[];
}

export interface Member {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: Role;
  status: "active" | "revoked";
  team_ids: string[];
}

export interface Team {
  id: string;
  name: string;
  member_ids: string[];
}

export interface Space {
  id: string;
  name: string;
  description: string;
  classification: Classification;
  can_read: boolean;
  can_edit: boolean;
  document_count: number;
}

export interface Grant {
  id: string;
  principal_type: PrincipalType;
  principal_id: string;
  principal_name: string;
  permission: Permission;
}

export interface DocumentVersion {
  id: string;
  version_no: number;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: VersionStatus;
  error: string | null;
  chunk_count: number;
  embedding_model: string | null;
  created_at: string;
  indexed_at: string | null;
}

export interface DocumentSummary {
  id: string;
  space_id: string;
  space_name: string;
  title: string;
  status: VersionStatus;
  current_version_id: string | null;
  created_at: string;
  can_edit: boolean;
}

export interface DocumentDetail extends DocumentSummary {
  versions: DocumentVersion[];
}

export interface ModelProfile {
  id: string;
  name: string;
  provider: "anthropic" | "ollama" | "fake";
  model: string;
  max_classification: Classification;
  enabled: boolean;
  is_default: boolean;
  external: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  marker: number;
  document_id: string | null;
  document_title: string;
  location: { page?: number; section?: string; path?: string[] };
  quote: string;
  restricted: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: MessageStatus;
  model_profile: string | null;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number | null;
  created_at: string;
  citations: Citation[];
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  event_type: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
}
