import { STR_ZOOM, busVisible } from "./lod";

describe("lod", () => {
  it("con poco zoom solo se ve el STN; el STR aparece al acercarse", () => {
    expect(busVisible(230, 0.3)).toBe(true);
    expect(busVisible(500, 0.3)).toBe(true);
    expect(busVisible(115, 0.3)).toBe(false);
    expect(busVisible(66, STR_ZOOM - 0.01)).toBe(false);
    expect(busVisible(115, STR_ZOOM)).toBe(true);
  });
});
