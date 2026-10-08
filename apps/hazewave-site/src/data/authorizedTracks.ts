import { getRealArtist, type RealArtistId } from "./realArtists";

export interface AuthorizedTrack {
  readonly id: string;
  readonly artistId: RealArtistId;
  readonly title: string;
  readonly sourceUrl: string;
  readonly ownerAuthorized: true;
  readonly durationSeconds?: number;
}

/** No audio has been supplied and approved. Visual authority does not grant audio rights. */
export const authorizedTracks: readonly AuthorizedTrack[] = [];

/** Fail closed before assigning a media URL, including for malformed runtime data. */
export function isAuthorizedTrack(
  value: unknown,
  baseUrl: string,
): value is AuthorizedTrack {
  if (!value || typeof value !== "object") return false;
  const track = value as Partial<AuthorizedTrack>;
  if (
    track.ownerAuthorized !== true ||
    typeof track.id !== "string" ||
    !track.id.trim() ||
    typeof track.title !== "string" ||
    !track.title.trim() ||
    typeof track.artistId !== "string" ||
    !getRealArtist(track.artistId) ||
    typeof track.sourceUrl !== "string" ||
    !track.sourceUrl ||
    /[\s\\\u0000-\u001f\u007f]/.test(track.sourceUrl)
  )
    return false;
  if (
    track.durationSeconds !== undefined &&
    (!Number.isFinite(track.durationSeconds) || track.durationSeconds <= 0)
  )
    return false;
  try {
    const base = new URL(baseUrl);
    const source = new URL(track.sourceUrl, base);
    if (source.username || source.password) return false;
    const absolute = /^[a-z][a-z0-9+.-]*:/i.test(track.sourceUrl);
    if (absolute) return source.protocol === "https:";
    return (
      !track.sourceUrl.startsWith("//") &&
      source.origin === base.origin &&
      source.protocol === base.protocol
    );
  } catch {
    return false;
  }
}
