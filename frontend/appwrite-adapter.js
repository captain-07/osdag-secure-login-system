/**
 * appwrite-adapter.js
 * --------------------
 * Intercepts window.fetch for the same routes mock-api.js handles, but
 * translates them into real Appwrite Web SDK calls. Only active when the
 * "Appwrite" radio button in index.html is selected.
 */
(function () {
  function config() {
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
    const client = new Appwrite.Client().setEndpoint(cfg.endpoint).setProject(cfg.project);
    return {
      client,
      account: new Appwrite.Account(client),
      tablesDB: new Appwrite.TablesDB(client),
      storage: new Appwrite.Storage(client),
    };
  }

  function json(status, body) {
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }

  function errorResponse(err) {
    const status = err.code || 500;
    return json(status, { error: err.message || "Appwrite error" });
  }

  async function handleRegister(req) {
    const { email, password } = await req.json();
    const { account } = client();
    try {
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
      const session = await account.createEmailPasswordSession(email, password);
      const user = await account.get();
      return json(200, { token: session.$id, user: { id: user.$id, email: user.email } });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleLogout(req) {
    const { account } = client();
    try {
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
    const { account, tablesDB } = client();
    try {
      const me = await account.get();
      const res = await tablesDB.listRows({
        databaseId: cfg.databaseId,
        tableId: cfg.filesCollectionId,
        queries: [Appwrite.Query.equal("ownerId", me.$id)],
      });
      const files = res.rows.map((r) => ({
        id: r.$id, ownerId: r.ownerId, fileName: r.filename,
        mimeType: r.mimeType, sizeBytes: r.sizeBytes,
      }));
      return json(200, { files });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleFileById(fileId) {
    const cfg = config();
    const { tablesDB } = client();
    try {
      const r = await tablesDB.getRow({
        databaseId: cfg.databaseId,
        tableId: cfg.filesCollectionId,
        rowId: fileId,
      });
      return json(200, {
        file: { id: r.$id, ownerId: r.ownerId, fileName: r.filename, mimeType: r.mimeType, sizeBytes: r.sizeBytes },
      });
    } catch (err) {
      return errorResponse(err);
    }
  }

  async function handleFileDownload(fileId) {
    const cfg = config();
    const { account, tablesDB, storage } = client();
    try {
      const r = await tablesDB.getRow({
        databaseId: cfg.databaseId,
        tableId: cfg.filesCollectionId,
        rowId: fileId,
      });
      const url = storage.getFileDownload(cfg.bucketId, r.storageFileId);
      const headers = {};
      try {
        const jwt = await account.createJWT();
        headers["x-appwrite-jwt"] = jwt.jwt;
      } catch (e) {
      }
      const fileRes = await realFetch(url, { credentials: "include", headers });
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

    return realFetch(input, init);
  };

  console.info("[appwrite-adapter] ready — select the 'Appwrite' radio in index.html to use it");
})();