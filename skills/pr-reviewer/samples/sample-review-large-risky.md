## 🔍 PR Review: Add real-time notification system

**Author**: @team-backend | **Files**: 27 | **+1850 −430 | **Platform**: github

### 📝 Summary
Adds a WebSocket-based real-time notification system with Redis pub/sub, database schema changes, and frontend notification bell component. Introduces new `notifications` service with worker pool.

### ⚠️ Identified Risks
- **Very large PR**: 1850 additions across 27 files — must be split into smaller PRs
- SQL query built with string concatenation in `notificationStore.js:87` — SQL injection risk
- `dangerouslySetInnerHTML` in `NotificationBell.tsx:34` — XSS vector for user-generated content
- Thread started without visible lock acquisition in `workerPool.py:56` — race condition on shared queue
- `requirements.txt` changed but no lockfile updated — dependencies may be inconsistent
- `verify=False` in Redis connection (`redis_client.py:12`) — SSL verification disabled
- `DEBUG=True` left in Django settings (`settings.py:89`) — production risk
- Hardcoded JWT secret in `auth_middleware.py:23` — move to environment variable
- `shell=True` in subprocess call (`cleanup.sh:15`) — command injection risk

### 💡 Improvement Suggestions
- Split into 3-4 focused PRs: (1) schema + models, (2) Redis + worker pool, (3) WebSocket layer, (4) frontend component
- Add connection retry logic with exponential backoff — current code fails silently on Redis disconnect
- No test files detected among 27 changed files — critical gap for a system of this complexity
- Configuration files changed (5 files) — verify staging and production environments
- XXX marker found in `broadcast.py` — clean up before merging

### 🟢 What Looks Good
- Detailed PR description — good context for reviewers
- References linked issues (#412, #567) — good traceability

### 📊 Quality Score
🔴 **26/100** `██░░░░░░░░`
**Confidence**: Low — significant scope and multiple security risks (SQL injection, XSS, disabled SSL, race conditions, hardcoded secrets)
**Security issues detected**: 6
