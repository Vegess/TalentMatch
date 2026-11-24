import { describe, expect, it } from "vitest";
import { budget, bytes, compactInr, initials, inr, lines, skillsFrom } from "./format";

describe("format", () => {
  it("formats rupees in the Indian system", () => {
    expect(inr(162000)).toBe("₹1,62,000");
    expect(inr(null)).toBe("—");
    expect(compactInr(250000)).toBe("₹2.5L");
    expect(compactInr(12000000)).toBe("₹1.2Cr");
  });
  it("describes job budgets", () => {
    expect(budget({ budget_type: "fixed", budget_min: 150000, budget_max: 250000 })).toBe("₹1.5L–₹2.5L");
    expect(budget({ budget_type: "hourly", budget_min: 1500, budget_max: null })).toBe("From ₹2k/hr");
    expect(budget({ budget_type: "fixed" })).toBe("Budget open");
  });
  it("parses skills and multi-line lists", () => {
    expect(skillsFrom(" Python, ,SQL ,Docker")).toEqual(["Python", "SQL", "Docker"]);
    expect(lines("a\n\n  b \n")).toEqual(["a", "b"]);
  });
  it("makes initials and file sizes", () => {
    expect(initials("Kavya Reddy")).toBe("KR");
    expect(initials("")).toBe("?");
    expect(bytes(2048)).toBe("2 KB");
  });
});
