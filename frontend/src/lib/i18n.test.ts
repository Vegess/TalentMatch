import { describe, expect, it } from "vitest";
import { translate } from "./i18n";
import D from "./i18n-dict";
import { money, budget, flag } from "./format";

describe("i18n", () => {
  it("leaves English and unknown text untouched", () => {
    expect(translate("Find talent", "en")).toBe("Find talent");
    expect(translate("Senior Python Backend Consultant", "es")).toBe("Senior Python Backend Consultant");
  });
  it("translates patterns with numbers and names (dictionary loaded on demand)", () => {
    expect(translate("Ranked matches (12)", "es")).toBe("Coincidencias (12)");
    expect(translate("  Welcome back, Priya  ", "hi")).toBe("  वापसी पर स्वागत है, Priya  ");
    expect(translate("94% match", "es")).toBe("94% de encaje");
  });
  it("every dictionary entry has both translations", () => {
    for (const [en, [hi, es]] of Object.entries(D)) {
      expect(hi, en).toBeTruthy(); expect(es, en).toBeTruthy();
    }
    expect(Object.keys(D).length).toBeGreaterThan(400);
  });
});

describe("money & places", () => {
  it("formats each currency", () => {
    expect(money(150000, "INR")).toBe("₹1,50,000");
    expect(money(1800, "EUR")).toBe("€1,800");
    expect(money(15, "USD")).toBe("$15");
    expect(money(12.5, "GBP")).toBe("£12.50");
  });
  it("budgets use the job's currency", () => {
    expect(budget({ budget_type: "hourly", budget_min: 60, budget_max: 90, currency: "USD" })).toBe("$60–$90/hr");
  });
  it("makes flag emoji", () => { expect(flag("IN")).toBe("🇮🇳"); expect(flag(null)).toBe(""); });
});
