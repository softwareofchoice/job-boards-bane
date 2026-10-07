import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { TagInput, TextField } from "./fields";

describe("TextField", () => {
  it("links the error message to the input", () => {
    render(<TextField label="Company name" error="Field required" />);
    const input = screen.getByLabelText("Company name");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("Field required");
  });
});

function Tags({ maxTags }: { maxTags?: number }) {
  const [tags, setTags] = useState<string[]>([]);
  return <TagInput label="Skills" value={tags} onChange={setTags} maxTags={maxTags} />;
}

describe("TagInput", () => {
  it("adds tags on Enter and comma, ignoring duplicates", async () => {
    render(<Tags />);
    const input = screen.getByLabelText("Skills");
    await userEvent.type(input, "Python{Enter}SQL,python{Enter}");
    const list = screen.getByRole("list", { name: "Skills tags" });
    expect(list).toHaveTextContent("Python");
    expect(list).toHaveTextContent("SQL");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("removes tags with the button and with Backspace", async () => {
    render(<Tags />);
    const input = screen.getByLabelText("Skills");
    await userEvent.type(input, "Go{Enter}Rust{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "Remove Go" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await userEvent.type(input, "{Backspace}");
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("stops at the tag limit", async () => {
    render(<Tags maxTags={1} />);
    const input = screen.getByLabelText("Skills");
    await userEvent.type(input, "Go{Enter}");
    expect(input).toBeDisabled();
  });
});
