import type { Goal, MediaArtifact, MediaType } from "./types";
import { apiUrl } from "./config";

const EXT: Record<MediaType, string> = { image: "png", video: "mp4", audio: "mp3", text: "txt" };

export function artifactUrl(a: MediaArtifact): string {
  return apiUrl(a.url ?? `/artifacts/${a.id}.${EXT[a.media_type]}`);
}

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export async function createRun(goal: Goal): Promise<{ run_id: string }> {
  return json(
    await fetch(apiUrl("/runs"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(goal),
    }),
  );
}

export async function respond(
  runId: string,
  body: { request_id: string; choice_id: string; notes?: string },
): Promise<void> {
  const r = await fetch(apiUrl(`/runs/${runId}/respond`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
}

export interface NewCastMember {
  name: string;
  type: "character" | "location";
  appearance?: string;
  style?: string;
  voice_id?: string;
  file?: File | null;
}

export async function createCastMember(m: NewCastMember): Promise<{ id: string; references: MediaArtifact[] }> {
  const fd = new FormData();
  fd.append("name", m.name);
  fd.append("type", m.type);
  if (m.appearance) fd.append("appearance", m.appearance);
  if (m.style) fd.append("style", m.style);
  if (m.voice_id) fd.append("voice_id", m.voice_id);
  if (m.file) fd.append("file", m.file);
  return json(await fetch(apiUrl("/characters/upload"), { method: "POST", body: fd }));
}

export async function uploadReference(entityId: string, file: File): Promise<{ artifact: MediaArtifact }> {
  const fd = new FormData();
  fd.append("file", file);
  return json(await fetch(apiUrl(`/entities/${entityId}/upload-reference`), { method: "POST", body: fd }));
}
