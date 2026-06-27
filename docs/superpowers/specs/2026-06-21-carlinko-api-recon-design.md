# Carlinko Cloud API Recon — Design Spec

**Date:** 2026-06-21
**Sub-project:** 1 of 3 (foundation)
**Status:** Approved, ready for implementation planning

## Context

The user owns a Jaecoo J5 EV Premium (delivered 2026-06-15). In Asia this car has no
first-party companion app (unlike the UK/Europe version). Owners use the third-party
**Carlinko** app as their telematics companion: phone → vendor cloud → car (car has a
telematics SIM; data flows over the internet, works away from the car).

The user wants, eventually:
1. **Map the cloud API** (this sub-project) — the foundation.
2. A **data logger / analytics** layer (later sub-project).
3. A **better dashboard app** (later sub-project).

This is authorized personal reverse engineering for interoperability: the user owns the
car and uses their own account. Not for redistribution or accessing other users' data.

### TPMS reality check
The motivating example was per-wheel PSI (Carlinko only shows "normal/abnormal"). If the
J5 EV uses **indirect TPMS** (estimates from ABS wheel-speed, no pressure sensor in the
wheel), then PSI values do not exist anywhere — not in the app, cloud, or on CAN — and
cannot be extracted. If it uses **direct TPMS** (sensor per wheel), PSI exists on CAN and
the cloud *may* carry it even if Carlinko hides it. **Confirm which type the car has
before promising any PSI feature.** This is a data-source question to resolve during
endpoint mapping (Step 5), not an assumption.

## Goal

Reverse the Carlinko cloud telematics API for the Jaecoo J5 EV well enough to issue
authenticated **read and control** requests from the user's own code, outside the app.

## Approach

**Hybrid static + dynamic** RE. Static decompile maps the "what" (endpoints, auth, crypto,
cert-pinning location); dynamic interception captures the "how" (live requests, real auth
tokens, encrypted-payload plaintext). Each covers the other's blind spot.

Rationale over alternatives:
- *Dynamic-only (MITM):* fails if payloads are encrypted/signed beyond TLS — likely here.
- *Static-only (decompile):* no real tokens/values; obfuscation slows confirmation.

**Expected hard part:** Jaecoo/Chery's backend is likely Chinese (Lion/iCar-style). Such
apps commonly **encrypt and sign request payloads beyond TLS** (AES key baked into the
app, per-request HMAC/RSA signature). Plain TLS interception may show ciphertext. Static
decompile finds the crypto scheme; Frida confirms it at runtime. This drives the hybrid
choice.

## Recon findings (2026-06-21) — APK static analysis

Pulled the v1.12.0 XAPK (versionCode 172, arm64-v8a) from APKPure and analysed it before
running. Key findings that reshape the toolchain:

- **The app is built with Flutter.** Native libs are `libflutter.so` + `libapp.so`
  (Dart AOT snapshot). Business logic, endpoints, and crypto are compiled into
  `libapp.so` — **not** in the DEX. So jadx/DEX analysis is largely useless here.
- **HTTP client: `dio`** (Dart). Interceptors (`app_dio`, `*_http_utils`) do the
  request signing/encryption.
- **Crypto: `pointycastle`** (Dart). Symbols present for AES (block/AEAD ciphers),
  HMAC/MAC, RSA, SHA256, MD5, signer, secure-random. Signing-related strings:
  `appKey`, `sign`, `signature`, `nonce`, `timeStamp`, `deviceId`, `token`.
  → Almost certainly: AES-encrypt the body + an HMAC/hash signature over
  params+nonce+timestamp. Classic Chinese API-gateway scheme.
- **API backends:** `cqr-api-{region}.hzhjcl.com` with paired `cqr-pub-{region}.hzhjcl.com`.
  Regions: `sea, ap, emea, me, sam, saf, naf, uzb, vn`. **`cqr-api-sea` = the likely
  region for Indonesia** (confirm at login). `hzhjcl` = Hangzhou Huijie (慧捷车联), the
  vendor. `cqr` = package prefix `com.cqr.CarLinko`.

**Consequence for interception:** Flutter does **not** honour the Android system proxy and
does **not** use the system/user CA store — it ships its own BoringSSL inside
`libflutter.so`. Standard mitmproxy + system CA will see nothing. Must use a Flutter-aware
approach (see toolchain).

## Environment / Lab (Windows host)

NOTE: the app is **ARM-only** (no x86_64 native libs). The x86_64 emulator image gives
`INSTALL_FAILED_NO_MATCHING_ABIS` and has no ARM translation. So the lab uses an
**arm64-v8a system image** (full emulation, slower but correct), or Genymotion with ARM
translation as a faster fallback.

| Component | Choice | Notes |
|---|---|---|
| Emulator | Android Studio AVD, **Google APIs arm64-v8a** image, **API 33** (Android 13) | Rootable (not Play image). API ≤33 keeps CA-cert install easy. Slow (no HW accel). Genymotion+ARM-translation = faster fallback. |
| Bridge | adb + cmdline-tools (sdkmanager/avdmanager) | SDK at `F:\AndroidStudioSDK`; cmdline-tools installed under `cmdline-tools\latest`. |
| Dart decompile | **Blutter** | `libapp.so` (Dart AOT) → pseudocode + Frida hooks. Recovers AES key + sign algorithm statically. |
| Flutter MITM | **reFlutter** (patch APK: disable pinning + set proxy) **or** Frida hook on `libflutter` BoringSSL `ssl_verify` | Needed because Flutter bypasses system proxy/CA. Capture into mitmproxy/Burp. |
| Runtime hooks | Frida + frida-server (arm64) | Hook `pointycastle` AES/HMAC to dump key + plaintext; confirm sign algo. |
| DEX (minor) | jadx | Only to inspect Flutter plugins / MethodChannels, not business logic. |
| Replay / scripting | Python 3 + requests | Reproduce auth + signing, replay endpoints. |

The user's iOS device is their daily phone (paired to the car) — used to **observe real
app behavior**, not for interception (iOS RE is harder; the emulator does the RE work).

## Workflow (Flutter-adjusted)

1. **Lab setup** — Boot rooted **arm64-v8a** AVD (API 33, Google APIs). Install the
   CarLinko split APKs (`install-multiple`). Push arm64 `frida-server`.
2. **Static recon (DONE 2026-06-21)** — Confirmed Flutter / dio / pointycastle, API hosts
   `cqr-api-{region}.hzhjcl.com`, signing fields. See "Recon findings".
3. **Dart decompile (Blutter)** — Run Blutter on `libapp.so` to recover: the dio signing
   interceptor, the AES key + mode + IV derivation, the HMAC/hash sign algorithm, and the
   login/token flow. This is the crux for reproducing requests.
4. **Flutter MITM** — Patch the APK with **reFlutter** (or Frida-hook `libflutter` BoringSSL
   `ssl_verify`) so traffic routes to the proxy. Log in; capture live requests/responses
   (still encrypted bodies, but real headers, tokens, endpoint usage).
5. **Crypto confirmation** — Frida-hook `pointycastle` AES/HMAC at runtime to dump the live
   key and plaintext; cross-check against Blutter output. Reproduce signing in Python.
6. **Endpoint mapping** — Exercise every feature (status, location, battery, charge,
   climate, lock, **TPMS**); capture + decrypt each; document the schema. Read **and**
   control. Resolve direct-vs-indirect TPMS here (expectation: indirect → no PSI exists).
7. **Replay harness** — Python: login → token → read calls → **one low-risk control call**
   (find-car / climate — *not* safety-critical first). Prove end-to-end outside the app.
8. **Document** — Auth flow, signing algorithm, endpoint catalog with samples.

## Control-endpoint risk handling

Control (write) calls may require extra: device binding, a PIN/2FA, a vehicle-control
token, or a replay nonce. Mitigations:
- Start with the **lowest-risk** control (flash lights / find car / climate), never a
  safety-critical action first.
- Test against the user's own car and observe the physical result.
- **Rate-limit politely**; never spam control endpoints.

## Deliverables

- `lab-setup.md` — reproducible environment setup.
- `api-map.md` — endpoint catalog + auth flow + crypto scheme, with sample req/resp.
- `replay.py` — working authenticated read + one control call.
- Captured traffic samples — **sanitized** (strip the user's tokens/VIN before any sharing).

## Validation / Testing

- Per endpoint: replayed Python request reproduces the app's behavior (e.g. a lock call
  actually locks the car).
- Crypto: a request the server **accepts** confirms the signing scheme is correct.

## Out of scope (YAGNI — later sub-projects)

Dashboard UI, scheduled data logger, Home Assistant / smart-home integration, multi-user.

## Early unknowns to kill first

- Does Carlinko ship an **Android** build? (Need the APK. If iOS-only, the plan changes.)
- Is the backend reachable from the user's region without a VPN?
- Exact app **package name / vendor** behind Carlinko.

## Legal / ToS posture

Own account only, personal interoperability use, polite rate-limiting, never access other
users' data, no redistribution of credentials or captured tokens. Sanitize samples.
