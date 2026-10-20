import type { CheckResult, DoctorCheck, DoctorResult } from "./forgeJson";

// A kit's health (plan R30), from forge's own doctor: every check kept as forge wrote it, and the number that are not
// ok. Any status other than "ok" counts, so a status forge adds later (or "unexpected") is never read as healthy.
export type KitHealth =
  | { kit: string; state: "checked"; problems: number; checks: DoctorCheck[] }
  // forge's doctor did not answer for this kit (refused, timed out): its own reason.
  | { kit: string; state: "unavailable"; reason: string };

export interface FolderHealth {
  // forge check's presence flags, verbatim (has_agents_md and so on). They say what is there, not what is wrong: in
  // the default isolated mode forge removes .agents/skills.json and plugins.json on purpose, so a false flag is not a
  // problem. What a kit is missing is its doctor's to say.
  presence: Record<string, boolean>;
  kits: KitHealth[];
}

export function problems(checks: DoctorCheck[]): number {
  return checks.filter((c) => c.status !== "ok").length;
}

export function kitHealth(doctor: DoctorResult): KitHealth {
  return { kit: doctor.kit, state: "checked", problems: problems(doctor.checks), checks: doctor.checks };
}

// One folder's health: forge check's presence flags, and each kit's doctor (or why it has none), in the order given.
export function healthFrom(check: CheckResult, doctors: (DoctorResult | { kit: string; reason: string })[]): FolderHealth {
  return {
    presence: { ...check.flags },
    kits: doctors.map((d) => ("checks" in d ? kitHealth(d) : { kit: d.kit, state: "unavailable", reason: d.reason })),
  };
}
