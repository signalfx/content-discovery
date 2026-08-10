/**
 * BridgeIT/CircuIT auto-fix proposer.
 *
 * Companion to bridge_it_validate_content.mjs. Reuses the same OAuth flow
 * (id.cisco.com) and chat-ai.cisco.com deployment, but with a fix-focused
 * prompt: asks the model to return a strict-JSON RFC-6902 patch for the
 * single "primary suspect" file identified during triage.
 *
 * Trust boundary: only files listed in `triage.json:allowed_files` may be
 * modified. `replace` is the only op we accept. Any deviation aborts.
 *
 * Inputs:
 *   triage.json (artifact from ootb-bug-fix job) with keys:
 *     bug_text, jira_key, branch, primary_file, allowed_files[]
 *
 * Env (already configured in GitLab CI/CD settings):
 *   BRIDGE_API_CLIENT_ID
 *   BRIDGE_API_CLIENT_SECRET
 *   BRIDGE_API_APP_KEY
 *   BRIDGE_API_MODEL_NAME (optional, default gpt-4.1)
 *   BRIDGE_API_TEMPERATURE (optional, default 0.2 — lower than validator, we want deterministic fixes)
 *   BRIDGE_API_TOP_P (optional, default 0.1)
 *   PROPOSE_FIX_MIN_CONFIDENCE (optional, default 0.7)
 *
 * Exit codes:
 *   0 — patch applied, files modified on disk (caller commits/pushes)
 *   0 — LLM confidence too low or no fix proposed (soft no-op)
 *   1 — hard failure (config, network, or invalid response)
 */

import fs from "fs";
import https from "https";
import path from "path";

const BRIDGE_API_CLIENT_ID = process.env.BRIDGE_API_CLIENT_ID;
const BRIDGE_API_CLIENT_SECRET = process.env.BRIDGE_API_CLIENT_SECRET;
const BRIDGE_API_APP_KEY = process.env.BRIDGE_API_APP_KEY;
const BRIDGE_API_HOSTNAME = "chat-ai.cisco.com";
const BRIDGE_API_MODEL_NAME = process.env.BRIDGE_API_MODEL_NAME || "gpt-4.1";
const BRIDGE_API_PATH = `/openai/deployments/${BRIDGE_API_MODEL_NAME}/chat/completions`;
const BRIDGE_API_TEMPERATURE = Number(process.env.BRIDGE_API_TEMPERATURE ?? 0.2);
const BRIDGE_API_TOP_P = Number(process.env.BRIDGE_API_TOP_P ?? 0.1);
const MIN_CONFIDENCE = Number(process.env.PROPOSE_FIX_MIN_CONFIDENCE ?? 0.7);

const AUTH_API_HOSTNAME = "id.cisco.com";
const AUTH_API_PATH = "/oauth2/default/v1/token";

const TRIAGE_PATH = process.env.OOTB_TRIAGE_ARTIFACT || "triage.json";
const OUTPUT_SUMMARY_PATH =
  process.env.OOTB_PROPOSE_FIX_SUMMARY || "propose_fix_summary.json";

const ALLOWED_OPS = new Set(["replace"]);

function fatal(message, exit = 1) {
  console.error(`[propose-fix] FATAL: ${message}`);
  process.exit(exit);
}

function log(message) {
  console.log(`[propose-fix] ${message}`);
}

function requireEnv() {
  const missing = [];
  if (!BRIDGE_API_CLIENT_ID) missing.push("BRIDGE_API_CLIENT_ID");
  if (!BRIDGE_API_CLIENT_SECRET) missing.push("BRIDGE_API_CLIENT_SECRET");
  if (!BRIDGE_API_APP_KEY) missing.push("BRIDGE_API_APP_KEY");
  if (missing.length) {
    fatal(`missing required env vars: ${missing.join(", ")}`);
  }
}

function httpRequest(options, payload) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const body = Buffer.concat(chunks).toString();
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(
            new Error(`HTTP ${res.statusCode} from ${options.hostname}: ${body.slice(0, 500)}`)
          );
        }
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(new Error(`invalid JSON from ${options.hostname}: ${err.message}`));
        }
      });
    });
    req.on("error", reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function bridgeItAuth() {
  const authHeader =
    "Basic " +
    Buffer.from(`${BRIDGE_API_CLIENT_ID}:${BRIDGE_API_CLIENT_SECRET}`).toString("base64");
  const resp = await httpRequest(
    {
      hostname: AUTH_API_HOSTNAME,
      path: AUTH_API_PATH,
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: authHeader,
      },
    },
    "grant_type=client_credentials"
  );
  if (!resp.access_token) {
    fatal("BridgeIT auth response missing access_token");
  }
  return resp.access_token;
}

function loadTriage() {
  if (!fs.existsSync(TRIAGE_PATH)) {
    fatal(`triage artifact not found at ${TRIAGE_PATH} — did ootb-bug-fix run?`);
  }
  let triage;
  try {
    triage = JSON.parse(fs.readFileSync(TRIAGE_PATH, "utf8"));
  } catch (err) {
    fatal(`failed to parse ${TRIAGE_PATH}: ${err.message}`);
  }
  if (!triage.bug_text || !triage.primary_file) {
    log(`triage artifact has no primary_file (bug_text=${!!triage.bug_text}); nothing to fix.`);
    writeSummary({ status: "no_primary_file", triage });
    process.exit(0);
  }
  if (!Array.isArray(triage.allowed_files) || triage.allowed_files.length === 0) {
    fatal("triage.allowed_files must be a non-empty array");
  }
  return triage;
}

function loadFileSafely(relPath) {
  const abs = path.resolve(process.cwd(), relPath);
  const repoRoot = process.cwd();
  if (!abs.startsWith(repoRoot + path.sep)) {
    fatal(`refusing to read outside repo root: ${relPath}`);
  }
  if (!fs.existsSync(abs)) {
    fatal(`primary_file does not exist on disk: ${relPath}`);
  }
  const raw = fs.readFileSync(abs, "utf8");
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    fatal(`primary_file is not valid JSON (${relPath}): ${err.message}`);
  }
  return { abs, raw, parsed };
}

function buildPrompt(triage, fileContent) {
  const system = [
    "You are a precise engineering assistant that produces MINIMAL fixes to Splunk Observability out-of-the-box (OOTB) content JSON.",
    "You must return ONLY strict JSON matching the schema below — no markdown, no commentary, no code fences.",
    "",
    "SCHEMA (RFC-6902 subset):",
    "{",
    '  "confidence": 0.0-1.0,',
    '  "explanation": "<= 300 chars, human-readable why this file and this change fix the reported bug",',
    '  "risk_notes": "<= 200 chars, anything reviewers must double-check",',
    '  "patches": [',
    "    {",
    '      "file": "<must exactly equal the input file path>",',
    '      "operations": [',
    '        { "op": "replace", "path": "/rfc6902/json/pointer", "value": <any JSON> }',
    "      ]",
    "    }",
    "  ]",
    "}",
    "",
    "STRICT RULES:",
    "1. Only 'replace' operations. No add/remove/move/copy/test.",
    "2. Every 'path' MUST already exist in the current document; do not invent new keys.",
    "3. Do not change hashCode, id, version, importQualifier, or any field ending in '_id'.",
    "4. If you are less than 70% sure of the fix, return confidence < 0.7 and an empty patches array.",
    "5. Prefer the smallest possible change. Do not refactor.",
    "6. If the bug is ambiguous or cannot be fixed by editing this one file, return an empty patches array with an explanation.",
  ].join("\n");

  const user = [
    `# Reported bug`,
    triage.bug_text.trim(),
    "",
    `# Primary suspect file: ${triage.primary_file}`,
    "This is the ONLY file you are permitted to modify.",
    "Current contents:",
    "```json",
    JSON.stringify(fileContent, null, 2),
    "```",
    "",
    "Return the JSON object described in the system prompt.",
  ].join("\n");

  return [
    { role: "system", content: system },
    { role: "user", content: user },
  ];
}

async function callBridgeIt(accessToken, messages) {
  const payload = JSON.stringify({
    messages,
    user: JSON.stringify({ appkey: BRIDGE_API_APP_KEY }),
    stop: ["<|im_end|>"],
    temperature: BRIDGE_API_TEMPERATURE,
    top_p: BRIDGE_API_TOP_P,
    response_format: { type: "json_object" },
  });

  const resp = await httpRequest(
    {
      hostname: BRIDGE_API_HOSTNAME,
      path: BRIDGE_API_PATH,
      method: "POST",
      headers: {
        "api-key": accessToken,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload, "utf8"),
      },
    },
    payload
  );

  const content = resp?.choices?.[0]?.message?.content;
  if (!content) {
    fatal("BridgeIT response has no choices[0].message.content");
  }
  return content;
}

function parseProposal(raw) {
  let stripped = String(raw).trim();
  if (stripped.startsWith("```")) {
    stripped = stripped.replace(/^```(?:json)?\s*/i, "").replace(/```$/i, "").trim();
  }
  try {
    return JSON.parse(stripped);
  } catch (err) {
    fatal(`LLM returned non-JSON content: ${err.message}\n---\n${stripped.slice(0, 800)}`);
  }
}

function jsonPointerNavigate(doc, pointer) {
  if (!pointer.startsWith("/")) return { ok: false, reason: "pointer must start with /" };
  const tokens = pointer
    .split("/")
    .slice(1)
    .map((t) => t.replace(/~1/g, "/").replace(/~0/g, "~"));
  let parent = null;
  let key = null;
  let cursor = doc;
  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    if (cursor === null || typeof cursor !== "object") {
      return { ok: false, reason: `cannot descend into non-object at token ${i}` };
    }
    if (Array.isArray(cursor)) {
      const idx = Number(tok);
      if (!Number.isInteger(idx) || idx < 0 || idx >= cursor.length) {
        return { ok: false, reason: `array index out of range: ${tok}` };
      }
      parent = cursor;
      key = idx;
      cursor = cursor[idx];
    } else {
      if (!Object.prototype.hasOwnProperty.call(cursor, tok)) {
        return { ok: false, reason: `key not present: ${tok}` };
      }
      parent = cursor;
      key = tok;
      cursor = cursor[tok];
    }
  }
  return { ok: true, parent, key, existing: cursor };
}

const FORBIDDEN_PATH_SEGMENTS = ["hashCode", "id", "version", "importQualifier"];

function isForbiddenPath(pointer) {
  const tokens = pointer.split("/").slice(1);
  for (const tok of tokens) {
    if (FORBIDDEN_PATH_SEGMENTS.includes(tok)) return true;
    if (tok.endsWith("_id")) return true;
  }
  return false;
}

function applyProposal(proposal, triage, fileState) {
  const applied = [];
  const rejected = [];

  if (!Array.isArray(proposal.patches) || proposal.patches.length === 0) {
    return { applied, rejected: [{ reason: "no patches" }] };
  }

  for (const patch of proposal.patches) {
    if (!triage.allowed_files.includes(patch.file)) {
      rejected.push({ file: patch.file, reason: "file not in allowed_files" });
      continue;
    }
    if (patch.file !== triage.primary_file) {
      rejected.push({ file: patch.file, reason: "conservative mode: only primary_file is allowed" });
      continue;
    }
    if (!Array.isArray(patch.operations)) {
      rejected.push({ file: patch.file, reason: "operations must be an array" });
      continue;
    }

    let doc = fileState.parsed;
    for (const op of patch.operations) {
      if (!ALLOWED_OPS.has(op.op)) {
        rejected.push({ file: patch.file, op, reason: `op '${op.op}' not allowed` });
        continue;
      }
      if (typeof op.path !== "string") {
        rejected.push({ file: patch.file, op, reason: "path must be string" });
        continue;
      }
      if (isForbiddenPath(op.path)) {
        rejected.push({ file: patch.file, op, reason: "path touches immutable field" });
        continue;
      }
      const nav = jsonPointerNavigate(doc, op.path);
      if (!nav.ok) {
        rejected.push({ file: patch.file, op, reason: `path resolve failed: ${nav.reason}` });
        continue;
      }
      const before = nav.existing;
      nav.parent[nav.key] = op.value;
      applied.push({
        file: patch.file,
        path: op.path,
        before,
        after: op.value,
      });
    }
  }

  return { applied, rejected };
}

function writeSummary(payload) {
  try {
    fs.writeFileSync(OUTPUT_SUMMARY_PATH, JSON.stringify(payload, null, 2));
    log(`wrote summary -> ${OUTPUT_SUMMARY_PATH}`);
  } catch (err) {
    console.error(`[propose-fix] could not write summary: ${err.message}`);
  }
}

async function main() {
  requireEnv();
  const triage = loadTriage();
  log(`bug: ${triage.bug_text.slice(0, 100)}`);
  log(`primary_file: ${triage.primary_file}`);
  log(`allowed_files: ${JSON.stringify(triage.allowed_files)}`);

  const fileState = loadFileSafely(triage.primary_file);
  const messages = buildPrompt(triage, fileState.parsed);

  log(`authenticating to ${AUTH_API_HOSTNAME}...`);
  const accessToken = await bridgeItAuth();

  log(`calling ${BRIDGE_API_HOSTNAME}${BRIDGE_API_PATH} (model=${BRIDGE_API_MODEL_NAME}, temp=${BRIDGE_API_TEMPERATURE})...`);
  const raw = await callBridgeIt(accessToken, messages);
  const proposal = parseProposal(raw);

  const confidence = Number(proposal.confidence ?? 0);
  log(`LLM confidence: ${confidence.toFixed(2)} (threshold ${MIN_CONFIDENCE})`);
  log(`explanation: ${proposal.explanation || "(none)"}`);

  if (confidence < MIN_CONFIDENCE) {
    log(`confidence below threshold; leaving MR untouched.`);
    writeSummary({
      status: "low_confidence",
      confidence,
      threshold: MIN_CONFIDENCE,
      explanation: proposal.explanation,
      risk_notes: proposal.risk_notes,
      raw_proposal: proposal,
    });
    process.exit(0);
  }

  const { applied, rejected } = applyProposal(proposal, triage, fileState);

  if (applied.length === 0) {
    log(`no operations applied (${rejected.length} rejected). See summary for details.`);
    writeSummary({
      status: "no_applied_ops",
      confidence,
      explanation: proposal.explanation,
      risk_notes: proposal.risk_notes,
      rejected,
      raw_proposal: proposal,
    });
    process.exit(0);
  }

  const nextRaw = JSON.stringify(fileState.parsed, null, 2) + "\n";
  fs.writeFileSync(fileState.abs, nextRaw);
  log(`applied ${applied.length} op(s) to ${triage.primary_file} (rejected: ${rejected.length})`);

  writeSummary({
    status: "applied",
    confidence,
    explanation: proposal.explanation,
    risk_notes: proposal.risk_notes,
    applied,
    rejected,
    file: triage.primary_file,
    jira_key: triage.jira_key,
    mr_iid: triage.mr_iid,
    branch: triage.branch,
  });
}

main().catch((err) => {
  console.error(`[propose-fix] unhandled error: ${err?.stack || err}`);
  process.exit(1);
});
