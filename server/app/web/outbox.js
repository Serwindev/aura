/* Offline outbox: notes that could not reach the server wait here (IndexedDB, this phone only)
   and are re-sent with the same idempotency key, so a retry never creates a second draft. */
const Outbox = (() => {
  const DB = "aura", STORE = "outbox";
  let dbp = null;

  function open() {
    if (!dbp) {
      dbp = new Promise((resolve, reject) => {
        if (!("indexedDB" in window)) return reject(new Error("no-idb"));
        const req = indexedDB.open(DB, 1);
        req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
      dbp.catch(() => { dbp = null; });
    }
    return dbp;
  }

  async function tx(mode, fn) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const t = db.transaction(STORE, mode);
      const out = fn(t.objectStore(STORE));
      t.oncomplete = () => resolve(out && "result" in out ? out.result : undefined);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error || new Error("aborted"));
    });
  }

  return {
    put: (item) => tx("readwrite", (s) => s.put(item)),
    remove: (id) => tx("readwrite", (s) => s.delete(id)),
    async list(owner) {
      const all = (await tx("readonly", (s) => s.getAll())) || [];
      return all.filter((x) => !owner || x.owner === owner).sort((a, b) => a.created_at.localeCompare(b.created_at));
    },
    async clear(owner) {
      for (const x of await this.list(owner)) await this.remove(x.id);
    },
  };
})();
