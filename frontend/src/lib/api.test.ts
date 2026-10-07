import { api, ApiError, toFieldErrors } from "./api";

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      body === null
        ? new Response(null, { status, headers })
        : new Response(JSON.stringify(body), {
            status,
            headers: { "Content-Type": "application/json", ...headers },
          }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("toFieldErrors", () => {
  it("maps FastAPI locations to field names, first message wins", () => {
    expect(
      toFieldErrors([
        { loc: ["body", "job_title"], msg: "Field required" },
        { loc: ["body", "job_title"], msg: "second message" },
        { loc: ["body", "skills", 2], msg: "Too long" },
        { loc: ["query", "page"], msg: "Must be positive" },
        { loc: ["body"], msg: "Value error, jobs selected can't be more than jobs pulled" },
      ]),
    ).toEqual({
      job_title: "Field required",
      "skills.2": "Too long",
      page: "Must be positive",
      _form: "jobs selected can't be more than jobs pulled",
    });
  });
});

describe("api", () => {
  it("returns parsed JSON", async () => {
    respond(200, { ok: true });
    await expect(api("/api/x")).resolves.toEqual({ ok: true });
  });

  it("returns undefined for 204", async () => {
    respond(204, null);
    await expect(api("/api/x", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("sends JSON bodies with a content type, FormData without", async () => {
    respond(200, {});
    await api("/api/x", { method: "POST", body: { a: 1 } });
    const fetchMock = vi.mocked(fetch);
    let init = fetchMock.mock.calls[0]?.[1];
    expect(init?.body).toBe('{"a":1}');
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });

    const form = new FormData();
    await api("/api/x", { method: "POST", body: form });
    init = fetchMock.mock.calls[1]?.[1];
    expect(init?.body).toBe(form);
    expect(init?.headers).not.toHaveProperty("Content-Type");
  });

  it("turns 422 into field errors", async () => {
    respond(422, { detail: [{ loc: ["body", "company_name"], msg: "Field required" }] });
    const error = await api("/api/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).fieldErrors).toEqual({ company_name: "Field required" });
  });

  it("uses the app error body and request ID", async () => {
    respond(500, {
      error: { code: "internal_error", message: "Something went wrong.", request_id: "r1" },
    });
    const error = (await api("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("internal_error");
    expect(error.displayMessage).toBe("Something went wrong. (reference: r1)");
  });

  it("handles non-JSON errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Bad gateway", { status: 502 })),
    );
    const error = (await api("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.code).toBe("http_error");
  });

  it("reports network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const error = (await api("/api/x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("network_error");
  });
});
