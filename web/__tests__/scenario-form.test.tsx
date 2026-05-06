import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScenarioForm } from "@/components/scenario/scenario-form";

describe("ScenarioForm", () => {
  it("submits with required fields", async () => {
    const onSubmit = vi.fn();
    render(<ScenarioForm onSubmit={onSubmit} models={["vllm-qwen"]} maxN={500} />);
    await userEvent.type(screen.getByLabelText(/제목/), "테스트 시나리오");
    await userEvent.type(screen.getByLabelText(/자극/), "본문 자극 텍스트");
    await userEvent.click(screen.getByRole("button", { name: /시뮬 시작/ }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario_title: "테스트 시나리오",
        scenario_stimulus: "본문 자극 텍스트",
        n: expect.any(Number),
        model: "vllm-qwen",
      })
    );
  });

  it("blocks submit when n exceeds maxN", async () => {
    const onSubmit = vi.fn();
    render(<ScenarioForm onSubmit={onSubmit} models={["vllm-qwen"]} maxN={20} />);
    await userEvent.type(screen.getByLabelText(/제목/), "x");
    await userEvent.type(screen.getByLabelText(/자극/), "y");
    const nInput = screen.getByLabelText(/n \(페르소나/);
    await userEvent.clear(nInput);
    await userEvent.type(nInput, "100");
    await userEvent.click(screen.getByRole("button", { name: /시뮬 시작/ }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/최대/)).toBeInTheDocument();
  });
});
