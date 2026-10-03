import { describe, expect, it } from "vitest";
import { signInHref, signInLinks } from "./api";

describe("sign-in links", () => {
  it("is one plain link for one provider, and one named link a provider for several", () => {
    expect(signInLinks(undefined, "#/digest")).toEqual([]);
    expect(signInLinks({ configured: true, providers: [{ key: "google" }] }, "#/digest")).toEqual([{ label: "Sign in with Google", href: "/auth/google?next=%23%2Fdigest" }]);
    expect(signInLinks({ configured: true, providers: [{ key: "google", label: "Board" }, { key: "mgmt" }] }, "")).toEqual([
      { label: "Sign in with Google (Board)", href: "/auth/google?provider=google" },
      { label: "Sign in with Google (mgmt)", href: "/auth/google?provider=mgmt" },
    ]);
    expect(signInHref({ start: "/auth/google" }, "not-a-route")).toBe("/auth/google");
  });
});
