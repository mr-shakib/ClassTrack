#!/usr/bin/env node
// Drive the ClassTrack web app in headless Chromium, one command per stdin line.
//
//   node .claude/skills/run-classtrack/driver.cjs <<'EOF'
//   login SRH classtrack
//   nav /profile
//   wait-text Change password
//   ss profile
//   EOF
//
// Commands (quote an argument with '...' or "..." when it has spaces):
//   nav <path|url>             go to a page; a path is relative to $CT_BASE
//   login <user> <password>    sign in through the real form; waits to leave /login
//   viewport <w> <h>           e.g. viewport 390 844 for a phone
//   click <selector>           any Playwright selector: css, text=..., role=...
//   fill <selector> <value>    the value is the rest of the line
//   select <selector> <value>  pick a <select> option by value (slot pickers)
//   press <key>                Enter, Tab, ...
//   wait-text <text>           until the text is visible (60s)
//   wait-gone <text>           until it is not, e.g. wait-gone Loading…
//   wait-url <glob>            e.g. wait-url **/teacher
//   ss <name> [full]           screenshot to $CT_RUN_DIR/shots/<name>.png
//   ss-el <selector> <name>    screenshot of one element
//   text <selector>            print the element's innerText
//   value <selector>           print an input's value
//   eval <js>                  print the result of a page expression
//   errors                     print console errors so far
//   sleep <ms>
//   # ...                      a comment
//
// Any failing command saves fail.png and exits 1.

const path = require("path");
const os = require("os");
const fs = require("fs");
const readline = require("readline");

const RUN =
  process.env.CT_RUN_DIR || path.join(process.env.TMPDIR || os.tmpdir(), "classtrack-run");
const BASE = process.env.CT_BASE || "http://localhost:3000";
const SHOTS = path.join(RUN, "shots");
const TIMEOUT = 60_000; // Next dev compiles each route on first visit.

function loadPlaywright() {
  try {
    return require("playwright");
  } catch {
    return require(path.join(RUN, "pw", "node_modules", "playwright"));
  }
}

function tokens(line) {
  const out = [];
  for (const m of line.matchAll(/"([^"]*)"|'([^']*)'|(\S+)/g)) out.push(m[1] ?? m[2] ?? m[3]);
  return out;
}

/** The rest of the line after `n` tokens, unquoted if it is one quoted string. */
function rest(line, n) {
  let s = line.trim();
  for (let i = 0; i < n; i++) {
    const m = s.match(/^("[^"]*"|'[^']*'|\S+)\s*/);
    s = s.slice(m[0].length);
  }
  const q = s.match(/^(["'])(.*)\1$/);
  return q ? q[2] : s;
}

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true });
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  // Headless Chromium runs in UTC whatever the host zone; the department, and
  // every time the app prints, is in Dhaka.
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    timezoneId: process.env.CT_TZ || "Asia/Dhaka",
  });
  const page = await ctx.newPage();
  page.setDefaultTimeout(TIMEOUT);

  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));

  const url = (p) => (/^https?:/.test(p) ? p : BASE + (p.startsWith("/") ? p : `/${p}`));

  const commands = {
    nav: async ([p]) => page.goto(url(p), { timeout: TIMEOUT }),
    login: async ([user, pass]) => {
      await page.goto(url("/login"), { timeout: TIMEOUT });
      await page.fill('input[autocomplete="username"]', user);
      await page.fill('input[autocomplete="current-password"]', pass);
      await page.click('button[type="submit"]');
      await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: TIMEOUT });
      return page.url();
    },
    viewport: async ([w, h]) => page.setViewportSize({ width: +w, height: +h }),
    click: async ([sel]) => page.click(sel),
    fill: async ([sel], line) => page.fill(sel, rest(line, 2)),
    select: async ([sel], line) => {
      await page.selectOption(sel, rest(line, 2));
    },
    press: async ([key]) => page.keyboard.press(key),
    "wait-text": async (_, line) =>
      page.getByText(rest(line, 1)).first().waitFor({ state: "visible" }),
    "wait-url": async ([glob]) => page.waitForURL(glob),
    "wait-gone": async (_, line) =>
      page.getByText(rest(line, 1)).first().waitFor({ state: "hidden" }),
    ss: async ([name, full]) => {
      const file = path.join(SHOTS, `${name}.png`);
      await page.screenshot({ path: file, fullPage: full === "full" });
      return file;
    },
    "ss-el": async ([sel, name]) => {
      const file = path.join(SHOTS, `${name}.png`);
      await page.locator(sel).first().screenshot({ path: file });
      return file;
    },
    text: async ([sel]) => page.locator(sel).first().innerText(),
    value: async ([sel]) => page.locator(sel).first().inputValue(),
    eval: async (_, line) => JSON.stringify(await page.evaluate(rest(line, 1))),
    errors: async () => (errors.length ? errors.join("\n") : "none"),
    sleep: async ([ms]) => page.waitForTimeout(+ms),
  };

  const rl = readline.createInterface({ input: process.stdin });
  let n = 0;
  for await (const raw of rl) {
    const line = raw.trim();
    n++;
    if (!line || line.startsWith("#")) continue;
    const [cmd, ...args] = tokens(line);
    const fn = commands[cmd];
    console.log(`> ${line}`);
    if (!fn) {
      console.log(`ERR line ${n}: unknown command ${cmd}`);
      await browser.close();
      process.exit(1);
    }
    try {
      const out = await fn(args, line);
      if (typeof out === "string") console.log(out);
    } catch (err) {
      console.log(`ERR line ${n}: ${err.message.split("\n")[0]}`);
      await page.screenshot({ path: path.join(SHOTS, "fail.png") }).catch(() => {});
      console.log(`page: ${page.url()}  screenshot: ${path.join(SHOTS, "fail.png")}`);
      await browser.close();
      process.exit(1);
    }
  }
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
