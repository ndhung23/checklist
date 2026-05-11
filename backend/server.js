const jsonServer = require("json-server");
const cors = require("cors");
const os = require("os");

const server = jsonServer.create();
const router = jsonServer.router("db.json");
const middlewares = jsonServer.defaults();

server.use(cors());
server.use(jsonServer.bodyParser);
server.use(middlewares);

// ============ AUTH ============

server.post("/login", (req, res) => {
  const { username, password } = req.body;

  if (!username || !password) {
    return res.status(400).json({ message: "Username and password are required" });
  }

  const db = router.db;
  const user = db.get("users").find({ username, password }).value();

  if (!user) {
    return res.status(401).json({ message: "Invalid username or password" });
  }

  const { password: pw, ...userData } = user;
  res.json(userData);
});

// ============ CHECKS ============

server.get("/my-checks", (req, res) => {
  const userId = parseInt(req.query.userId);
  const date = req.query.date;

  if (!userId) {
    return res.status(400).json({ message: "userId is required" });
  }

  const db = router.db;
  let checks = db.get("dailyChecks").filter({ userId }).value();

  if (date) {
    checks = checks.filter((c) => c.date === date);
  }

  checks.sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.limitTime.localeCompare(b.limitTime);
  });

  res.json(checks);
});

server.get("/admin/checks", (req, res) => {
  const role = req.query.role;

  if (role !== "admin" && role !== "manager") {
    return res.status(403).json({ message: "Forbidden" });
  }

  const db = router.db;
  let checks = db.get("dailyChecks").value();

  const date = req.query.date;

  if (date) {
    checks = checks.filter((c) => c.date === date);
  }

  checks.sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date);
    return a.limitTime.localeCompare(b.limitTime);
  });

  res.json(checks);
});

// ============ USERS ============

server.get("/users-list", (req, res) => {
  const db = router.db;
  const users = db.get("users").value().map(({ password, ...rest }) => rest);
  res.json(users);
});

// ============ NOTIFICATIONS ============

server.get("/notifications/incomplete", (req, res) => {
  const userId = parseInt(req.query.userId);
  const date = req.query.date;

  if (!userId || !date) {
    return res.status(400).json({ message: "userId and date are required" });
  }

  const db = router.db;
  const allChecks = db.get("dailyChecks").filter({ userId, date }).value();

  const incomplete = allChecks.filter((c) => c.status === "x");
  const abnormal = allChecks.filter((c) => c.status === "△");

  const notes = db.get("abnormalNotes").filter({ userId }).value();

  const abnormalWithNotes = abnormal.map((item) => {
    const note = notes.find((n) => n.dailyCheckId === item.id);
    return {
      ...item,
      note: note ? note.note : "",
    };
  });

  res.json({
    incomplete,
    abnormal: abnormalWithNotes,
  });
});

// ============ GENERATE DAILY CHECKS ============

server.post("/generate-daily-checks", (req, res) => {
  const { userId, date } = req.body;

  if (!userId || !date) {
    return res.status(400).json({ message: "userId and date are required" });
  }

  const db = router.db;

  const existing = db
    .get("dailyChecks")
    .filter({
      userId: parseInt(userId),
      date,
    })
    .value();

  if (existing.length > 0) {
    return res.status(400).json({ message: "Checklist đã tồn tại cho ngày này" });
  }

  const categories = db.get("categories").value();
  const created = [];

  categories.forEach((cat) => {
    const newCheck = {
      userId: parseInt(userId),
      categoryId: cat.id,
      symbol: cat.symbol,
      category: cat.category,
      date,
      status: "x",
      limitTime: cat.limitTime,
    };

    const inserted = db.get("dailyChecks").insert(newCheck).write();
    created.push(inserted);
  });

  res.status(201).json({
    message: `Đã tạo ${created.length} checklist`,
    data: created,
  });
});

// ============ CONFIRMATIONS ============

server.get("/daily-confirmations", (req, res) => {
  const userId = parseInt(req.query.userId);
  const date = req.query.date;

  if (!userId || !date) {
    return res.status(400).json({ message: "userId and date are required" });
  }

  const db = router.db;
  const confirmation = db.get("dailyConfirmations").find({ userId, date }).value();

  res.json(confirmation || null);
});

// ============ ROUTER ============

server.use(router);

// ============ SERVER ============

const PORT = 3000;

function getLocalIP() {
  const interfaces = os.networkInterfaces();

  for (const name of Object.keys(interfaces)) {
    for (const net of interfaces[name]) {
      if (net.family === "IPv4" && !net.internal) {
        return net.address;
      }
    }
  }

  return "localhost";
}

const localIP = getLocalIP();

server.listen(PORT, "0.0.0.0", () => {
  console.log("\n✅ Server running");
  console.log(`🌐 Local:   http://localhost:${PORT}`);
  console.log(`🌐 Company: http://${localIP}:${PORT}`);
  console.log("\nCopy link Company gửi cho mọi người trong công ty.\n");
});

// ============ JSON-SERVER ROUTER ============
// server.use(router);

// const PORT = 3001;
// server.listen(PORT, () => {
//   console.log(`\n  ✅ Backend running at http://localhost:${PORT}`);
//   console.log(`  📋 Custom: /login, /my-checks, /admin/checks, /users-list`);
//   console.log(`  📋 Custom: /notifications/incomplete, /generate-daily-checks, /daily-confirmations`);
//   console.log(`  🔄 CRUD: /dailyChecks, /categories, /abnormalNotes, /dailyConfirmations\n`);
// });
