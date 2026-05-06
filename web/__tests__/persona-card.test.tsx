import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PersonaCard } from "@/components/live-feed/persona-card";

const sample = {
  persona: { sex: "female", age: 28, province: "서울특별시" },
  avatarKey: "female_20s_서울특별시",
  reaction: {
    stance: "positive" as const,
    intensity: 4,
    action_intent: "purchase",
    quote: "신라면 맵기가 적당해서 사겠다.",
    key_drivers: ["가격", "맛"],
    concerns: [],
  },
};

describe("PersonaCard", () => {
  it("renders demographic header and quote", () => {
    render(<PersonaCard {...sample} />);
    expect(screen.getByText(/여 28 서울/)).toBeInTheDocument();
    expect(screen.getByText(sample.reaction.quote)).toBeInTheDocument();
  });

  it("shows stance badge with intensity", () => {
    render(<PersonaCard {...sample} />);
    expect(screen.getByLabelText(/긍정 4/)).toBeInTheDocument();
  });
});
