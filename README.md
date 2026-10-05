# Overrule

**An on-chain appeal court for content-moderation decisions — built as a GenLayer Intelligent Contract.**

A platform publishes an immutable rulebook, then issues moderation decisions against
users citing rules from it. The person on the receiving end gets exactly one appeal.
Validators re-read the frozen rulebook and the live content, classify each cited rule,
and the contract derives the outcome **in code**.

> The model classifies. The contract decides.

---

## Live on studionet

| | |
|---|---|
| Contract | [`0x76D56AA824a00B3378c3ADB49224fdFb0376F46c`](https://explorer-studio.genlayer.com/address/0x76D56AA824a00B3378c3ADB49224fdFb0376F46c) |
| Network | studionet (chain ID 61999) |
| dApp | <https://god-jia.github.io/genlayer-overrule/> |
| Deploy tx | [`0x997b858a…05c29195`](https://explorer-studio.genlayer.com/tx/0x997b858ab5ac4f3721310e920499ffe525ce19d273c2a77f6649d10a05c29195) |

The full lifecycle has been executed against studionet with real validators, a real web
fetch, and a real LLM round:

| Step | Transaction | Result |
|---|---|---|
| `publish_rulebook` | [`0xf3e03d72…c93ba419`](https://explorer-studio.genlayer.com/tx/0xf3e03d72d118dc59fbd093bb59886c4e8b979ee6a700a5f67848f102c93ba419) | rulebook #0 frozen |
| `issue_decision` | [`0x37b08bb0…24260a5c`](https://explorer-studio.genlayer.com/tx/0x37b08bb0ed96932aeec491e3f56b5a16673bff754558919467dfccca24260a5c) | decision #0, rule `H1` cited |
| `appeal` | [`0xac0970fa…4ecfa183`](https://explorer-studio.genlayer.com/tx/0xac0970fa149c6c7c7e2fff35dacab00a1981f696730a2afd7092fa994ecfa183) | filed by the subject wallet |
| `adjudicate` | [`0x1016b375…7d959315`](https://explorer-studio.genlayer.com/tx/0x1016b375f53aabb0f1aad652fab99262c167a2488006e82248b217427d959315) | `overturned`, rule classified `unsupported` |

The adjudication record returned on-chain:

```json
{
  "result": "overturned",
  "content_available": true,
  "confidence": 99,
  "rule_verdicts": [
    {
      "id": "H1",
      "verdict": "unsupported",
      "reason": "The content is a generic example-domain webpage and does not demean, threaten, dehumanize, or target any specific person or group."
    }
  ],
  "reasoning": "The visible content is standard informational text about a documentation example domain, with no harassment or references to any person or group. Because H1 could apply to user posts in general but this specific content shows none of the prohibited behavior, the citation is unsupported."
}
```

Per-platform statistics read back from the contract:

```json
{ "issued": 1, "adjudicated": 1, "upheld": 0, "overturned": 1, "remanded": 0 }
```

## Why this needs GenLayer

A moderation appeal has two halves, and a normal smart contract can only do one of them.

| Half | Nature | Where it belongs |
|---|---|---|
| Was rule `H1` actually applied correctly to this post? | subjective, needs reading a live web page | non-deterministic |
| Upheld / overturned / remanded, and the counters | mechanical, must be identical for everyone | deterministic |

GenLayer lets both halves live in one contract. `gl.nondet.web.render` fetches the post
and the appellant's evidence at adjudication time; `gl.nondet.exec_prompt` asks the
model for a per-rule classification; `gl.vm.run_nondet_unsafe` runs a validator function
that only accepts a leader result it can independently reproduce.

The important design choice: **the model never picks the outcome.** It returns one of
three labels per rule (`applied` / `misapplied` / `unsupported`). A pure Python function
maps those labels to `upheld` / `overturned` / `remanded`. A model that is talked into
a bad classification still cannot talk its way into a bad verdict, and two validators
that disagree on a label disagree on the outcome — which is exactly the signal the
consensus round is supposed to catch.

## The lifecycle

```
publish_rulebook(name, rules_json)          -> rulebook_id     (frozen, digest-pinned)
issue_decision(rulebook_id, subject, ...)   -> decision_id     (platform only)
appeal(decision_id, argument, evidence)                        (subject only, once)
adjudicate(decision_id)                                        (anyone, after appeal)
```

1. **Rulebook is frozen.** `publish_rulebook` canonicalises the rules, stores a
   `sha256:` digest next to them, and never exposes a mutation path. A decision records
   the digest it was issued under, so the standard an appeal is judged against cannot be
   edited after the fact. This is the whole point — most "appeal" processes are judged
   against a policy that the platform can quietly rewrite.

2. **A decision cites rules by id.** `issue_decision` rejects any rule id that is not in
   the rulebook, so a decision can never be justified by a rule that does not exist.

3. **One appeal, by the subject only.** The contract compares
   `gl.message.sender_address` against the stored `subject`. A platform cannot appeal on
   a user's behalf.

4. **Adjudication is re-derivable.** During `adjudicate`, `evaluate()` fetches the
   content URL and every evidence URL, builds a prompt that puts all fetched text inside
   tagged, explicitly-untrusted blocks, and asks for a JSON classification. The
   `validate()` function re-runs `evaluate()` and accepts the leader only if the derived
   outcome matches, every rule label matches, and the self-reported confidence is within
   25 points.

## Trust boundaries

Everything the contract did not write itself is treated as data, not instruction:

- The content under moderation, the appellant's argument, the appellant's evidence, and
  the platform's own stated reason all arrive inside `<content>`, `<argument>`,
  `<evidence>` and `<platform_reason>` blocks.
- The prompt states, in the data region itself, that instructions found inside those
  blocks must never be followed — even if they claim to come from the platform, a
  moderator, or the system.
- The cited rules are printed from on-chain storage and labelled authoritative, so a
  prompt-injection payload inside the post cannot redefine the rule it is judged by.
- If the content URL cannot be fetched, the outcome is forced to `remanded` rather than
  letting a missing page be scored as compliance.

## What the contract does *not* do

- It does not move funds. There is no token, no bond, no escrow.
- It does not enforce the platform's action. Removing a post is the platform's job; this
  contract produces a recorded, reviewable verdict.
- It is not a governance system. One platform, one rulebook namespace.

The deliverable is accountability: a decision, an appeal, and a verdict that anyone can
re-read later and check.

## Repository layout

```
contracts/overrule.py            the Intelligent Contract
tests/direct/test_overrule.py    19 direct-mode unit tests
docs/index.html                  the dApp (served by GitHub Pages)
docs/styles.css
docs/app.js                      genlayer-js wiring
gltest.config.yaml
requirements.txt
```

## Running the tests

The tests run in **direct mode** — no network, no Studio, no validators. Web and LLM
calls are mocked, so the whole suite runs in under a second.

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
pytest -q
```

```
19 passed in 0.76s
```

Coverage:

- rulebook validation (rule count, id uniqueness, text length bounds)
- only the publisher can issue decisions against their own rulebook
- a platform cannot issue a decision against itself
- unknown cited rule ids are rejected
- only the subject can appeal, and only once
- adjudication derives `upheld` / `overturned` / `remanded` from the label set
- an unfetchable content URL forces `remanded`
- per-platform transparency counters

Static analysis:

```bash
.venv/Scripts/genvm-lint.exe contracts/overrule.py
```

## Deploying the contract

The contract is already deployed on studionet at the address above. To deploy your own
copy:

1. Open [GenLayer Studio](https://studio.genlayer.com).
2. Paste `contracts/overrule.py` into the contract editor.
3. Click **Deploy** and copy the resulting contract address.
4. In the dApp, set the network to `studionet` and paste that address into
   **Overrule contract address**.

Studio funds the account for you with the built-in faucet, so no real GEN is needed.

To deploy from a script instead, `genlayer-js` exposes the same path:

```js
import fs from 'node:fs';
import { createAccount, createClient } from 'genlayer-js';
import { studionet } from 'genlayer-js/chains';

const client = createClient({ chain: studionet, account: createAccount() });
const hash = await client.deployContract({
  code: fs.readFileSync('contracts/overrule.py', 'utf8'),
  args: [],
});
const receipt = await client.waitForTransactionReceipt({ hash, status: 'FINALIZED' });
console.log(receipt.txDataDecoded.contractAddress);
```

## Using the dApp

A hosted copy runs at <https://god-jia.github.io/genlayer-overrule/> (served from the
`docs/` folder of this repository). To run it locally:

```bash
cd docs
python -m http.server 8080
```

Then open <http://localhost:8080>. The page is plain HTML/CSS/JS with no build step; the
only dependency is `genlayer-js`, loaded from a CDN as an ES module.

The four tabs mirror the contract lifecycle:

- **Platform console** — publish a rulebook, then issue a decision citing rule ids from it.
- **Appeal** — load a decision, read it, and appeal it as the subject wallet.
- **Adjudicate** — trigger adjudication on an appealed decision and watch the verdict land.
- **Transparency** — per-platform issued / adjudicated / upheld / overturned / remanded
  counts, with an overturn rate. This is the number a user cannot get from the platform
  today.

Reads work without a wallet. Writing needs an EIP-1193 wallet (MetaMask) on the selected
network.

### A full end-to-end walkthrough

You need two wallets: one acting as the platform, one acting as the user.

1. Connect wallet A. On **Platform console**, publish the prefilled rulebook. Note the id
   that comes back (usually `0`).
2. Still on wallet A, fill in **Issue a decision**: subject = wallet B's address,
   cited rules = `H1`, content URL = any public page that plausibly violates rule `H1`,
   and a stated reason of at least 20 characters. Submit.
3. Switch to wallet B and connect. Open **Appeal**, load the decision id, and submit an
   argument of at least 40 characters.
4. On **Adjudicate**, load the decision and press *Adjudicate*. Validators fetch the
   content, classify each cited rule, and the outcome appears in the record.
5. Open **Transparency** and load wallet A's address to see the counters move.

## License

MIT — see [LICENSE](LICENSE).
