/**
 * appwrite-adapter.js
 * --------------------
 * Intercepts window.fetch for the same routes mock-api.js handles, but
 * translates them into real Appwrite Web SDK calls. Only active when the
 * "Appwrite" radio button in index.html is selected.
 */
(function () {
  function config() {
    // Read config fields live on every call — lets you switch projects
    // without reloading the page.
    return {
      endpoint: document.getElementById("awEndpoint").value,
      project: document.getElementById("awProjectId").value,
      databaseId: document.getElementById("awDatabaseId").value,
      filesCollectionId: document.getElementById("awFilesCollectionId").value,
      bucketId: document.getElementById("awBucketId").value,
    };
  }

  function client() {
    const cfg = config();
    // `Appwrite` global comes from the CDN script tag — must be uncommented
    // in index.html for this to exist.
    const client = new Appwrite.Client().setEndpoint(cfg.endpoint).setProject(cfg.project);
    return {
      client,
      account: new Appwrite.Account(client),
      databases: new Appwrite.Databases(client),
      storage: new Appwrite.Storage(client),
    };
  }

  function json(status, body) {
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }

  // Appwrite throws AppwriteException with a `.code` (HTTP-like status)
  // and `.message`. Normalizing it here means every handler below can
  // just try/catch and reuse this.
  function errorResponse(err) {
    const status = err.code || 500;
    return json(status, { error: err.message || "Appwrite error" });
  }

  async function handleRegister(req) {
    const { email, password } = await req.json();
    const { account } = client();
    try {
      // ID.unique() lets Appwrite generate the user ID — we don't need to
      // manage ID generation ourselves, unlike the Django backend.
      const user = await account.create(Appwrite.ID.unique(), email, password);
      return json(201, { id: user.$id, email: user.email });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleLogin(req) {
    const { email, password } = await req.json();
    const { account } = client();
    try {
      // This creates a session Appwrite manages server-side — the
      // returned session includes a secret we surface as "token" so
      // index.html's auto-fill (which looks for body.token) still works,
      // even though Appwrite's own JS SDK would normally handle the
      // session via cookies internally.
      const session = await account.createEmailPasswordSession(email, password);
      const user = await account.get();
      return json(200, { token: session.$id, user: { id: user.$id, email: user.email } });
    } catch (err) {
      // Appwrite already returns a generic "Invalid credentials" message
      // for both wrong-password and unknown-email — this requirement is
      // handled automatically, not something we configured.
      return errorResponse(err);
    }
  }

  async function handleLogout(req) {
    const { account } = client();
    try {
      // Deletes the CURRENT session server-side — matches "invalidate
      // server-side, not just cleared client-side" from the requirements.
      await account.deleteSession("current");
      return json(200, { message: "Logged out" });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleMe() {
    const { account } = client();
    try {
      const user = await account.get();
      return json(200, { id: user.$id, email: user.email, name: user.name });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleFiles() {
    const cfg = config();
    const { account, databases } = client();
    try {
      const me = await account.get();
      // Query filter is a defense-in-depth extra — document permissions
      // already prevent other users' rows from being returned even
      // without this filter, but it keeps the query itself honest.
      const res = await databases.listDocuments(cfg.databaseId, cfg.filesCollectionId, [
        Appwrite.Query.equal("ownerId", me.$id),
      ]);
      const files = res.documents.map((d) => ({
        id: d.$id, ownerId: d.ownerId, fileName: d.filename,
        mimeType: d.mimeType, sizeBytes: d.sizeBytes,
      }));
      return json(200, { files });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleFileById(fileId) {
    const cfg = config();
    const { databases } = client();
    try {
      // No manual ownership check here — Appwrite enforces it via the
      // document's read permission (set at creation, see seed script).
      // If this call succeeds at all, Appwrite already confirmed access.
      const d = await databases.getDocument(cfg.databaseId, cfg.filesCollectionId, fileId);
      return json(200, {
        file: { id: d.$id, ownerId: d.ownerId, fileName: d.filename, mimeType: d.mimeType, sizeBytes: d.sizeBytes },
      });
    } catch (err) {
      // NOTE for your README: Appwrite returns 401 for "exists but not
      // yours" and 404 for "doesn't exist" — a different status code
      // than the 403/404 split you chose for the Django backend, but the
      // same underlying distinction. Document this difference explicitly;
      // it's a direct answer to "what did Appwrite handle automatically."
      return errorResponse(err);
    }
  }

  async function handleFileDownload(fileId) {
    const cfg = config();
    const { databases, storage } = client();
    try {
      const d = await databases.getDocument(cfg.databaseId, cfg.filesCollectionId, fileId);
      // getFileDownload returns a URL (with the session's auth baked into
      // the request context) — we fetch it ourselves and re-wrap as a
      // Response so index.html's existing blob-download code works
      // unmodified.
      const url = storage.getFileDownload(cfg.bucketId, d.storageFileId);
      const fileRes = await fetch(url, { credentials: "include" });
      return fileRes;
    } catch (err) {
      return errorResponse(err);
    }
  }

  const realFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    const appwriteToggle = document.querySelector('input[name="backendMode"][value="appwrite"]');
    if (!appwriteToggle || !appwriteToggle.checked) return realFetch(input, init);

    const url = typeof input === "string" ? input : input.url;
    const { pathname } = new URL(url, window.location.href);
    const req = new Request(url, init);

    if (pathname === "/register" && req.method === "POST") return handleRegister(req);
    if (pathname === "/login" && req.method === "POST") return handleLogin(req);
    if (pathname === "/logout" && req.method === "POST") return handleLogout(req);
    if (pathname === "/me" && req.method === "GET") return handleMe();
    if (pathname === "/files" && req.method === "GET") return handleFiles();

    let m = pathname.match(/^\/files\/([^/]+)\/download$/);
    if (m && req.method === "GET") return handleFileDownload(m[1]);

    m = pathname.match(/^\/files\/([^/]+)$/);
    if (m && req.method === "GET") return handleFileById(m[1]);

    return json(404, { error: "No Appwrite adapter route for " + req.method + " " + pathname });
  };

  console.info("[appwrite-adapter] ready — select the 'Appwrite' radio in index.html to use it");
})();