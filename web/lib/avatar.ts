const SEX_CANONICAL: Record<string, string> = {
  female: "female",
  male: "male",
  여: "female",
  남: "male",
};

export function ageToBand(age: number): string {
  if (age < 20) return "~19";
  if (age < 30) return "20s";
  if (age < 40) return "30s";
  if (age < 50) return "40s";
  if (age < 60) return "50s";
  if (age < 70) return "60s";
  return "70+";
}

export function avatarUrlForKey(key: string): string {
  return `/avatars/${encodeURIComponent(key)}.webp`;
}

export function avatarKeyFor(persona: { sex: string; age: number; province: string }): string | null {
  const canonical = SEX_CANONICAL[persona.sex];
  if (!canonical) return null;
  return `${canonical}_${ageToBand(persona.age)}_${persona.province}`;
}
