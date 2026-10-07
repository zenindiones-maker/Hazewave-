export type PlayerPhase =
  | "IDLE"
  | "SELECTED"
  | "ANTICIPATION"
  | "TRAVEL"
  | "ALIGN"
  | "INSERT"
  | "CONTACT"
  | "ACTIVATING"
  | "PLAYING"
  | "ENDED"
  | "EJECT"
  | "RETURN"
  | "PAUSED"
  | "ERROR";

const legal: Record<PlayerPhase, ReadonlySet<PlayerPhase>> = {
  IDLE: new Set(["SELECTED", "ERROR"]),
  SELECTED: new Set(["ANTICIPATION", "PLAYING", "ERROR"]),
  ANTICIPATION: new Set(["TRAVEL", "ERROR"]),
  TRAVEL: new Set(["ALIGN", "ERROR"]),
  ALIGN: new Set(["INSERT", "ERROR"]),
  INSERT: new Set(["CONTACT", "ERROR"]),
  CONTACT: new Set(["ACTIVATING", "ERROR"]),
  ACTIVATING: new Set(["PLAYING", "ERROR"]),
  PLAYING: new Set(["PAUSED", "ENDED", "EJECT", "SELECTED", "ERROR"]),
  ENDED: new Set(["PLAYING", "EJECT", "SELECTED", "ERROR"]),
  EJECT: new Set(["RETURN", "ERROR"]),
  RETURN: new Set(["SELECTED", "IDLE", "ERROR"]),
  PAUSED: new Set(["PLAYING", "EJECT", "SELECTED", "ERROR"]),
  ERROR: new Set(["IDLE", "SELECTED"])
};

export class PlayerMachine {
  phase: PlayerPhase = "IDLE";
  activeTrackId: string | null = null;

  transition(next: PlayerPhase): void {
    if (next === this.phase) return;
    if (!legal[this.phase].has(next)) {
      throw new Error(`ILLEGAL_PLAYER_TRANSITION:${this.phase}->${next}`);
    }
    this.phase = next;
  }

  select(trackId: string): void {
    if (!trackId) throw new Error("TRACK_ID_REQUIRED");
    if (this.phase === "ERROR") this.transition("IDLE");
    if (this.phase === "PLAYING" || this.phase === "PAUSED" || this.phase === "ENDED") {
      this.transition("EJECT");
      this.transition("RETURN");
    }
    if (this.phase === "RETURN" || this.phase === "IDLE") this.transition("SELECTED");
    else if (this.phase !== "SELECTED") throw new Error(`SELECT_NOT_ALLOWED_FROM:${this.phase}`);
    this.activeTrackId = trackId;
  }

  fail(): void {
    this.phase = "ERROR";
  }

  reset(): void {
    this.phase = "IDLE";
    this.activeTrackId = null;
  }
}
